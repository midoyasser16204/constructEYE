"""
Construct Eye — Construction Progress Report Generator
Raspberry Pi 5: dual-track structural + architectural analysis, PDF, Firebase upload.

Expected Test folder layout:
  Architectural View.png          <- architectural reference
  Structural View.png             <- structural reference
  Building Under Construction (...).png  <- site photos
-
Usage:
  python3 construction_progress_report.py /path/to/Test
  python3 construction_progress_report.py /path/to/Test --no-upload

Environment:
  MOONDREAM_API_KEY          Moondream cloud API key (get from https://moondream.ai)
  FIREBASE_SERVICE_ACCOUNT   Path to Firebase admin JSON key (never commit this file)
  FIREBASE_STORAGE_BUCKET    e.g. YOUR_PROJECT_ID.appspot.com

Install on Pi:
  pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "shared"))
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import base64
import requests
from PIL import Image

try:
    from fpdf import FPDF
    try:
        from fpdf.enums import XPos, YPos
    except ImportError:
        XPos = YPos = None  # type: ignore[misc, assignment]
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    XPos = YPos = None  # type: ignore[misc, assignment]

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

from firebase_common import (
    DEVICE_LOCATION,
    PROJECT_ID,
    SITE_NAME,
    build_construction_report_notification,
    detect_device_location,
    get_or_create_device_id,
    NOTIFICATION_TYPE_CONSTRUCTION_REPORT,
    notify_project_users,
    register_device,
)

try:
    from progress_report_gui import (
        DEFAULT_GUI_ICON,
        DEFAULT_GUI_LOGO,
        NullReportProgress,
        ReportProgressTracker,
        gui_available,
        run_with_gui,
    )

    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    DEFAULT_GUI_ICON = str(_PROJECT_ROOT / "assets" / "branding" / "construct_eye_logo.ico")
    DEFAULT_GUI_LOGO = str(_PROJECT_ROOT / "assets" / "branding" / "construct_eye_logo.png")

    class NullReportProgress:  # type: ignore[no-redef]
        def bind_gui(self, gui: Any) -> None:
            return

        def section_start(self, section_id: str, title: str) -> None:
            return

        def section_complete(self, section_id: str) -> None:
            return

        def step_start(self, section_id: str, step_key: str, label: Optional[str] = None) -> None:
            return

        def step_complete(self, section_id: str) -> None:
            return

        def set_status(self, message: str) -> None:
            return

        def complete(self, summary: Dict[str, Any]) -> None:
            return

        def fail(self, message: str) -> None:
            return

    ReportProgressTracker = NullReportProgress  # type: ignore[misc,assignment]

    def gui_available() -> bool:
        return False

    def run_with_gui(job: Any, *, total_steps: int) -> int:
        return job(NullReportProgress())


DEFAULT_LOCATION = DEVICE_LOCATION
DEFAULT_SITE_NAME = SITE_NAME
DEFAULT_IMAGE_DIR = os.getenv("CONSTRUCT_EYE_IMAGE_DIR", str(_PROJECT_ROOT / "sample-site-images"))
DEFAULT_REPORTS_DIR = str(_PROJECT_ROOT / "progress-reporting" / "output" / "construction_reports")
DEFAULT_PDF_LOGO = str(_PROJECT_ROOT / "assets" / "branding" / "construct_eye_logo.png")
PDF_HEADER_BAND_MM = 18.0
PDF_HEADER_ACCENT_MM = 2.0
PDF_PAGE_TOP_MARGIN_MM = PDF_HEADER_BAND_MM + PDF_HEADER_ACCENT_MM + 8.0
STORAGE_IMAGE_PREFIX = "construction_progress"
STORAGE_PDF_PREFIX = "construction_reports/pdf"
FIRESTORE_COLLECTION = "construction_reports"
SCRIPT_VERSION = "2.4.0"
REFERENCE_CACHE_VERSION = 1
DEFAULT_REFERENCE_CACHE_DIR = str(_PROJECT_ROOT / "progress-reporting" / "output" / "reference_metrics_cache")

ProgressTracker = Union["ReportProgressTracker", "NullReportProgress"]

MOONDREAM_BASE_URL = "https://api.moondream.ai/v1"
MOONDREAM_HOST = "api.moondream.ai"
MOONDREAM_RETRIES = 4
MOONDREAM_RETRY_DELAY_S = 3.0
MIN_SITE_ANALYSIS_SUCCESS_RATE = 0.75
ARCHITECTURAL_HINTS = ("architectural", "architecture")
STRUCTURAL_HINTS = ("structural", "structure")
ALL_REFERENCE_HINTS = ARCHITECTURAL_HINTS + STRUCTURAL_HINTS + ("reference", "design")


class AnalysisQualityError(RuntimeError):
    """Raised when too many Moondream site-analysis calls fail to trust the report."""


class MoondreamClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Moondream API key is required")
        self.headers = {"X-Moondream-Auth": api_key, "Content-Type": "application/json"}
        self.failed_requests = 0

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as handle:
            raw = handle.read()
        suffix = Path(image_path).suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        return f"data:{mime};base64,{base64.b64encode(raw).decode('utf-8')}"

    @staticmethod
    def verify_connectivity() -> None:
        """Fail fast when the Pi cannot resolve or reach the Moondream API."""
        import socket

        try:
            socket.getaddrinfo(MOONDREAM_HOST, 443)
        except socket.gaierror as exc:
            raise AnalysisQualityError(
                f"Cannot resolve {MOONDREAM_HOST} ({exc}). "
                "Check Pi internet/DNS before running a report."
            ) from exc

        try:
            response = requests.get(
                f"https://{MOONDREAM_HOST}",
                timeout=15,
            )
            if response.status_code >= 500:
                raise AnalysisQualityError(
                    f"Moondream API returned HTTP {response.status_code}. Try again shortly."
                )
        except requests.RequestException as exc:
            raise AnalysisQualityError(
                f"Cannot reach {MOONDREAM_HOST} ({exc}). "
                "Check Pi internet connection, then re-run."
            ) from exc

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, MOONDREAM_RETRIES + 1):
            try:
                response = requests.post(
                    f"{MOONDREAM_BASE_URL}/{endpoint}",
                    json=payload,
                    headers=self.headers,
                    timeout=120,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < MOONDREAM_RETRIES:
                    delay = MOONDREAM_RETRY_DELAY_S * attempt
                    print(
                        f"[WARN] Moondream {endpoint} attempt {attempt}/{MOONDREAM_RETRIES} "
                        f"failed: {exc}; retrying in {delay:.0f}s..."
                    )
                    time.sleep(delay)
        assert last_exc is not None
        raise last_exc

    def caption(self, image_path: str, prompt: str, length: str = "long") -> str:
        try:
            data = self._post("caption", {
                "image_url": self._encode_image(image_path),
                "stream": False,
                "length": length,
                "prompt": prompt,
            })
            return (data.get("caption") or "").strip()
        except Exception as exc:
            self.failed_requests += 1
            print(f"[ERROR] Moondream caption failed: {exc}")
            return ""

    def query(self, image_path: str, question: str) -> str:
        try:
            data = self._post("query", {
                "image_url": self._encode_image(image_path),
                "stream": False,
                "question": question,
            })
            return (data.get("answer") or "").strip()
        except Exception as exc:
            self.failed_requests += 1
            print(f"[ERROR] Moondream query failed: {exc}")
            return ""


def parse_int_answer(text: str, default: int = 0) -> int:
    if not text:
        return default
    match = re.search(r"-?\d+", text.replace(",", ""))
    if not match:
        return default
    try:
        return max(0, int(match.group()))
    except ValueError:
        return default


def parse_yes_no(text: str) -> bool:
    return "yes" in (text or "").lower()


def parse_days_answer(text: str) -> int:
    """Parse Moondream day/month estimates from free-form answers."""
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return 0

    month_match = re.search(r"(\d+)\s*(?:months?|mos?)\b", cleaned)
    if month_match:
        return max(0, int(month_match.group(1)) * 30)

    week_match = re.search(r"(\d+)\s*(?:weeks?|wks?)\b", cleaned)
    if week_match:
        return max(0, int(week_match.group(1)) * 7)

    day_match = re.search(r"(\d+)\s*(?:days?)\b", cleaned)
    if day_match:
        return max(0, int(day_match.group(1)))

    return max(0, parse_int_answer(cleaned, 0))


def metric_completion_days(
    remaining_percentage: float,
    structural_remaining: float,
    architectural_remaining: float,
) -> int:
    """Progress-based day estimate derived from structural/architectural analysis."""
    weighted_remaining = (
        (remaining_percentage * 0.40)
        + (structural_remaining * 0.30)
        + (architectural_remaining * 0.30)
    )
    if weighted_remaining <= 0.5:
        return 0
    pace_factor = 2.2
    if architectural_remaining > structural_remaining:
        pace_factor = 2.6
    return max(14, min(730, round(weighted_remaining * pace_factor)))


def blend_completion_days(ai_days: int, metric_days: int, remaining_percentage: float) -> int:
    """Combine Moondream visual estimate with calculated progress metrics."""
    if remaining_percentage <= 0.5:
        return 0
    if ai_days <= 0:
        return metric_days
    blended = round((ai_days * 0.65) + (metric_days * 0.35))
    return max(14, min(730, blended))


def split_completion_duration(total_days: int) -> Dict[str, int]:
    """Split total days into months (30d), weeks (7d), and remaining days."""
    if total_days <= 0:
        return {"total_days": 0, "months": 0, "weeks": 0, "days": 0}
    months = total_days // 30
    remainder = total_days % 30
    weeks = remainder // 7
    days = remainder % 7
    return {
        "total_days": total_days,
        "months": months,
        "weeks": weeks,
        "days": days,
    }


def format_completion_duration_label(breakdown: Dict[str, int]) -> str:
    total = breakdown["total_days"]
    if total <= 0:
        return "0 days"
    return (
        f"{total} days "
        f"({breakdown['months']} months, {breakdown['weeks']} weeks, {breakdown['days']} days)"
    )


def format_completion_estimate(
    days: int,
    reference: datetime,
    *,
    ai_days: int = 0,
    metric_days: int = 0,
) -> Dict[str, Any]:
    """Build Firestore/PDF completion fields from blended day count."""
    if days <= 0:
        return {
            "estimated_completion_days": 0,
            "estimated_completion_months": 0,
            "estimated_completion_weeks": 0,
            "estimated_completion_breakdown_days": 0,
            "estimated_completion_date": reference.date().isoformat(),
            "estimated_completion_date_display": reference.strftime("%d %B %Y"),
            "estimated_completion_duration_label": "0 days",
            "estimated_completion_ai_days": ai_days,
            "estimated_completion_metric_days": metric_days,
            "estimated_completion_explanation": (
                "The project appears substantially complete based on current AI site analysis."
            ),
            "estimated_completion_summary": (
                "Estimated completion: the project appears substantially complete "
                "based on current AI site analysis."
            ),
            "estimated_completion_detail": (
                "Estimated completion: the project appears substantially complete "
                "based on current AI site analysis."
            ),
        }

    breakdown = split_completion_duration(days)
    completion_date = (reference + timedelta(days=days)).date()
    date_label = completion_date.strftime("%d %B %Y")
    duration_label = format_completion_duration_label(breakdown)

    if ai_days <= 0:
        explanation = (
            f"The {days}-day estimate is based on remaining structural and architectural "
            f"progress from the site analysis (metric estimate: {metric_days} days)."
        )
    else:
        explanation = (
            f"The {days}-day total blends Moondream AI visual assessment ({ai_days} days) "
            f"with progress-metric calculation ({metric_days} days), weighted 65% AI and "
            f"35% metrics from current site analysis."
        )

    summary = (
        f"Estimated completion in {days} days "
        f"({breakdown['months']} months, {breakdown['weeks']} weeks, {breakdown['days']} days), "
        f"around {date_label}."
    )
    detail = (
        f"{summary} {explanation}"
    )

    return {
        "estimated_completion_days": days,
        "estimated_completion_months": breakdown["months"],
        "estimated_completion_weeks": breakdown["weeks"],
        "estimated_completion_breakdown_days": breakdown["days"],
        "estimated_completion_date": completion_date.isoformat(),
        "estimated_completion_date_display": date_label,
        "estimated_completion_duration_label": duration_label,
        "estimated_completion_ai_days": ai_days,
        "estimated_completion_metric_days": metric_days,
        "estimated_completion_explanation": explanation,
        "estimated_completion_summary": summary,
        "estimated_completion_detail": detail,
    }

def _matches_hints(filename: str, hints: Tuple[str, ...]) -> bool:
    name = filename.lower()
    return any(hint in name for hint in hints)


class ReferenceMetricsCache:
    """Persist structural/architectural reference AI metrics between report runs."""

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def fingerprint(image_path: str) -> str:
        resolved = os.path.abspath(image_path)
        stat = os.stat(resolved)
        return f"{resolved}|{stat.st_size}|{int(stat.st_mtime)}"

    def _cache_file(self, image_path: str, metric_type: str) -> Path:
        stem = Path(image_path).stem.replace(" ", "_")
        digest = hashlib.sha256(self.fingerprint(image_path).encode("utf-8")).hexdigest()[:12]
        return self.cache_dir / f"{metric_type}_{stem}_{digest}.json"

    def _read_payload(self, image_path: str, metric_type: str) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        cache_file = self._cache_file(image_path, metric_type)
        if not cache_file.exists():
            return None, None
        try:
            with open(cache_file, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] Could not read reference cache {cache_file.name}: {exc}")
            return cache_file, None
        return cache_file, payload

    def is_valid(self, image_path: str, metric_type: str) -> bool:
        _cache_file, payload = self._read_payload(image_path, metric_type)
        if not payload:
            return False
        return (
            payload.get("version") == REFERENCE_CACHE_VERSION
            and payload.get("fingerprint") == self.fingerprint(image_path)
            and payload.get("metric_type") == metric_type
        )

    def has_valid(self, image_path: str, metric_type: str) -> bool:
        return self.is_valid(image_path, metric_type)

    def load(self, image_path: str, metric_type: str) -> Optional[Dict[str, Any]]:
        cache_file, payload = self._read_payload(image_path, metric_type)
        if not payload:
            return None

        if payload.get("version") != REFERENCE_CACHE_VERSION:
            return None
        if payload.get("fingerprint") != self.fingerprint(image_path):
            print(f"[INFO] Reference cache stale for {os.path.basename(image_path)} (image changed)")
            return None
        if payload.get("metric_type") != metric_type:
            return None

        metrics = dict(payload.get("metrics") or {})
        metrics["reference_image"] = os.path.basename(image_path)
        metrics["reference_path"] = os.path.abspath(image_path)
        if cache_file is not None:
            metrics["_cache_file"] = str(cache_file)
        return metrics

    def save(self, image_path: str, metric_type: str, metrics: Dict[str, Any]) -> Path:
        cache_file = self._cache_file(image_path, metric_type)
        payload = {
            "version": REFERENCE_CACHE_VERSION,
            "metric_type": metric_type,
            "image_path": os.path.abspath(image_path),
            "image_name": os.path.basename(image_path),
            "fingerprint": self.fingerprint(image_path),
            "cached_at": datetime.now().isoformat(),
            "metrics": {
                key: value
                for key, value in metrics.items()
                if not str(key).startswith("_")
            },
        }
        with open(cache_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print(f"[CACHE] Saved {metric_type} metrics -> {cache_file}")
        return cache_file


class ConstructionProgressEngine:
    """Dual-track analysis: structural vs architectural."""

    STRUCTURAL_REFERENCE_QUESTIONS = {
        "total_floors": "How many floor levels does this structural design show? Count every level including ground floor. Answer with a number only.",
        "structural_system": "What is the main structural system? Choose one: [concrete frame, steel frame, load-bearing masonry, mixed, other]. Answer with the exact phrase only.",
        "column_count": "Approximately how many vertical structural columns are visible on the front facade? Answer with a number only.",
        "floor_slabs": "How many floor slabs are visible in this structural design? Answer with a number only.",
        "roof_structure": "What is the roof structure type? Choose one: [flat slab, pitched roof frame, parapet wall, not visible]. Answer with the exact phrase only.",
    }

    STRUCTURAL_SITE_QUESTIONS = {
        "built_floors": "How many floor levels are currently built and visible? Count every completed level including ground floor. Answer with a number only.",
        "visible_columns": "Are vertical structural columns visible on the building? Answer only yes or no.",
        "floor_slabs_cast": "How many floor slabs appear cast and complete? Answer with a number only.",
        "roof_slab_status": "What is the structural roof slab status? Choose one: [no roof slab yet, roof slab cast but open, roof slab complete]. Answer with the exact phrase only.",
        "scaffolding": "Is scaffolding visible around the building? Answer only yes or no.",
        "workers_visible": "Are construction workers visible? Answer only yes or no.",
        "structural_materials": "List visible structural materials on site in one short sentence.",
        "crane_or_equipment": "Is heavy construction equipment such as a crane visible? Answer only yes or no.",
    }

    ARCHITECTURAL_REFERENCE_QUESTIONS = {
        "total_floors": "How many floors does this completed architectural design show? Count every level including ground floor. Answer with a number only.",
        "total_windows": "Count the total window openings visible on this architectural design. Answer with a number only.",
        "total_balconies": "Count the total balconies visible on this architectural design. Answer with a number only.",
        "building_type": "What type of building is this? Choose one: [residential apartment, villa, commercial, mixed-use, other]. Answer with the exact phrase only.",
        "facade_material": "What is the primary exterior facade finish? Answer in one short phrase.",
        "roof_finish": "Describe the finished roof appearance in one short phrase.",
    }

    ARCHITECTURAL_SITE_QUESTIONS = {
        "windows_now": "Count window openings currently visible on the building. Answer with a number only.",
        "balconies_now": "Count balconies currently visible on the building. Answer with a number only.",
        "wall_status": "What is the main exterior wall finish visible? Choose only one: [bare concrete only, red bricks or blockwork started, bricks mostly complete, walls plastered, final cladding or paint applied]. Answer with the exact phrase only.",
        "roof_status": "What is the current roof finish status? Choose only one: [no roof yet, roof slab cast but open, waterproofing done, roof fully covered and finished]. Answer with the exact phrase only.",
        "windows_glass": "Are window frames or glass installed in most openings? Answer only yes or no.",
        "railings_done": "Are balcony railings installed on most balconies? Answer only yes or no.",
        "landscaping": "Is there landscaping, paving, fencing, or plants around the building? Answer only yes or no.",
        "facade_color": "Describe the current exterior color or surface appearance in one short phrase.",
        "entrance_finished": "Does the main entrance area appear finished? Answer only yes or no.",
    }

    STRUCTURAL_REFERENCE_PROMPT = (
        "Describe this structural building design. Include floors, frame type, columns, "
        "floor slabs, roof structure, and structural layout. Write 2-4 sentences for a structural engineer."
    )
    STRUCTURAL_SITE_PROMPT = (
        "Write a structural construction observation for this site photo. Describe floors built, "
        "columns and frame, floor slabs, roof slab status, scaffolding, workers, structural materials, "
        "and work in progress. Write 3-5 sentences for a structural engineer."
    )
    STRUCTURAL_COMPARISON_PROMPT = (
        "Compare this construction site to the target structural design. Describe structural work "
        "completed, remaining elements, and next structural steps. Write 3-4 sentences."
    )
    ARCHITECTURAL_REFERENCE_PROMPT = (
        "Describe this completed architectural design. Include floors, style, facade materials, "
        "windows, balconies, roof appearance, and finished aesthetic. Write 2-4 sentences for an architect."
    )
    ARCHITECTURAL_SITE_PROMPT = (
        "Write an architectural construction observation for this site photo. Describe wall finishes, "
        "brickwork or cladding, windows, balconies, glass, railings, roof finish, entrance, landscaping, "
        "and overall appearance. Write 3-5 sentences for an architect."
    )
    ARCHITECTURAL_COMPARISON_PROMPT = (
        "Compare this construction site to the target architectural design. Describe finishing work "
        "completed, what differs from the final design, and next architectural steps. Write 3-4 sentences."
    )
    COMPLETION_ESTIMATE_QUESTION = (
        "You are estimating practical project completion for a construction dashboard. "
        "Use the site photo together with this analysis:\n"
        "- Overall progress: {overall}%\n"
        "- Structural progress: {struct_pct}% ({struct_phase})\n"
        "- Architectural progress: {arch_pct}% ({arch_phase})\n"
        "- Remaining overall work: {remaining}%\n"
        "- Built floors: {built_floors}\n"
        "- Floor slabs cast: {floor_slabs}\n"
        "- Roof slab status: {roof_slab_status}\n"
        "- Wall finish status: {wall_status}\n"
        "- Roof finish status: {roof_status}\n"
        "- Workers visible: {workers_visible}\n"
        "- Scaffolding visible: {scaffolding}\n"
        "- Structural note: {struct_note}\n"
        "- Architectural note: {arch_note}\n"
        "How many calendar days until this building is practically complete? "
        "Answer with one number only (days)."
    )

    def __init__(
        self,
        client: MoondreamClient,
        progress: Optional[ProgressTracker] = None,
        *,
        reference_cache: Optional[ReferenceMetricsCache] = None,
        force_reference_scan: bool = False,
    ) -> None:
        self.client = client
        self.progress = progress or NullReportProgress()
        self.reference_cache = reference_cache or ReferenceMetricsCache(DEFAULT_REFERENCE_CACHE_DIR)
        self.force_reference_scan = force_reference_scan
        self._structural_ref_cache: Optional[Dict[str, Any]] = None
        self._architectural_ref_cache: Optional[Dict[str, Any]] = None

    def _mark_section_cached(self, section_id: str, title: str, cache_file: str) -> None:
        cache_name = Path(cache_file).name
        self.progress.section_start(section_id, f"{title} (cached)")
        self.progress.step_start(
            section_id,
            "cache_hit",
            f"Using saved metrics from {cache_name}",
        )
        self.progress.step_complete(section_id)
        self.progress.section_complete(section_id)

    @staticmethod
    def _count_empty_answers(raw: Dict[str, str]) -> int:
        return sum(1 for value in raw.values() if not str(value or "").strip())

    def _query_bundle(
        self,
        image_path: str,
        questions: Dict[str, str],
        label: str,
        *,
        section_id: str,
    ) -> Dict[str, str]:
        raw: Dict[str, str] = {}
        for key, question in questions.items():
            print(f"   ... {label}: {key}")
            self.progress.step_start(section_id, key)
            raw[key] = self.client.query(image_path, question)
            self.progress.step_complete(section_id)
        return raw

    def _validate_site_analysis(
        self,
        *,
        struct_site: Dict[str, Any],
        arch_site: Dict[str, Any],
        struct_comparison: str,
        arch_comparison: str,
    ) -> None:
        struct_empty = self._count_empty_answers(struct_site.get("raw_answers", {}))
        arch_empty = self._count_empty_answers(arch_site.get("raw_answers", {}))
        caption_empty = sum(
            1
            for text in (
                struct_site.get("description", ""),
                arch_site.get("description", ""),
                struct_comparison,
                arch_comparison,
            )
            if not str(text or "").strip()
        )
        total_calls = (
            len(self.STRUCTURAL_SITE_QUESTIONS)
            + len(self.ARCHITECTURAL_SITE_QUESTIONS)
            + 4
        )
        failed_calls = struct_empty + arch_empty + caption_empty
        success_rate = 1.0 - (failed_calls / total_calls)
        print(
            f"[AI] Site analysis quality: {success_rate * 100:.0f}% "
            f"({total_calls - failed_calls}/{total_calls} calls succeeded)"
        )
        if success_rate < MIN_SITE_ANALYSIS_SUCCESS_RATE:
            raise AnalysisQualityError(
                "Site analysis is unreliable because too many Moondream API calls failed "
                f"({failed_calls}/{total_calls} empty). Progress percentages would be wrong "
                "(for example architectural 0% with structural 85%). "
                "Fix Pi internet/DNS, verify `ping api.moondream.ai`, then re-run."
            )

    def analyze_structural_reference(self, path: str) -> Dict[str, Any]:
        if self._structural_ref_cache is not None:
            return self._structural_ref_cache

        if not self.force_reference_scan:
            cached = self.reference_cache.load(path, "structural_reference")
            if cached is not None:
                cache_file = cached.pop("_cache_file", "")
                print(f"[CACHE] Structural reference loaded from {cache_file or 'cache'}")
                self._mark_section_cached(
                    "struct_ref",
                    "Structural Reference Analysis",
                    cache_file or os.path.basename(path),
                )
                self._structural_ref_cache = cached
                return cached

        print("[AI] Part 1 - Structural reference analysis")
        self.progress.section_start("struct_ref", "Structural Reference Analysis")
        raw = self._query_bundle(
            path, self.STRUCTURAL_REFERENCE_QUESTIONS, "struct ref", section_id="struct_ref",
        )
        self.progress.step_start("struct_ref", "description", "Generating structural design summary")
        description = self.client.caption(path, self.STRUCTURAL_REFERENCE_PROMPT, length="long")
        self.progress.step_complete("struct_ref")
        result = {
            "reference_image": os.path.basename(path),
            "reference_path": path,
            "total_floors": parse_int_answer(raw["total_floors"], 1),
            "structural_system": raw.get("structural_system", "unknown"),
            "column_count": parse_int_answer(raw.get("column_count", ""), 0),
            "floor_slabs": parse_int_answer(raw.get("floor_slabs", ""), 0),
            "roof_structure": raw.get("roof_structure", "unknown"),
            "description": description,
            "raw_answers": raw,
        }
        self._structural_ref_cache = result
        self.progress.section_complete("struct_ref")
        self.reference_cache.save(path, "structural_reference", result)
        return result

    def analyze_architectural_reference(self, path: str) -> Dict[str, Any]:
        if self._architectural_ref_cache is not None:
            return self._architectural_ref_cache

        if not self.force_reference_scan:
            cached = self.reference_cache.load(path, "architectural_reference")
            if cached is not None:
                cache_file = cached.pop("_cache_file", "")
                print(f"[CACHE] Architectural reference loaded from {cache_file or 'cache'}")
                self._mark_section_cached(
                    "arch_ref",
                    "Architectural Reference Analysis",
                    cache_file or os.path.basename(path),
                )
                self._architectural_ref_cache = cached
                return cached

        print("[AI] Part 2 - Architectural reference analysis")
        self.progress.section_start("arch_ref", "Architectural Reference Analysis")
        raw = self._query_bundle(
            path, self.ARCHITECTURAL_REFERENCE_QUESTIONS, "arch ref", section_id="arch_ref",
        )
        self.progress.step_start("arch_ref", "description", "Generating architectural design summary")
        description = self.client.caption(path, self.ARCHITECTURAL_REFERENCE_PROMPT, length="long")
        self.progress.step_complete("arch_ref")
        result = {
            "reference_image": os.path.basename(path),
            "reference_path": path,
            "total_floors": parse_int_answer(raw["total_floors"], 1),
            "total_windows": parse_int_answer(raw["total_windows"], 0),
            "total_balconies": parse_int_answer(raw["total_balconies"], 0),
            "building_type": raw.get("building_type", "unknown"),
            "facade_material": raw.get("facade_material", "unknown"),
            "roof_finish": raw.get("roof_finish", "unknown"),
            "description": description,
            "raw_answers": raw,
        }
        self._architectural_ref_cache = result
        self.progress.section_complete("arch_ref")
        self.reference_cache.save(path, "architectural_reference", result)
        return result

    def analyze_structural_site(self, path: str) -> Dict[str, Any]:
        print("[AI] Part 1 - Structural site analysis")
        self.progress.section_start("struct_site", "Site Photo - Structural Analysis")
        raw = self._query_bundle(
            path, self.STRUCTURAL_SITE_QUESTIONS, "struct site", section_id="struct_site",
        )
        self.progress.step_start("struct_site", "description", "Writing structural site observation")
        description = self.client.caption(path, self.STRUCTURAL_SITE_PROMPT, length="long")
        self.progress.step_complete("struct_site")
        result = {
            "built_floors": parse_int_answer(raw["built_floors"], 0),
            "visible_columns": parse_yes_no(raw.get("visible_columns", "")),
            "floor_slabs_cast": parse_int_answer(raw.get("floor_slabs_cast", ""), 0),
            "roof_slab_status": (raw.get("roof_slab_status") or "").lower(),
            "scaffolding": parse_yes_no(raw.get("scaffolding", "")),
            "workers_visible": parse_yes_no(raw.get("workers_visible", "")),
            "structural_materials": raw.get("structural_materials", ""),
            "crane_or_equipment": parse_yes_no(raw.get("crane_or_equipment", "")),
            "description": description,
            "raw_answers": raw,
        }
        self.progress.section_complete("struct_site")
        return result

    def analyze_architectural_site(self, path: str) -> Dict[str, Any]:
        print("[AI] Part 2 - Architectural site analysis")
        self.progress.section_start("arch_site", "Site Photo - Architectural Analysis")
        raw = self._query_bundle(
            path, self.ARCHITECTURAL_SITE_QUESTIONS, "arch site", section_id="arch_site",
        )
        self.progress.step_start("arch_site", "description", "Writing architectural site observation")
        description = self.client.caption(path, self.ARCHITECTURAL_SITE_PROMPT, length="long")
        self.progress.step_complete("arch_site")
        result = {
            "windows_now": parse_int_answer(raw["windows_now"], 0),
            "balconies_now": parse_int_answer(raw["balconies_now"], 0),
            "wall_status": (raw.get("wall_status") or "").lower(),
            "roof_status": (raw.get("roof_status") or "").lower(),
            "windows_glass": parse_yes_no(raw.get("windows_glass", "")),
            "railings_done": parse_yes_no(raw.get("railings_done", "")),
            "landscaping": parse_yes_no(raw.get("landscaping", "")),
            "facade_color": raw.get("facade_color", ""),
            "entrance_finished": parse_yes_no(raw.get("entrance_finished", "")),
            "description": description,
            "raw_answers": raw,
        }
        self.progress.section_complete("arch_site")
        return result

    @staticmethod
    def _structural_roof_score(status: str) -> float:
        if "cast but open" in status or "roof slab cast" in status:
            return 15.0
        if "complete" in status:
            return 25.0
        return 0.0

    @staticmethod
    def _arch_wall_score(status: str) -> float:
        if "red bricks" in status or "blockwork" in status:
            return 12.0
        if "mostly complete" in status:
            return 18.0
        if "plastered" in status:
            return 22.0
        if "cladding" in status or "paint" in status:
            return 25.0
        if "bare concrete" in status:
            return 5.0
        return 0.0

    @staticmethod
    def _arch_roof_score(status: str) -> float:
        if "slab cast" in status:
            return 6.0
        if "waterproofing" in status:
            return 10.0
        if "fully covered" in status:
            return 15.0
        return 0.0

    @staticmethod
    def structural_phase(site: Dict[str, Any], progress: float) -> str:
        if progress >= 95:
            return "Structure Complete"
        if "complete" in site.get("roof_slab_status", ""):
            return "Roof Slab"
        if site.get("floor_slabs_cast", 0) >= site.get("built_floors", 0) > 0:
            return "Floor Slabs"
        if site.get("visible_columns"):
            return "Frame"
        if site.get("built_floors", 0) >= 1:
            return "Superstructure"
        return "Foundation"

    @staticmethod
    def architectural_phase(site: Dict[str, Any], progress: float) -> str:
        wall = site.get("wall_status", "")
        if progress >= 95:
            return "Complete"
        if "cladding" in wall or "paint" in wall:
            return "Finishing"
        if site.get("windows_glass"):
            return "Windows"
        if "fully covered" in site.get("roof_status", ""):
            return "Roof"
        if "red bricks" in wall or "blockwork" in wall or "mostly complete" in wall:
            return "Brick"
        if "plastered" in wall:
            return "Plaster"
        if site.get("landscaping"):
            return "Landscaping"
        return "Envelope"

    def calculate_structural_progress(self, ref: Dict[str, Any], site: Dict[str, Any]) -> Tuple[float, str, Dict[str, float]]:
        total_floors = max(ref.get("total_floors", 1), 1)
        built = site.get("built_floors", 0)
        slabs = site.get("floor_slabs_cast", 0)
        breakdown = {
            "floors_built": round(min(built / total_floors, 1.0) * 45.0, 1),
            "floor_slabs": round(min(slabs / total_floors, 1.0) * 20.0, 1),
            "columns_frame": 15.0 if site.get("visible_columns") else 0.0,
            "roof_slab": self._structural_roof_score(site.get("roof_slab_status", "")),
            "scaffolding_clear": 10.0 if not site.get("scaffolding") and built > 0 else 0.0,
            "site_activity": 10.0 if site.get("crane_or_equipment") or site.get("workers_visible") else 5.0,
        }
        progress = min(round(sum(breakdown.values()), 1), 100.0)
        return progress, self.structural_phase(site, progress), breakdown

    def calculate_architectural_progress(self, ref: Dict[str, Any], site: Dict[str, Any]) -> Tuple[float, str, Dict[str, float]]:
        total_windows = max(ref.get("total_windows", 0), 0)
        total_balconies = max(ref.get("total_balconies", 0), 0)
        breakdown = {
            "exterior_walls": self._arch_wall_score(site.get("wall_status", "")),
            "roof_finish": self._arch_roof_score(site.get("roof_status", "")),
            "windows": round(min(site.get("windows_now", 0) / total_windows, 1.0) * 15.0, 1) if total_windows else 0.0,
            "balconies": round(min(site.get("balconies_now", 0) / total_balconies, 1.0) * 10.0, 1) if total_balconies else 0.0,
            "glass": 15.0 if site.get("windows_glass") else 0.0,
            "railings": 10.0 if site.get("railings_done") else 0.0,
            "entrance": 10.0 if site.get("entrance_finished") else 0.0,
            "landscaping": 15.0 if site.get("landscaping") else 0.0,
        }
        progress = min(round(sum(breakdown.values()), 1), 100.0)
        return progress, self.architectural_phase(site, progress), breakdown

    @staticmethod
    def combined_phase(arch_phase: str, struct_phase: str, overall: float) -> str:
        if overall >= 95:
            return "Complete"
        if arch_phase in {"Brick", "Plaster", "Windows", "Roof", "Finishing", "Landscaping"}:
            return arch_phase
        if overall < 35:
            return struct_phase if struct_phase != "Structure Complete" else "Structural"
        return arch_phase

    @staticmethod
    def _truncate_text(text: str, max_len: int = 220) -> str:
        cleaned = " ".join((text or "").split())
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[: max_len - 3].rstrip() + "..."

    def estimate_completion(
        self,
        site_path: str,
        *,
        overall: float,
        struct_pct: float,
        arch_pct: float,
        struct_phase: str,
        arch_phase: str,
        remaining_percentage: float,
        struct_site: Dict[str, Any],
        arch_site: Dict[str, Any],
        struct_comparison: str,
        arch_comparison: str,
        reference: datetime,
    ) -> Dict[str, Any]:
        struct_remaining = round(100.0 - struct_pct, 1)
        arch_remaining = round(100.0 - arch_pct, 1)
        metric_days = metric_completion_days(
            remaining_percentage,
            struct_remaining,
            arch_remaining,
        )

        self.progress.section_start("completion", "Completion Estimate")
        self.progress.step_start("completion", "ai_completion_estimate")
        question = self.COMPLETION_ESTIMATE_QUESTION.format(
            overall=overall,
            struct_pct=struct_pct,
            arch_pct=arch_pct,
            struct_phase=struct_phase,
            arch_phase=arch_phase,
            remaining=remaining_percentage,
            built_floors=struct_site.get("built_floors", 0),
            floor_slabs=struct_site.get("floor_slabs_cast", 0),
            roof_slab_status=struct_site.get("roof_slab_status", "unknown"),
            wall_status=arch_site.get("wall_status", "unknown"),
            roof_status=arch_site.get("roof_status", "unknown"),
            workers_visible="yes" if struct_site.get("workers_visible") else "no",
            scaffolding="yes" if struct_site.get("scaffolding") else "no",
            struct_note=self._truncate_text(
                struct_site.get("description", "") or struct_comparison
            ),
            arch_note=self._truncate_text(
                arch_site.get("description", "") or arch_comparison
            ),
        )
        ai_answer = self.client.query(site_path, question)
        ai_days = parse_days_answer(ai_answer)
        days = blend_completion_days(ai_days, metric_days, remaining_percentage)

        if ai_days <= 0 and metric_days > 0:
            print(
                f"[WARN] Moondream completion estimate unusable ({ai_answer!r}); "
                f"using metric fallback ({metric_days} days)"
            )
        else:
            print(
                f"[AI] Completion estimate: {ai_days} days (AI) + {metric_days} days "
                f"(metrics) -> {days} days blended"
            )

        self.progress.step_complete("completion")
        self.progress.section_complete("completion")
        return format_completion_estimate(
            days,
            reference,
            ai_days=ai_days,
            metric_days=metric_days,
        )

    def run_full_analysis(
        self,
        structural_ref_path: str,
        architectural_ref_path: str,
        site_path: str,
    ) -> Dict[str, Any]:
        struct_ref = self.analyze_structural_reference(structural_ref_path)
        arch_ref = self.analyze_architectural_reference(architectural_ref_path)
        struct_site = self.analyze_structural_site(site_path)
        arch_site = self.analyze_architectural_site(site_path)

        self.progress.section_start("comparison", "Design Comparison")
        self.progress.step_start("comparison", "structural_comparison")
        struct_comparison = self.client.caption(site_path, self.STRUCTURAL_COMPARISON_PROMPT, length="long")
        self.progress.step_complete("comparison")
        self.progress.step_start("comparison", "architectural_comparison")
        arch_comparison = self.client.caption(site_path, self.ARCHITECTURAL_COMPARISON_PROMPT, length="long")
        self.progress.step_complete("comparison")
        self.progress.section_complete("comparison")
        self._validate_site_analysis(
            struct_site=struct_site,
            arch_site=arch_site,
            struct_comparison=struct_comparison,
            arch_comparison=arch_comparison,
        )

        self.progress.section_start("calculate", "Progress Calculation")
        self.progress.step_start("calculate", "structural_progress")
        struct_pct, struct_phase, struct_breakdown = self.calculate_structural_progress(struct_ref, struct_site)
        self.progress.step_complete("calculate")
        self.progress.step_start("calculate", "architectural_progress")
        arch_pct, arch_phase, arch_breakdown = self.calculate_architectural_progress(arch_ref, arch_site)
        self.progress.step_complete("calculate")
        self.progress.step_start("calculate", "overall_phase")
        overall = round((struct_pct * 0.45) + (arch_pct * 0.55), 1)
        display_phase = self.combined_phase(arch_phase, struct_phase, overall)
        self.progress.step_complete("calculate")
        self.progress.section_complete("calculate")

        if overall < 25:
            detailed = "Structural framework"
        elif overall < 50:
            detailed = "Blockwork and brickwork"
        elif overall < 75:
            detailed = "External finishing"
        else:
            detailed = "Final handover stage"

        site_condition_summary = (
            f"The site is {overall}% complete in the {display_phase} phase with "
            f"structural work at {struct_pct}% and architectural work at {arch_pct}%."
        )

        now = datetime.now()
        remaining_percentage = round(100.0 - overall, 1)
        completion_estimate = self.estimate_completion(
            site_path,
            overall=overall,
            struct_pct=struct_pct,
            arch_pct=arch_pct,
            struct_phase=struct_phase,
            arch_phase=arch_phase,
            remaining_percentage=remaining_percentage,
            struct_site=struct_site,
            arch_site=arch_site,
            struct_comparison=struct_comparison,
            arch_comparison=arch_comparison,
            reference=now,
        )
        return {
            "project": "Construction Progress Analysis",
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp_iso": now.isoformat(),
            "site_image": os.path.basename(site_path),
            "site_path": site_path,
            "structural_reference_image": os.path.basename(structural_ref_path),
            "architectural_reference_image": os.path.basename(architectural_ref_path),
            "structural_reference_path": structural_ref_path,
            "architectural_reference_path": architectural_ref_path,
            "structural": {
                "reference_metrics": struct_ref,
                "site_metrics": struct_site,
                "progress_percentage": struct_pct,
                "current_phase": struct_phase,
                "remaining_percentage": round(100.0 - struct_pct, 1),
                "progress_breakdown": struct_breakdown,
                "description": struct_site.get("description", ""),
                "comparison_summary": struct_comparison,
                "reference_description": struct_ref.get("description", ""),
            },
            "architectural": {
                "reference_metrics": arch_ref,
                "site_metrics": arch_site,
                "progress_percentage": arch_pct,
                "current_phase": arch_phase,
                "remaining_percentage": round(100.0 - arch_pct, 1),
                "progress_breakdown": arch_breakdown,
                "description": arch_site.get("description", ""),
                "comparison_summary": arch_comparison,
                "reference_description": arch_ref.get("description", ""),
            },
            "progress_percentage": overall,
            "structural_progress_percentage": struct_pct,
            "architectural_progress_percentage": arch_pct,
            "current_phase": display_phase,
            "detailed_phase": detailed,
            "remaining_percentage": remaining_percentage,
            "description": arch_site.get("description", ""),
            "comparison_summary": arch_comparison,
            "design_description": arch_ref.get("description", ""),
            "site_condition_summary": site_condition_summary,
            **completion_estimate,
        }


class PDFReportBuilder:
    BRAND = "Construct Eye"
    NAVY = (15, 42, 68)
    TEAL = (14, 116, 144)
    AMBER = (217, 119, 6)
    BG_LIGHT = (248, 250, 252)
    BORDER = (226, 232, 240)
    TEXT_DARK = (30, 41, 59)
    TEXT_MUTED = (100, 116, 139)
    PROGRESS_FILL = (34, 197, 94)
    MARGIN = 15.0
    COVER_LOGO_HEIGHT_MM = 46.0
    INNER_LOGO_HEIGHT_MM = 16.0
    SECTION_GAP_MM = 6.0
    METRIC_MIN_CARD_H_MM = 20.0

    def __init__(self, output_dir: str, *, logo_path: str = DEFAULT_PDF_LOGO) -> None:
        if not FPDF_AVAILABLE:
            raise RuntimeError("fpdf2 is not installed. Run: pip install fpdf2")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logo_path = logo_path or DEFAULT_PDF_LOGO
        self._logo_asset: Optional[Path] = None

    @staticmethod
    def _safe(text: str) -> str:
        return (
            (text or "")
            .replace("\u2014", "-").replace("\u2013", "-")
            .replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .encode("latin-1", errors="replace").decode("latin-1")
        )

    def _content_width(self, pdf: FPDF) -> float:
        return pdf.w - pdf.l_margin - pdf.r_margin

    def _remaining_height(self, pdf: FPDF) -> float:
        return pdf.h - pdf.b_margin - pdf.get_y()

    def _usable_page_height(self, pdf: FPDF) -> float:
        return pdf.h - pdf.t_margin - pdf.b_margin

    def _is_near_page_top(self, pdf: FPDF, tolerance: float = 2.0) -> bool:
        return pdf.get_y() <= pdf.t_margin + tolerance

    def _ensure_space(self, pdf: FPDF, height: float) -> None:
        if height > self._remaining_height(pdf):
            pdf.add_page()

    def _ensure_block_space(self, pdf: FPDF, height: float) -> None:
        """Start a new page when a whole section block cannot fit on the current page."""
        if height <= 0:
            return
        if height <= self._remaining_height(pdf):
            return
        if self._is_near_page_top(pdf) and height > self._usable_page_height(pdf):
            return
        pdf.add_page()

    def _start_new_content_page(self, pdf: FPDF) -> None:
        """Advance to a new page only when the current page already has content on it."""
        if not self._is_near_page_top(pdf, tolerance=12.0):
            pdf.add_page()

    def _ensure_text_block_together(
        self,
        pdf: FPDF,
        text: str,
        width: float,
        line_height: float,
        *,
        padding: float = 10.0,
        min_tail_lines: int = 2,
    ) -> None:
        """Keep paragraphs together and avoid tiny orphaned tails alone on a page."""
        if not str(text or "").strip():
            return
        line_count = self._measure_multicell_lines(pdf, text, width, line_height)
        if line_count == 0:
            return
        block_h = line_count * line_height + padding
        remaining = self._remaining_height(pdf)
        usable = self._usable_page_height(pdf)

        if block_h <= remaining:
            return

        if block_h <= usable:
            pdf.add_page()
            return

        lines_fit = max(0, int((remaining - padding) / line_height))
        tail_lines = line_count - lines_fit
        if lines_fit > 0 and 0 < tail_lines <= min_tail_lines:
            pdf.add_page()

    def _wrap_text_lines(
        self,
        pdf: FPDF,
        text: str,
        max_width: float,
        font_size: int,
        *,
        style: str = "",
    ) -> List[str]:
        pdf.set_font("Helvetica", style, font_size)
        words = self._safe(str(text or "")).split()
        if not words:
            return [""]
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdf.get_string_width(candidate) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def _measure_multicell_lines(
        self,
        pdf: FPDF,
        text: str,
        width: float,
        line_height: float,
        *,
        font_size: int = 10,
        style: str = "",
    ) -> int:
        """Match fpdf multi_cell wrapping, including explicit newlines."""
        if not str(text or "").strip():
            return 0
        pdf.set_font("Helvetica", style, font_size)
        safe = self._safe(text)
        try:
            lines = pdf.multi_cell(
                width,
                line_height,
                safe,
                dry_run=True,
                output="LINES",
            )
            return len(lines)
        except (TypeError, ValueError):
            total = 0
            for block in safe.split("\n"):
                if not block.strip():
                    total += 1
                else:
                    total += len(
                        self._wrap_text_lines(pdf, block, width, font_size, style=style)
                    )
            return total

    def _estimate_heading_height(self, subtitle: str = "") -> float:
        height = 12.0 + self.SECTION_GAP_MM
        if subtitle:
            height += 6.0
        return height

    def _estimate_body_paragraph_height(self, pdf: FPDF, text: str) -> float:
        if not text.strip():
            return 0.0
        line_count = self._measure_multicell_lines(
            pdf,
            text,
            self._content_width(pdf),
            5.5,
        )
        return line_count * 5.5 + 6.0

    def _estimate_callout_height(self, pdf: FPDF, text: str) -> float:
        if not text.strip():
            return 0.0
        line_count = self._measure_multicell_lines(
            pdf,
            text,
            self._content_width(pdf) - 10,
            5.5,
        )
        return max(18.0, line_count * 5.5 + 8.0) + 4.0

    def _estimate_metric_grid_height(self, pdf: FPDF, metrics: List[Tuple[str, str]]) -> float:
        if not metrics:
            return 0.0
        width = self._content_width(pdf)
        gap = 4.0
        col_w = (width - gap) / 2
        inner_w = col_w - 8.0
        row_heights: List[float] = []
        for index, (_label, value) in enumerate(metrics):
            value_lines = self._wrap_text_lines(pdf, str(value), inner_w, 10, style="B")
            card_h = max(self.METRIC_MIN_CARD_H_MM, 8.0 + len(value_lines) * 5.0 + 4.0)
            row = index // 2
            if row >= len(row_heights):
                row_heights.append(card_h)
            else:
                row_heights[row] = max(row_heights[row], card_h)
        return sum(row_heights) + max(0, len(row_heights) - 1) * gap + 4.0

    def _estimate_progress_bars_height(self, breakdown: Dict[str, float]) -> float:
        if not breakdown:
            return 0.0
        return len(breakdown) * 9.0 + 4.0

    def _available_draw_height(self, pdf: FPDF, *, reserved_bottom: float = 18.0) -> float:
        """Remaining vertical space on the current page for a large image + caption."""
        return max(60.0, pdf.h - pdf.b_margin - pdf.get_y() - reserved_bottom)

    def _estimate_framed_image_height(
        self,
        path: str,
        *,
        max_width: float,
        max_height: float,
    ) -> float:
        if not path or not os.path.exists(path):
            return 0.0
        try:
            with Image.open(path) as img:
                iw, ih = img.size
            ratio = min(max_width / iw, max_height / ih)
            return ih * ratio + 20.0
        except Exception:
            return max_height + 20.0

    def _line_cell(self, pdf: FPDF, width: float, height: float, text: str, style: str = "") -> None:
        if style:
            pdf.set_font("Helvetica", style, pdf.font_size)
        if XPos is not None and YPos is not None:
            pdf.cell(width, height, self._safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.cell(width, height, self._safe(text), ln=1)

    def _prepare_logo_asset(self, logo_path: str) -> Optional[Path]:
        if not logo_path or not os.path.exists(logo_path):
            return None
        try:
            with Image.open(logo_path) as img:
                if img.mode in ("RGBA", "LA", "P"):
                    rgba = img.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (15, 42, 68, 255))
                    background.alpha_composite(rgba)
                    out = background.convert("RGB")
                else:
                    out = img.convert("RGB")
                dest = self.output_dir / "_tmp_construct_eye_logo.png"
                out.save(dest, format="PNG")
            return dest
        except Exception as exc:
            print(f"[WARN] Could not prepare PDF logo: {exc}")
            return None

    def _logo_dimensions(self, max_height: float) -> Tuple[float, float]:
        if self._logo_asset is None or not self._logo_asset.exists():
            return 0.0, 0.0
        with Image.open(self._logo_asset) as img:
            iw, ih = img.size
        if ih <= 0:
            return 0.0, 0.0
        ratio = max_height / float(ih)
        return iw * ratio, max_height

    def _embed_logo(
        self,
        pdf: FPDF,
        *,
        max_height: float,
        x: Optional[float] = None,
        y: Optional[float] = None,
        align: str = "left",
        padding: float = 10.0,
    ) -> None:
        if self._logo_asset is None:
            return
        disp_w, disp_h = self._logo_dimensions(max_height)
        if disp_w <= 0 or disp_h <= 0:
            return
        pos_x = padding if x is None else x
        if align == "right":
            pos_x = pdf.w - padding - disp_w
        pos_y = pdf.get_y() if y is None else y
        pdf.image(str(self._logo_asset), x=pos_x, y=pos_y, w=disp_w, h=disp_h)

    def _draw_cover_page(self, pdf: FPDF) -> None:
        cover_h = 60.0
        pdf.set_fill_color(*self.NAVY)
        pdf.rect(0, 0, pdf.w, cover_h, style="F")
        pdf.set_fill_color(*self.TEAL)
        pdf.rect(0, cover_h, pdf.w, PDF_HEADER_ACCENT_MM, style="F")
        self._embed_logo(
            pdf,
            max_height=self.COVER_LOGO_HEIGHT_MM,
            x=self.MARGIN,
            y=8.0,
            align="left",
        )
        title_x = self.MARGIN + max(self._logo_dimensions(self.COVER_LOGO_HEIGHT_MM)[0], 55.0) + 8.0
        pdf.set_xy(title_x, 20.0)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 9, self._safe("Construction Progress Report"))
        pdf.set_xy(title_x, 32.0)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(210, 225, 240)
        pdf.cell(0, 6, self._safe(f"Project {PROJECT_ID}  |  AI Site Analysis"))
        pdf.set_y(cover_h + PDF_HEADER_ACCENT_MM + 6.0)
        pdf.set_text_color(*self.TEXT_DARK)

    def _draw_meta_table(self, pdf: FPDF, rows: List[Tuple[str, str]]) -> None:
        width = self._content_width(pdf)
        col_label = 48.0
        col_value = width - col_label - 6.0
        value_x = self.MARGIN + col_label + 3
        line_h = 5.2
        pad_v = 3.0
        min_row_h = 10.0
        font_size = 9

        row_specs: List[Tuple[str, str, float]] = []
        for label, value in rows:
            line_count = max(
                1,
                self._measure_multicell_lines(
                    pdf,
                    str(value),
                    col_value,
                    line_h,
                    font_size=font_size,
                    style="",
                ),
            )
            row_h = max(min_row_h, pad_v * 2 + line_count * line_h + 0.5)
            row_specs.append((label, str(value), row_h))

        y = pdf.get_y()
        for index, (label, value, row_h) in enumerate(row_specs):
            pdf.set_draw_color(*self.BORDER)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(self.MARGIN, y, width, row_h, style="DF")
            if index > 0:
                pdf.set_draw_color(*self.BORDER)
                pdf.line(self.MARGIN, y, self.MARGIN + width, y)

            pdf.set_xy(self.MARGIN + 3, y + pad_v)
            pdf.set_font("Helvetica", "B", font_size)
            pdf.set_text_color(*self.TEXT_MUTED)
            if XPos is not None and YPos is not None:
                pdf.cell(
                    col_label,
                    line_h,
                    self._safe(label),
                    new_x=XPos.RIGHT,
                    new_y=YPos.TOP,
                )
            else:
                pdf.cell(col_label, line_h, self._safe(label))

            pdf.set_xy(value_x, y + pad_v)
            pdf.set_font("Helvetica", "", font_size)
            pdf.set_text_color(*self.TEXT_DARK)
            if XPos is not None and YPos is not None:
                pdf.multi_cell(
                    col_value,
                    line_h,
                    self._safe(value),
                    new_x=XPos.RIGHT,
                    new_y=YPos.TOP,
                )
            else:
                pdf.multi_cell(col_value, line_h, self._safe(value))

            y += row_h
            pdf.set_xy(self.MARGIN, y)

        pdf.set_y(y + 4)

    def _draw_progress_cards(self, pdf: FPDF, report: Dict[str, Any]) -> None:
        width = self._content_width(pdf)
        gap = 4.0
        card_w = (width - 2 * gap) / 3
        card_h = 28.0
        start_y = pdf.get_y()
        cards = [
            ("Overall", report["progress_percentage"], self.TEAL),
            ("Structural", report["structural_progress_percentage"], self.NAVY),
            ("Architectural", report["architectural_progress_percentage"], self.AMBER),
        ]
        for index, (label, pct, color) in enumerate(cards):
            x = self.MARGIN + index * (card_w + gap)
            pdf.set_fill_color(*self.BG_LIGHT)
            pdf.set_draw_color(*self.BORDER)
            pdf.rect(x, start_y, card_w, card_h, style="DF")
            pdf.set_xy(x + 4, start_y + 4)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*self.TEXT_MUTED)
            pdf.cell(card_w - 8, 5, self._safe(label.upper()))
            pdf.set_xy(x + 4, start_y + 10)
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(*color)
            pdf.cell(card_w - 8, 10, self._safe(f"{pct}%"))
            bar_y = start_y + card_h - 8
            bar_w = card_w - 8
            pdf.set_fill_color(*self.BORDER)
            pdf.rect(x + 4, bar_y, bar_w, 4, style="F")
            pdf.set_fill_color(*color)
            pdf.rect(x + 4, bar_y, bar_w * min(float(pct), 100.0) / 100.0, 4, style="F")
        pdf.set_y(start_y + card_h + 6)
        pdf.set_text_color(*self.TEXT_DARK)

    def _section_heading(
        self,
        pdf: FPDF,
        title: str,
        subtitle: str = "",
        *,
        ensure_space: bool = False,
    ) -> None:
        block_h = self._estimate_heading_height(subtitle)
        if ensure_space:
            self._ensure_block_space(pdf, block_h)
        y = pdf.get_y()
        pdf.set_fill_color(*self.TEAL)
        pdf.rect(self.MARGIN, y, 3, 10, style="F")
        pdf.set_xy(self.MARGIN + 6, y)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*self.NAVY)
        self._line_cell(pdf, self._content_width(pdf) - 6, 7, title)
        if subtitle:
            pdf.set_x(self.MARGIN + 6)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.TEXT_MUTED)
            self._line_cell(pdf, self._content_width(pdf) - 6, 5, subtitle)
        pdf.ln(self.SECTION_GAP_MM)
        pdf.set_text_color(*self.TEXT_DARK)

    def _callout_box(self, pdf: FPDF, text: str, *, preflight: bool = True) -> None:
        if not text.strip():
            return
        width = self._content_width(pdf)
        text_w = width - 10.0
        line_h = 5.5
        pad_top = 4.0
        pad_bottom = 4.0
        line_count = self._measure_multicell_lines(pdf, text, text_w, line_h)
        box_h = max(18.0, line_count * line_h + pad_top + pad_bottom)
        if preflight:
            self._ensure_space(pdf, box_h + 4)
        y = pdf.get_y()
        pdf.set_fill_color(*self.BG_LIGHT)
        pdf.set_draw_color(*self.BORDER)
        pdf.rect(self.MARGIN, y, width, box_h, style="DF")
        pdf.set_fill_color(*self.TEAL)
        pdf.rect(self.MARGIN, y, 2.5, box_h, style="F")
        pdf.set_xy(self.MARGIN + 5, y + pad_top)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*self.TEXT_DARK)
        pdf.multi_cell(text_w, line_h, self._safe(text))
        pdf.set_y(max(pdf.get_y(), y + box_h) + 4)

    def _body_paragraph(
        self,
        pdf: FPDF,
        text: str,
        *,
        preflight: bool = True,
        keep_together: bool = True,
    ) -> None:
        if not text.strip():
            return
        width = self._content_width(pdf)
        if keep_together:
            self._ensure_text_block_together(pdf, text, width, 5.5)
        elif preflight:
            self._ensure_space(pdf, self._estimate_body_paragraph_height(pdf, text))
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*self.TEXT_DARK)
        start_y = pdf.get_y()
        pdf.set_x(self.MARGIN)
        pdf.multi_cell(self._content_width(pdf), 5.5, self._safe(text))
        if pdf.get_y() <= start_y:
            pdf.set_y(start_y + 5.5)
        pdf.ln(4)

    def _metric_grid(self, pdf: FPDF, metrics: List[Tuple[str, str]], *, preflight: bool = True) -> None:
        if not metrics:
            return
        width = self._content_width(pdf)
        gap = 4.0
        col_w = (width - gap) / 2
        inner_w = col_w - 8.0
        rows = (len(metrics) + 1) // 2
        row_heights: List[float] = []
        card_specs: List[Tuple[str, str, float]] = []
        for index, (label, value) in enumerate(metrics):
            value_lines = self._wrap_text_lines(pdf, str(value), inner_w, 10, style="B")
            card_h = max(self.METRIC_MIN_CARD_H_MM, 8.0 + len(value_lines) * 5.0 + 4.0)
            row = index // 2
            if row >= len(row_heights):
                row_heights.append(card_h)
            else:
                row_heights[row] = max(row_heights[row], card_h)
            card_specs.append((label, str(value), card_h))

        total_h = sum(row_heights) + max(0, len(row_heights) - 1) * gap + 4.0
        if preflight:
            self._ensure_space(pdf, total_h)

        start_y = pdf.get_y()
        row_offsets = [0.0]
        for row_h in row_heights[:-1]:
            row_offsets.append(row_offsets[-1] + row_h + gap)

        for index, (label, value, card_h) in enumerate(card_specs):
            col = index % 2
            row = index // 2
            x = self.MARGIN + col * (col_w + gap)
            y = start_y + row_offsets[row]
            row_h = row_heights[row]
            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(*self.BORDER)
            pdf.rect(x, y, col_w, row_h, style="DF")
            pdf.set_xy(x + 4, y + 3)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*self.TEXT_MUTED)
            pdf.cell(inner_w, 4, self._safe(label.upper()))
            pdf.set_xy(x + 4, y + 8)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*self.TEXT_DARK)
            pdf.multi_cell(inner_w, 5.0, self._safe(value))
        pdf.set_y(start_y + total_h)

    def _progress_breakdown_bars(
        self,
        pdf: FPDF,
        breakdown: Dict[str, float],
        *,
        preflight: bool = True,
    ) -> None:
        if not breakdown:
            return
        width = self._content_width(pdf)
        bar_max_w = width - 58
        row_h = 9.0
        if preflight:
            self._ensure_space(pdf, len(breakdown) * row_h + 4)
        for label, value in breakdown.items():
            y = pdf.get_y()
            pretty = label.replace("_", " ").title()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.TEXT_DARK)
            pdf.set_xy(self.MARGIN, y + 1)
            pdf.cell(42, 6, self._safe(pretty))
            pdf.set_fill_color(*self.BORDER)
            pdf.rect(self.MARGIN + 44, y + 2, bar_max_w, 4, style="F")
            pct = min(float(value), 100.0)
            pdf.set_fill_color(*self.PROGRESS_FILL)
            pdf.rect(self.MARGIN + 44, y + 2, bar_max_w * pct / 100.0, 4, style="F")
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*self.NAVY)
            pdf.set_xy(self.MARGIN + 44 + bar_max_w + 2, y + 1)
            pdf.cell(12, 6, self._safe(f"{value}%"), align="R")
            pdf.set_y(y + row_h)
        pdf.ln(2)

    def _prepare_image(self, path: str) -> Optional[Path]:
        if not path or not os.path.exists(path):
            return None
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                tmp = self.output_dir / f"_tmp_{Path(path).stem}.jpg"
                img.save(tmp, format="JPEG", quality=88)
            return tmp
        except Exception as exc:
            print(f"[WARN] Could not prepare image: {exc}")
            return None

    def _draw_framed_image(
        self,
        pdf: FPDF,
        path: str,
        *,
        caption: str,
        max_width: float,
        max_height: float = 95.0,
        preflight: bool = True,
    ) -> None:
        tmp = self._prepare_image(path)
        if tmp is None:
            return
        try:
            with Image.open(tmp) as img:
                iw, ih = img.size
            ratio = min(max_width / iw, max_height / ih)
            disp_w = iw * ratio
            disp_h = ih * ratio
            if preflight:
                self._ensure_space(pdf, disp_h + 16)
            x = (pdf.w - disp_w) / 2
            y = pdf.get_y()
            pdf.set_draw_color(*self.BORDER)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x - 2, y - 2, disp_w + 4, disp_h + 4, style="DF")
            pdf.image(str(tmp), x=x, y=y, w=disp_w, h=disp_h)
            pdf.set_y(y + disp_h + 3)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*self.TEXT_MUTED)
            pdf.set_x(self.MARGIN)
            pdf.multi_cell(self._content_width(pdf), 4, self._safe(caption), align="C")
            pdf.ln(4)
        finally:
            tmp.unlink(missing_ok=True)

    def _track_section(self, pdf: FPDF, title: str, track: Dict[str, Any], ref_path: str) -> None:
        part_subtitle = (
            f"Phase: {track['current_phase']}  |  "
            f"{track['progress_percentage']}% complete  |  "
            f"{track['remaining_percentage']}% remaining"
        )
        description_text = track.get("description", "")
        comparison_text = track.get("comparison_summary", "")
        heading_callout_block = (
            self._estimate_heading_height(part_subtitle)
            + self._estimate_callout_height(pdf, description_text)
        )
        self._ensure_block_space(pdf, heading_callout_block)
        self._section_heading(pdf, title, part_subtitle)
        self._callout_box(pdf, description_text, preflight=False)
        self._body_paragraph(pdf, comparison_text, preflight=False, keep_together=True)

        ref = track.get("reference_metrics", {})
        site = track.get("site_metrics", {})
        if "built_floors" in site:
            metrics = [
                ("Design floors", ref.get("total_floors", 0)),
                ("Built floors", site.get("built_floors", 0)),
                ("Floor slabs cast", site.get("floor_slabs_cast", 0)),
                ("Roof slab", site.get("roof_slab_status", "unknown")),
                ("Columns visible", "Yes" if site.get("visible_columns") else "No"),
                ("Scaffolding", "Yes" if site.get("scaffolding") else "No"),
                ("Structural materials", site.get("structural_materials", "N/A")),
                ("Site activity", "Active" if site.get("crane_or_equipment") else "Normal"),
            ]
        else:
            metrics = [
                ("Design windows", ref.get("total_windows", 0)),
                ("Current windows", site.get("windows_now", 0)),
                ("Design balconies", ref.get("total_balconies", 0)),
                ("Current balconies", site.get("balconies_now", 0)),
                ("Wall status", site.get("wall_status", "unknown")),
                ("Roof finish", site.get("roof_status", "unknown")),
                ("Glass installed", "Yes" if site.get("windows_glass") else "No"),
                ("Railings", "Yes" if site.get("railings_done") else "No"),
                ("Landscaping", "Yes" if site.get("landscaping") else "No"),
                ("Entrance finished", "Yes" if site.get("entrance_finished") else "No"),
            ]

        metrics_block = self._estimate_heading_height() + self._estimate_metric_grid_height(pdf, metrics)
        self._ensure_block_space(pdf, metrics_block)
        self._section_heading(pdf, "Key Metrics")
        self._metric_grid(pdf, metrics, preflight=False)

        breakdown = track.get("progress_breakdown", {})
        breakdown_block = self._estimate_heading_height() + self._estimate_progress_bars_height(breakdown)
        self._ensure_block_space(pdf, breakdown_block)
        self._section_heading(pdf, "Progress Breakdown")
        self._progress_breakdown_bars(pdf, breakdown, preflight=False)

        ref_desc = track.get("reference_description", "")
        ref_image_w = min(150.0, self._content_width(pdf))
        reference_block = (
            self._estimate_heading_height()
            + self._estimate_body_paragraph_height(pdf, ref_desc)
            + self._estimate_framed_image_height(
                ref_path,
                max_width=ref_image_w,
                max_height=80.0,
            )
        )
        self._ensure_block_space(pdf, reference_block)
        self._section_heading(pdf, "Reference Design")
        self._body_paragraph(pdf, ref_desc, preflight=False, keep_together=True)
        self._draw_framed_image(
            pdf,
            ref_path,
            caption=f"Reference: {Path(ref_path).name}",
            max_width=ref_image_w,
            max_height=80.0,
            preflight=False,
        )

    def _make_pdf(self) -> FPDF:
        builder = self

        class _ConstructEyePDF(FPDF):
            def header(self) -> None:
                if self.page_no() <= 1:
                    return
                self.set_fill_color(*builder.NAVY)
                self.rect(0, 0, self.w, PDF_HEADER_BAND_MM, style="F")
                self.set_fill_color(*builder.TEAL)
                self.rect(0, PDF_HEADER_BAND_MM, self.w, PDF_HEADER_ACCENT_MM, style="F")
                logo_h = builder.INNER_LOGO_HEIGHT_MM
                logo_y = max(1.0, (PDF_HEADER_BAND_MM - logo_h) / 2.0)
                builder._embed_logo(
                    self,
                    max_height=logo_h,
                    y=logo_y,
                    align="right",
                    padding=builder.MARGIN,
                )

            def footer(self) -> None:
                self.set_y(-12)
                self.set_draw_color(*builder.BORDER)
                self.line(builder.MARGIN, self.get_y(), self.w - builder.MARGIN, self.get_y())
                self.set_y(-10)
                self.set_font("Helvetica", "", 8)
                self.set_text_color(*builder.TEXT_MUTED)
                self.cell(
                    0,
                    8,
                    builder._safe(
                        f"Construct Eye  |  Project {PROJECT_ID}  |  "
                        f"Page {self.page_no()}/{{nb}}  |  Confidential"
                    ),
                    align="C",
                )

        return _ConstructEyePDF()

    def build(
        self,
        report: Dict[str, Any],
        location: str,
        progress: Optional[ProgressTracker] = None,
    ) -> str:
        tracker = progress or NullReportProgress()
        tracker.section_start("pdf", "PDF Report Generation")
        tracker.step_start("pdf", "render_pdf")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"construct_eye_report_{ts}_{Path(report['site_path']).stem}.pdf"
        output = self.output_dir / filename

        logo_path = self.logo_path
        site_parent = str(Path(report.get("site_path", "")).parent)
        folder_logo = os.path.join(site_parent, "Construct_eye_full.png")
        folder_icon = os.path.join(site_parent, "Construct_eye_logo.ico")
        if os.path.exists(folder_logo):
            logo_path = folder_logo
        elif os.path.exists(folder_icon):
            logo_path = folder_icon
        self._logo_asset = self._prepare_logo_asset(logo_path)

        pdf = self._make_pdf()
        pdf.set_margins(self.MARGIN, PDF_PAGE_TOP_MARGIN_MM, self.MARGIN)
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.alias_nb_pages()
        pdf.add_page()

        self._draw_cover_page(pdf)
        self._draw_meta_table(pdf, [
            ("Generated", report["timestamp"]),
            ("Location", location),
            ("Site photograph", report["site_image"]),
            ("Current phase", report["current_phase"]),
            ("Detailed stage", report["detailed_phase"]),
            ("Target date", report["estimated_completion_date_display"]),
            ("Time remaining", report["estimated_completion_duration_label"]),
            ("Estimate basis", report["estimated_completion_explanation"]),
            ("Structural reference", report["structural_reference_image"]),
            ("Architectural reference", report["architectural_reference_image"]),
        ])
        self._draw_progress_cards(pdf, report)

        summary_text = (
            f"Overall completion stands at {report['progress_percentage']}% with "
            f"structural work at {report['structural_progress_percentage']}% and "
            f"architectural work at {report['architectural_progress_percentage']}%. "
            f"The site is currently in the {report['current_phase']} phase "
            f"({report['detailed_phase']})."
        )
        summary_block = self._estimate_heading_height() + self._estimate_callout_height(pdf, summary_text)
        self._ensure_block_space(pdf, summary_block)
        self._section_heading(pdf, "Executive Summary")
        self._callout_box(pdf, summary_text, preflight=False)

        pdf.add_page()
        self._section_heading(pdf, "Current Site Photograph")
        site_photo_width = self._content_width(pdf)
        caption_reserve = 18.0
        site_photo_height = self._available_draw_height(pdf, reserved_bottom=caption_reserve)
        auto_break = pdf.auto_page_break
        page_break_margin = pdf.b_margin
        pdf.set_auto_page_break(auto=False)
        self._draw_framed_image(
            pdf,
            report["site_path"],
            caption=f"Live site capture: {report['site_image']}",
            max_width=site_photo_width,
            max_height=site_photo_height,
            preflight=False,
        )
        pdf.set_auto_page_break(auto=auto_break, margin=page_break_margin)
        self._start_new_content_page(pdf)

        self._track_section(
            pdf,
            "Part 1 - Structural Analysis",
            report["structural"],
            report["structural_reference_path"],
        )
        self._start_new_content_page(pdf)
        self._track_section(
            pdf,
            "Part 2 - Architectural Analysis",
            report["architectural"],
            report["architectural_reference_path"],
        )

        notes_text = (
            "This report was generated automatically by Construct Eye on Raspberry Pi 5 "
            "using AI vision analysis. Metrics combine structural and architectural "
            "observations against approved reference drawings. Access the latest version "
            "and live site stream from the Construct Eye mobile app."
        )
        notes_block = self._estimate_heading_height() + self._estimate_callout_height(pdf, notes_text)
        self._ensure_block_space(pdf, notes_block)
        self._section_heading(pdf, "Report Notes")
        self._callout_box(pdf, notes_text, preflight=False)

        pdf.output(str(output))
        if self._logo_asset is not None:
            self._logo_asset.unlink(missing_ok=True)
            self._logo_asset = None
        tracker.step_complete("pdf")
        tracker.section_complete("pdf")
        print(f"[PDF] Saved: {output}")
        return str(output)


class FirebaseReporter:
    def __init__(
        self,
        key_path: str,
        bucket_name: str,
        *,
        project_id: int = PROJECT_ID,
        site_name: str = DEFAULT_SITE_NAME,
        location: str = DEFAULT_LOCATION,
        stream_link: str = "",
        device_id: Optional[str] = None,
    ) -> None:
        if not FIREBASE_AVAILABLE:
            raise RuntimeError("firebase-admin not installed")
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Firebase key not found: {key_path}")
        self.project_id = project_id
        self.site_name = site_name
        self.location = location
        self.device_id = get_or_create_device_id(device_id)
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
        self.bucket = storage.bucket()
        self.db = firestore.client()
        if stream_link:
            resolved = detect_device_location()
            register_device(
                self.db,
                device_id=self.device_id,
                stream_link=stream_link,
                site_name=self.site_name,
                resolved=resolved,
                project_id=self.project_id,
            )
        print(f"[INIT] Firebase connected (project_id={project_id}, device={self.device_id})")

    def upload_file(self, local_path: str, storage_path: str) -> str:
        blob = self.bucket.blob(storage_path)
        blob.upload_from_filename(local_path)
        blob.make_public()
        return blob.public_url

    def publish_report(
        self,
        report: Dict[str, Any],
        site_path: str,
        pdf_path: str,
        location: str,
        progress: Optional[ProgressTracker] = None,
    ) -> str:
        tracker = progress or NullReportProgress()
        tracker.section_start("firebase", "Cloud Publish")
        site_filename = os.path.basename(site_path)
        pdf_filename = os.path.basename(pdf_path)

        tracker.step_start("firebase", "upload_site_image")
        image_url = self.upload_file(site_path, f"{STORAGE_IMAGE_PREFIX}/{site_filename}")
        tracker.step_complete("firebase")

        tracker.step_start("firebase", "upload_pdf")
        pdf_url = self.upload_file(pdf_path, f"{STORAGE_PDF_PREFIX}/{pdf_filename}")
        tracker.step_complete("firebase")

        struct = report["structural"]
        arch = report["architectural"]

        doc = {
            "project_id": self.project_id,
            "site_name": self.site_name,
            "timestamp": report["timestamp"],
            "timestamp_iso": report["timestamp_iso"],
            "image_name": site_filename,
            "progress_percentage": report["progress_percentage"],
            "structural_progress_percentage": report["structural_progress_percentage"],
            "architectural_progress_percentage": report["architectural_progress_percentage"],
            "current_phase": report["current_phase"],
            "detailed_phase": report["detailed_phase"],
            "remaining_percentage": report["remaining_percentage"],
            "description": report["description"],
            "site_condition_summary": report["site_condition_summary"],
            "estimated_completion_days": report["estimated_completion_days"],
            "estimated_completion_months": report["estimated_completion_months"],
            "estimated_completion_weeks": report["estimated_completion_weeks"],
            "estimated_completion_breakdown_days": report["estimated_completion_breakdown_days"],
            "estimated_completion_date": report["estimated_completion_date"],
            "estimated_completion_date_display": report["estimated_completion_date_display"],
            "estimated_completion_duration_label": report["estimated_completion_duration_label"],
            "estimated_completion_ai_days": report["estimated_completion_ai_days"],
            "estimated_completion_metric_days": report["estimated_completion_metric_days"],
            "estimated_completion_explanation": report["estimated_completion_explanation"],
            "estimated_completion_summary": report["estimated_completion_summary"],
            "estimated_completion_detail": report["estimated_completion_detail"],
            "image_url": image_url,
            "pdf_url": pdf_url,
            "pdf_filename": pdf_filename,
            "report_ready": True,
            "location": self.location or location,
            "structural_reference_image": report["structural_reference_image"],
            "architectural_reference_image": report["architectural_reference_image"],
            "structural": {
                "progress_percentage": struct["progress_percentage"],
                "current_phase": struct["current_phase"],
                "description": struct["description"],
                "comparison_summary": struct["comparison_summary"],
                "reference_metrics": struct["reference_metrics"],
                "site_metrics": struct["site_metrics"],
                "progress_breakdown": struct["progress_breakdown"],
            },
            "architectural": {
                "progress_percentage": arch["progress_percentage"],
                "current_phase": arch["current_phase"],
                "description": arch["description"],
                "comparison_summary": arch["comparison_summary"],
                "reference_metrics": arch["reference_metrics"],
                "site_metrics": arch["site_metrics"],
                "progress_breakdown": arch["progress_breakdown"],
            },
            "ai_analysis": {
                "site_condition": report["description"],
                "structural_observation": struct["description"],
                "architectural_observation": arch["description"],
                "target_design": arch["reference_description"],
                "structural_target": struct["reference_description"],
                "comparison_summary": arch["comparison_summary"],
                "structural_comparison": struct["comparison_summary"],
                "architectural_comparison": arch["comparison_summary"],
            },
        }

        tracker.step_start("firebase", "write_firestore")
        _, doc_ref = self.db.collection(FIRESTORE_COLLECTION).add(doc)
        tracker.step_complete("firebase")

        title, body = build_construction_report_notification(
            report["progress_percentage"],
            report["current_phase"],
            site_filename,
        )
        tracker.step_start("firebase", "send_notification")
        notify_project_users(
            self.db,
            title=title,
            body=body,
            project_id=self.project_id,
            notification_extra={
                "type": NOTIFICATION_TYPE_CONSTRUCTION_REPORT,
                "report_id": doc_ref.id,
                "image_url": image_url,
                "pdf_url": pdf_url,
                "progress_percentage": report["progress_percentage"],
                "current_phase": report["current_phase"],
            },
            fcm_data={
                "type": NOTIFICATION_TYPE_CONSTRUCTION_REPORT,
                "report_id": doc_ref.id,
            },
        )
        tracker.step_complete("firebase")
        tracker.section_complete("firebase")

        print(f"[SUCCESS] Firestore: {doc_ref.id}")
        print(f"[SUCCESS] PDF URL: {pdf_url}")
        return doc_ref.id


def _list_images(folder: str) -> List[str]:
    images: List[str] = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        images.extend(glob.glob(os.path.join(folder, ext)))
    return sorted(set(images))


def find_reference_images(
    folder: str,
    architectural: Optional[str] = None,
    structural: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    if architectural and os.path.exists(architectural):
        arch_path = architectural
    else:
        arch_path = next((p for p in _list_images(folder) if _matches_hints(os.path.basename(p), ARCHITECTURAL_HINTS)), None)

    if structural and os.path.exists(structural):
        struct_path = structural
    else:
        struct_path = next((p for p in _list_images(folder) if _matches_hints(os.path.basename(p), STRUCTURAL_HINTS)), None)

    return struct_path, arch_path


def find_site_images(folder: str, exclude: List[str], explicit: Optional[str] = None) -> List[str]:
    if explicit:
        return [explicit] if os.path.exists(explicit) else []

    exclude_abs = {os.path.abspath(p) for p in exclude}
    result = []
    for path in _list_images(folder):
        if os.path.abspath(path) in exclude_abs:
            continue
        name = os.path.basename(path)
        if _matches_hints(name, ALL_REFERENCE_HINTS):
            continue
        result.append(path)
    return result


def reference_cache_status(
    struct_ref_path: str,
    arch_ref_path: str,
    *,
    cache_dir: str,
    force_reference_scan: bool,
) -> Tuple[bool, bool]:
    """Return whether each reference image has a valid on-disk metrics cache."""
    if force_reference_scan:
        return False, False
    cache = ReferenceMetricsCache(cache_dir)
    return (
        cache.has_valid(struct_ref_path, "structural_reference"),
        cache.has_valid(arch_ref_path, "architectural_reference"),
    )


def compute_pipeline_step_count(
    *,
    include_firebase: bool,
    site_count: int = 1,
    struct_ref_cached: bool = False,
    arch_ref_cached: bool = False,
) -> int:
    """Steps tracked by the progress GUI and bottom progress bar."""
    struct_steps = 1 if struct_ref_cached else len(ConstructionProgressEngine.STRUCTURAL_REFERENCE_QUESTIONS) + 1
    arch_steps = 1 if arch_ref_cached else len(ConstructionProgressEngine.ARCHITECTURAL_REFERENCE_QUESTIONS) + 1
    per_site = (
        struct_steps
        + arch_steps
        + len(ConstructionProgressEngine.STRUCTURAL_SITE_QUESTIONS) + 1
        + len(ConstructionProgressEngine.ARCHITECTURAL_SITE_QUESTIONS) + 1
        + 2
        + 3
        + 1
        + (4 if include_firebase else 0)
    )
    prep_steps = 1 + (1 if include_firebase else 0)
    return prep_steps + (per_site * max(1, site_count))


def _format_elapsed(seconds: float) -> str:
    """Human-readable duration for terminal output."""
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Dual-track construction progress report generator (v{SCRIPT_VERSION}).",
    )
    parser.add_argument("folder", nargs="?", default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--architectural", help="Path to Architectural View reference")
    parser.add_argument("--structural", help="Path to Structural View reference")
    parser.add_argument("--site", help="Process one site image only")
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--firebase-key", default=os.getenv("FIREBASE_SERVICE_ACCOUNT"))
    parser.add_argument("--firebase-bucket", default=os.getenv("FIREBASE_STORAGE_BUCKET", "YOUR_PROJECT_ID.appspot.com"))
    parser.add_argument("--moondream-key", default=os.getenv("MOONDREAM_API_KEY"))
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument("--project-id", type=int, default=PROJECT_ID, help="Active project id (CONSTRUCT_EYE_PROJECT_ID env)")
    parser.add_argument("--device-id", default=os.getenv("DEVICE_ID"), help="Device doc ID for devices collection")
    parser.add_argument(
        "--stream-link",
        default=os.getenv("STREAM_LINK", ""),
        help="Optional live stream URL stored on devices/{device_id}",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Show live progress window on the Pi display (default when DISPLAY is set)",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Disable the progress window (terminal only)",
    )
    parser.add_argument(
        "--reference-cache-dir",
        default=DEFAULT_REFERENCE_CACHE_DIR,
        help="Directory for saved structural/architectural reference metrics (default: reference_metrics_cache)",
    )
    parser.add_argument(
        "--refresh-references",
        action="store_true",
        help="Force re-scan of reference images even when saved metrics exist",
    )
    parser.add_argument(
        "--gui-icon",
        default=os.getenv("CONSTRUCT_EYE_GUI_ICON", DEFAULT_GUI_ICON if GUI_AVAILABLE else ""),
        help="Window icon for the progress GUI (.ico or .png)",
    )
    parser.add_argument(
        "--gui-logo",
        default=os.getenv("CONSTRUCT_EYE_GUI_LOGO", DEFAULT_GUI_LOGO if GUI_AVAILABLE else ""),
        help="Logo image shown in the top-right of the progress GUI",
    )
    parser.add_argument(
        "--gui-theme",
        choices=("light", "dark"),
        default=os.getenv("CONSTRUCT_EYE_GUI_THEME", "light"),
        help="Initial GUI theme (light or dark); toggle button available in the window",
    )
    parser.add_argument(
        "--pdf-logo",
        default=os.getenv("CONSTRUCT_EYE_PDF_LOGO", DEFAULT_PDF_LOGO),
        help="Construct Eye logo for PDF cover (large) and inner pages (small)",
    )
    return parser


def _run_reports(args: argparse.Namespace, progress: ProgressTracker) -> int:
    if not args.moondream_key:
        print("[ERROR] Set MOONDREAM_API_KEY or pass --moondream-key")
        progress.fail("MOONDREAM_API_KEY is not set")
        return 1
    if not os.path.isdir(args.folder):
        print(f"[ERROR] Folder not found: {args.folder}")
        progress.fail(f"Folder not found: {args.folder}")
        return 1

    struct_ref, arch_ref = find_reference_images(args.folder, args.architectural, args.structural)
    if not struct_ref:
        print("[ERROR] No structural reference found. Expected 'Structural View.png' or --structural")
        progress.fail("Structural reference image not found")
        return 1
    if not arch_ref:
        print("[ERROR] No architectural reference found. Expected 'Architectural View.png' or --architectural")
        progress.fail("Architectural reference image not found")
        return 1

    site_images = find_site_images(args.folder, [struct_ref, arch_ref], args.site)
    if not site_images:
        print("[ERROR] No site photos found (Building Under Construction...).")
        progress.fail("No site photograph found")
        return 1

    struct_cached, arch_cached = reference_cache_status(
        struct_ref,
        arch_ref,
        cache_dir=args.reference_cache_dir,
        force_reference_scan=args.refresh_references,
    )
    print(f"[INFO] Structural reference:  {os.path.basename(struct_ref)}")
    print(f"[INFO] Architectural reference: {os.path.basename(arch_ref)}")
    print(f"[INFO] Site images: {len(site_images)}")
    if struct_cached:
        print("[INFO] Structural reference metrics: using saved cache")
    else:
        print("[INFO] Structural reference metrics: will scan with AI")
    if arch_cached:
        print("[INFO] Architectural reference metrics: using saved cache")
    else:
        print("[INFO] Architectural reference metrics: will scan with AI")
    if args.refresh_references:
        print("[INFO] --refresh-references set: forcing full reference re-scan")

    progress.section_start("prep", "Initialization")
    progress.step_start("prep", "validate_inputs", "Validating images and configuration")
    progress.step_complete("prep")
    progress.section_complete("prep")

    moondream = MoondreamClient(args.moondream_key)
    try:
        MoondreamClient.verify_connectivity()
    except AnalysisQualityError as exc:
        print(f"[ERROR] {exc}")
        progress.fail(str(exc))
        return 1

    engine = ConstructionProgressEngine(
        moondream,
        progress=progress,
        reference_cache=ReferenceMetricsCache(args.reference_cache_dir),
        force_reference_scan=args.refresh_references,
    )
    pdf_logo = args.pdf_logo
    if not os.path.isabs(pdf_logo) and os.path.isdir(args.folder):
        folder_logo = os.path.join(args.folder, "Construct_eye_full.png")
        if os.path.exists(folder_logo):
            pdf_logo = folder_logo
    pdf_builder = PDFReportBuilder(args.reports_dir, logo_path=pdf_logo)
    firebase = None
    if not args.no_upload:
        if not args.firebase_key:
            print("[ERROR] Set FIREBASE_SERVICE_ACCOUNT or pass --firebase-key")
            progress.fail("FIREBASE_SERVICE_ACCOUNT is not set")
            return 1
        progress.section_start("prep_cloud", "Cloud Connection")
        progress.step_start("prep_cloud", "connect_firebase")
        firebase = FirebaseReporter(
            args.firebase_key,
            args.firebase_bucket,
            project_id=args.project_id,
            location=args.location,
            stream_link=args.stream_link,
            device_id=args.device_id,
        )
        progress.step_complete("prep_cloud")
        progress.section_complete("prep_cloud")

    run_started = time.perf_counter()
    for site_path in site_images:
        print(f"\n{'=' * 60}\n[RUN] {os.path.basename(site_path)}\n{'=' * 60}")
        progress.set_status(f"Processing {os.path.basename(site_path)}")
        report_started = time.perf_counter()
        try:
            report = engine.run_full_analysis(struct_ref, arch_ref, site_path)
        except AnalysisQualityError as exc:
            print(f"[ERROR] {exc}")
            progress.fail(str(exc))
            return 1
        pdf_path = pdf_builder.build(report, args.location, progress=progress)
        if firebase:
            firebase.publish_report(
                report, site_path, pdf_path, args.location, progress=progress,
            )
        report_elapsed = time.perf_counter() - report_started
        print(
            f"[DONE] Overall {report['progress_percentage']}% | "
            f"Structural {report['structural_progress_percentage']}% | "
            f"Architectural {report['architectural_progress_percentage']}% | "
            f"Phase: {report['current_phase']}"
        )
        print(
            f"[TIME] Report took {_format_elapsed(report_elapsed)} "
            f"({report_elapsed:.1f}s total - AI analysis, PDF, "
            f"{'Firebase upload' if firebase else 'no upload'})"
        )
        progress.complete({
            "progress_percentage": report["progress_percentage"],
            "structural_progress_percentage": report["structural_progress_percentage"],
            "architectural_progress_percentage": report["architectural_progress_percentage"],
            "current_phase": report["current_phase"],
            "pdf_path": pdf_path,
        })

    total_elapsed = time.perf_counter() - run_started
    if len(site_images) > 1:
        print(
            f"\n[TIME] All {len(site_images)} reports finished in "
            f"{_format_elapsed(total_elapsed)} ({total_elapsed:.1f}s)"
        )
    return 0


def main() -> int:
    args = build_arg_parser().parse_args()
    print(f"[INFO] construction_progress_report.py v{SCRIPT_VERSION}")

    use_gui = not args.no_gui and (args.gui or gui_available())
    if use_gui and not GUI_AVAILABLE:
        print("[WARN] GUI requested but report_progress_gui is unavailable; using terminal only")
        use_gui = False
    if use_gui:
        print("[INFO] Live progress window enabled")

    include_firebase = not args.no_upload and bool(args.firebase_key or os.getenv("FIREBASE_SERVICE_ACCOUNT"))
    site_count_guess = 1 if args.site else 0
    struct_cached = False
    arch_cached = False
    if os.path.isdir(args.folder):
        struct_ref, arch_ref = find_reference_images(args.folder, args.architectural, args.structural)
        if struct_ref and arch_ref:
            if site_count_guess == 0:
                site_count_guess = len(find_site_images(args.folder, [struct_ref, arch_ref], None))
            struct_cached, arch_cached = reference_cache_status(
                struct_ref,
                arch_ref,
                cache_dir=args.reference_cache_dir,
                force_reference_scan=args.refresh_references,
            )
    total_steps = compute_pipeline_step_count(
        include_firebase=include_firebase,
        site_count=max(1, site_count_guess),
        struct_ref_cached=struct_cached,
        arch_ref_cached=arch_cached,
    )

    if use_gui:
        icon_path = args.gui_icon
        logo_path = args.gui_logo
        if not icon_path and args.folder:
            folder_icon = os.path.join(args.folder, "Construct_eye_logo.ico")
            if os.path.exists(folder_icon):
                icon_path = folder_icon
        if not logo_path and args.folder:
            folder_logo = os.path.join(args.folder, "Construct_eye_full.png")
            if os.path.exists(folder_logo):
                logo_path = folder_logo
        return run_with_gui(
            lambda progress: _run_reports(args, progress),
            total_steps=total_steps,
            icon_path=icon_path or DEFAULT_GUI_ICON,
            logo_path=logo_path or DEFAULT_GUI_LOGO,
            initial_theme=args.gui_theme,
        )
    return _run_reports(args, NullReportProgress())


if __name__ == "__main__":
    sys.exit(main())
