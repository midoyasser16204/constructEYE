"""
Tkinter progress UI for construction_progress_report.py (Raspberry Pi display).

Shows section headers, per-step loading spinners, green checks, a bottom
progress bar, branding logo, window icon, and light/dark theme toggle.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BRANDING = _PROJECT_ROOT / "assets" / "branding"

try:
    from PIL import Image, ImageTk

    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# --- Brand anchors ---
NAVY = "#0F2A44"
TEAL = "#0E7490"
SUCCESS = "#16A34A"

DEFAULT_GUI_ICON = str(_DEFAULT_BRANDING / "construct_eye_logo.ico")
DEFAULT_GUI_LOGO = str(_DEFAULT_BRANDING / "construct_eye_logo.png")

THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#F1F5F9",
        "card": "#FFFFFF",
        "header": NAVY,
        "header_text": "#FFFFFF",
        "header_sub": "#CBD5E1",
        "accent": TEAL,
        "border": "#CBD5E1",
        "text": "#0F172A",
        "muted": "#64748B",
        "section_bg": "#E8EEF7",
        "section_text": NAVY,
        "footer": "#FFFFFF",
        "spinner": TEAL,
        "success_bg": "#DCFCE7",
        "success_text": "#14532D",
        "toggle_bg": "#E2E8F0",
        "toggle_fg": NAVY,
        "toggle_border": "#94A3B8",
        "button_bg": NAVY,
        "button_fg": "#FFFFFF",
        "button_active": TEAL,
        "error_bg": "#FEE2E2",
        "error_fg": "#991B1B",
        "progress_track": "#E2E8F0",
        "scrollbar": "#CBD5E1",
        "scrollbar_trough": "#F1F5F9",
    },
    "dark": {
        "bg": "#0F172A",
        "card": "#1E293B",
        "header": NAVY,
        "header_text": "#F8FAFC",
        "header_sub": "#94A3B8",
        "accent": "#38BDF8",
        "border": "#334155",
        "text": "#F1F5F9",
        "muted": "#94A3B8",
        "section_bg": "#1E3A5F",
        "section_text": "#F8FAFC",
        "footer": "#1E293B",
        "spinner": "#38BDF8",
        "success_bg": "#064E3B",
        "success_text": "#D1FAE5",
        "toggle_bg": "#334155",
        "toggle_fg": "#F8FAFC",
        "toggle_border": "#475569",
        "button_bg": "#1E3A5F",
        "button_fg": "#FFFFFF",
        "button_active": TEAL,
        "error_bg": "#450A0A",
        "error_fg": "#FECACA",
        "progress_track": "#334155",
        "scrollbar": "#475569",
        "scrollbar_trough": "#1E293B",
    },
}

HEADER_LOGO_HEIGHT = 68


def humanize_step(key: str) -> str:
    """Turn internal metric keys into readable step labels."""
    labels = {
        "total_floors": "Counting floor levels in design",
        "structural_system": "Identifying structural system",
        "column_count": "Counting facade columns",
        "floor_slabs": "Counting floor slabs in design",
        "roof_structure": "Analyzing roof structure type",
        "total_windows": "Counting window openings in design",
        "total_balconies": "Counting balconies in design",
        "building_type": "Identifying building type",
        "facade_material": "Reading facade materials",
        "roof_finish": "Analyzing finished roof appearance",
        "built_floors": "Counting built floor levels on site",
        "visible_columns": "Checking visible structural columns",
        "floor_slabs_cast": "Counting cast floor slabs",
        "roof_slab_status": "Assessing structural roof slab status",
        "scaffolding": "Detecting scaffolding on site",
        "workers_visible": "Checking for workers on site",
        "structural_materials": "Listing structural materials",
        "crane_or_equipment": "Detecting cranes and equipment",
        "windows_now": "Counting window openings on site",
        "balconies_now": "Counting balconies on site",
        "wall_status": "Evaluating exterior wall finish",
        "roof_status": "Evaluating roof finish status",
        "windows_glass": "Checking window glass installation",
        "railings_done": "Checking balcony railings",
        "landscaping": "Checking landscaping and paving",
        "facade_color": "Reading exterior color and surface",
        "entrance_finished": "Assessing main entrance finish",
        "description": "Generating AI summary narrative",
        "structural_comparison": "Comparing site to structural target",
        "architectural_comparison": "Comparing site to architectural target",
        "structural_progress": "Calculating structural completion",
        "architectural_progress": "Calculating architectural completion",
        "overall_phase": "Determining current project phase",
        "render_pdf": "Rendering professional PDF report",
        "upload_site_image": "Uploading site photograph to cloud",
        "upload_pdf": "Uploading PDF report to cloud",
        "write_firestore": "Saving report to Firestore database",
        "send_notification": "Sending push notification to mobile app",
        "validate_inputs": "Validating images and configuration",
        "connect_firebase": "Connecting to Firebase cloud services",
        "cache_hit": "Loading saved reference metrics",
    }
    return labels.get(key, key.replace("_", " ").capitalize())


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _load_tk_image(
    path: str,
    *,
    max_height: int = 48,
    background: Optional[str] = None,
) -> Optional[tk.PhotoImage]:
    """Load PNG/ICO/JPG for Tkinter; optional flat background for header logos."""
    if not path or not os.path.exists(path):
        return None
    if not _PIL_AVAILABLE:
        if path.lower().endswith(".png"):
            try:
                return tk.PhotoImage(file=path)
            except tk.TclError:
                return None
        return None
    try:
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            if max_height and rgba.height > max_height:
                ratio = max_height / float(rgba.height)
                rgba = rgba.resize(
                    (max(1, int(rgba.width * ratio)), max_height),
                    Image.Resampling.LANCZOS,
                )
            if background:
                bg = Image.new("RGBA", rgba.size, _hex_to_rgb(background) + (255,))
                bg.alpha_composite(rgba)
                rgba = bg
            return ImageTk.PhotoImage(rgba.convert("RGB"))
    except Exception:
        return None


def _ico_frame_candidates(img: Image.Image) -> List[Image.Image]:
    """Extract every embedded size from a multi-resolution .ico file."""
    frames: List[Image.Image] = []
    try:
        index = 0
        while True:
            img.seek(index)
            frames.append(img.copy().convert("RGBA"))
            index += 1
    except EOFError:
        pass
    if not frames:
        frames.append(img.convert("RGBA"))
    return frames


def _load_window_icon(path: str, *, preferred_size: int = 64) -> Optional[tk.PhotoImage]:
    """Load a window/taskbar icon, preferring the best .ico embedded size."""
    if not path or not os.path.exists(path):
        return None
    if not _PIL_AVAILABLE:
        return None
    try:
        with Image.open(path) as img:
            if path.lower().endswith(".ico"):
                frames = _ico_frame_candidates(img)
            else:
                frames = [img.convert("RGBA")]

            def _frame_score(frame: Image.Image) -> int:
                return abs(max(frame.size) - preferred_size)

            best = min(frames, key=_frame_score)
            width, height = best.size
            max_dim = max(width, height)
            if max_dim > 128:
                ratio = 128 / float(max_dim)
                best = best.resize(
                    (max(1, int(width * ratio)), max(1, int(height * ratio))),
                    Image.Resampling.LANCZOS,
                )
            elif max_dim < 32:
                ratio = 32 / float(max_dim)
                best = best.resize(
                    (max(1, int(width * ratio)), max(1, int(height * ratio))),
                    Image.Resampling.LANCZOS,
                )
            return ImageTk.PhotoImage(best.convert("RGB"))
    except Exception:
        return None


def _icon_fallback_paths(icon_path: str) -> List[str]:
    """PNG fallbacks when a .ico cannot be used by the window manager."""
    candidates: List[str] = []
    if icon_path:
        base, _ = os.path.splitext(icon_path)
        candidates.append(f"{base}.png")
        folder = os.path.dirname(icon_path)
        if folder:
            candidates.append(os.path.join(folder, "construct_eye_logo.png"))
    candidates.append(DEFAULT_GUI_LOGO)
    seen: set[str] = set()
    ordered: List[str] = []
    for candidate in candidates:
        norm = os.path.normpath(candidate)
        if norm not in seen and os.path.exists(norm):
            seen.add(norm)
            ordered.append(norm)
    return ordered


class NullReportProgress:
    """No-op progress tracker when GUI is disabled."""

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


class ReportProgressTracker:
    """Thread-safe progress state; GUI polls via a queue."""

    def __init__(self, *, total_steps: int) -> None:
        self.total_steps = max(1, total_steps)
        self.completed_steps = 0
        self._events: queue.Queue[Tuple[str, Any]] = queue.Queue()
        self._started = time.perf_counter()

    def bind_gui(self, gui: "ReportProgressGUI") -> None:
        gui.attach_tracker(self)

    def _emit(self, event: str, payload: Any = None) -> None:
        self._events.put((event, payload))

    def section_start(self, section_id: str, title: str) -> None:
        self._emit("section_start", {"id": section_id, "title": title})

    def section_complete(self, section_id: str) -> None:
        self._emit("section_complete", {"id": section_id})

    def step_start(self, section_id: str, step_key: str, label: Optional[str] = None) -> None:
        self._emit(
            "step_start",
            {
                "section_id": section_id,
                "step_key": step_key,
                "label": label or humanize_step(step_key),
            },
        )

    def step_complete(self, section_id: str) -> None:
        self.completed_steps = min(self.total_steps, self.completed_steps + 1)
        self._emit(
            "step_complete",
            {
                "section_id": section_id,
                "completed": self.completed_steps,
                "total": self.total_steps,
                "elapsed": time.perf_counter() - self._started,
            },
        )

    def set_status(self, message: str) -> None:
        self._emit("status", message)

    def complete(self, summary: Dict[str, Any]) -> None:
        summary = dict(summary)
        summary["elapsed"] = time.perf_counter() - self._started
        summary["completed"] = self.total_steps
        summary["total"] = self.total_steps
        self._emit("complete", summary)

    def fail(self, message: str) -> None:
        self._emit("fail", message)


class ReportProgressGUI:
    """Professional Tkinter window for live report generation feedback."""

    def __init__(
        self,
        *,
        icon_path: str = DEFAULT_GUI_ICON,
        logo_path: str = DEFAULT_GUI_LOGO,
        initial_theme: str = "light",
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Construct Eye - Report Generation")
        self.root.geometry("860x640")
        self.root.minsize(760, 540)
        self._theme_name = initial_theme if initial_theme in THEMES else "light"
        self._theme = THEMES[self._theme_name]
        self.root.configure(bg=self._theme["bg"])

        self.exit_code = 0
        self._tracker: Optional[ReportProgressTracker] = None
        self._sections: Dict[str, Dict[str, Any]] = {}
        self._active_step: Optional[Dict[str, Any]] = None
        self._spinner_frames = ("|", "/", "-", "\\")
        self._spinner_index = 0
        self._spinner_job: Optional[str] = None
        self._poll_job: Optional[str] = None
        self._icon_image: Optional[tk.PhotoImage] = None
        self._logo_image: Optional[tk.PhotoImage] = None
        self._logo_path = logo_path
        self._complete_labels: List[tk.Label] = []
        self._close_button: Optional[tk.Button] = None
        self._error_label: Optional[tk.Label] = None
        self._scrollbar: Optional[tk.Scrollbar] = None

        self._apply_window_icon(icon_path)
        self._build_chrome()
        self._reload_header_logo()
        self._apply_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def theme(self) -> Dict[str, str]:
        return self._theme

    def _apply_window_icon(self, icon_path: str) -> None:
        if not icon_path:
            return

        image = _load_window_icon(icon_path)
        if image is None:
            for fallback in _icon_fallback_paths(icon_path):
                image = _load_window_icon(fallback)
                if image is not None:
                    break

        if image is not None:
            self._icon_image = image
            try:
                self.root.iconphoto(True, image)
                self.root.tk.call("wm", "iconphoto", self.root._w, image)
                return
            except tk.TclError:
                pass

        if icon_path.lower().endswith(".ico") and os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

    def _reload_header_logo(self) -> None:
        image = _load_tk_image(
            self._logo_path,
            max_height=HEADER_LOGO_HEIGHT,
            background=self._theme["header"],
        )
        if image is not None:
            self._logo_image = image
            self.logo_label.configure(image=image, text="")
            self.title_wrap.grid_remove()
            self.subtitle_label.grid(row=0, column=1, sticky="w", pady=24)
            self.subtitle_label.configure(font=("Helvetica", 11))
        else:
            self.logo_label.configure(
                image="",
                text="CE",
                fg=self._theme["header_sub"],
                font=("Helvetica", 16, "bold"),
            )
            self.title_wrap.grid()
            self.subtitle_label.grid(row=1, column=1, sticky="w", pady=(0, 14))
            self.subtitle_label.configure(font=("Helvetica", 10))

    def _build_chrome(self) -> None:
        self.header = tk.Frame(self.root, bg=self._theme["header"], height=92)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)

        self.logo_label = tk.Label(self.header, bg=self._theme["header"])
        self.logo_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(18, 10), pady=10)

        self.title_wrap = tk.Frame(self.header, bg=self._theme["header"])
        self.title_wrap.grid(row=0, column=1, sticky="w", pady=(18, 0))

        self.title_label = tk.Label(
            self.title_wrap,
            text="CONSTRUCT EYE",
            bg=self._theme["header"],
            fg=self._theme["header_text"],
            font=("Helvetica", 20, "bold"),
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(
            self.header,
            text="Construction Progress Report  |  Live Generation",
            bg=self._theme["header"],
            fg=self._theme["header_sub"],
            font=("Helvetica", 10),
            anchor="w",
        )
        self.subtitle_label.grid(row=1, column=1, sticky="w", pady=(0, 14))

        self.accent_bar = tk.Frame(self.root, bg=self._theme["accent"], height=3)
        self.accent_bar.pack(fill="x")

        self.body_wrap = tk.Frame(self.root, bg=self._theme["bg"])
        self.body_wrap.pack(fill="both", expand=True, padx=16, pady=12)

        self.status_var = tk.StringVar(value="Preparing report pipeline...")
        self.status_label = tk.Label(
            self.body_wrap,
            textvariable=self.status_var,
            bg=self._theme["bg"],
            fg=self._theme["text"],
            font=("Helvetica", 11, "bold"),
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(0, 8))

        self.list_card = tk.Frame(
            self.body_wrap,
            bg=self._theme["card"],
            highlightbackground=self._theme["border"],
            highlightthickness=1,
        )
        self.list_card.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            self.list_card,
            bg=self._theme["card"],
            highlightthickness=0,
            borderwidth=0,
        )
        self._scrollbar = tk.Scrollbar(self.list_card, orient="vertical", command=self.canvas.yview)
        self.scroll_inner = tk.Frame(self.canvas, bg=self._theme["card"])
        self.scroll_inner.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self._scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self._scrollbar.pack(side="right", fill="y", pady=8, padx=(0, 8))

        self.footer = tk.Frame(
            self.root,
            bg=self._theme["footer"],
            highlightbackground=self._theme["border"],
            highlightthickness=1,
        )
        self.footer.pack(fill="x", padx=16, pady=(0, 16))

        self.footer_inner = tk.Frame(self.footer, bg=self._theme["footer"])
        self.footer_inner.pack(fill="x", padx=14, pady=(10, 10))
        self.footer_inner.grid_columnconfigure(0, weight=1)

        self.progress_text = tk.StringVar(value="0%")
        self.progress_label = tk.Label(
            self.footer_inner,
            textvariable=self.progress_text,
            bg=self._theme["footer"],
            fg=self._theme["text"],
            font=("Helvetica", 10, "bold"),
        )
        self.progress_label.grid(row=0, column=0, sticky="w")

        self.theme_button = tk.Button(
            self.footer_inner,
            text="Dark mode",
            font=("Helvetica", 9, "bold"),
            relief="solid",
            borderwidth=1,
            padx=14,
            pady=5,
            cursor="hand2",
            command=self._toggle_theme,
        )
        self.theme_button.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.progress_bg = tk.Frame(self.footer_inner, bg=self._theme["progress_track"], height=12)
        self.progress_bg.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        self.progress_fill = tk.Frame(self.progress_bg, bg=self._theme["accent"], height=12, width=0)
        self.progress_fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)

        self.elapsed_var = tk.StringVar(value="Elapsed: 0s")
        self.elapsed_label = tk.Label(
            self.footer_inner,
            textvariable=self.elapsed_var,
            bg=self._theme["footer"],
            fg=self._theme["muted"],
            font=("Helvetica", 9),
        )
        self.elapsed_label.grid(row=2, column=0, columnspan=2, sticky="w")

        self.complete_panel = tk.Frame(
            self.body_wrap,
            bg=self._theme["success_bg"],
            highlightbackground=SUCCESS,
            highlightthickness=1,
        )
        self.complete_title: Optional[tk.Label] = None

    def _toggle_theme(self) -> None:
        self._theme_name = "dark" if self._theme_name == "light" else "light"
        self._theme = THEMES[self._theme_name]
        self._reload_header_logo()
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = self._theme
        self.root.configure(bg=t["bg"])
        self.header.configure(bg=t["header"])
        self.title_wrap.configure(bg=t["header"])
        self.title_label.configure(bg=t["header"], fg=t["header_text"])
        self.subtitle_label.configure(bg=t["header"], fg=t["header_sub"])
        self.logo_label.configure(bg=t["header"])
        self.theme_button.configure(
            text="Light mode" if self._theme_name == "dark" else "Dark mode",
            bg=t["toggle_bg"],
            fg=t["toggle_fg"],
            activebackground=t["button_active"],
            activeforeground=t["button_fg"],
            highlightbackground=t["toggle_border"],
            highlightcolor=t["toggle_border"],
        )
        self.accent_bar.configure(bg=t["accent"])
        self.body_wrap.configure(bg=t["bg"])
        self.status_label.configure(bg=t["bg"], fg=t["text"])
        self.list_card.configure(bg=t["card"], highlightbackground=t["border"])
        self.canvas.configure(bg=t["card"])
        self.scroll_inner.configure(bg=t["card"])
        if self._scrollbar is not None:
            self._scrollbar.configure(
                bg=t["scrollbar"],
                troughcolor=t["scrollbar_trough"],
                activebackground=t["accent"],
            )
        self.footer.configure(bg=t["footer"], highlightbackground=t["border"])
        self.footer_inner.configure(bg=t["footer"])
        self.progress_label.configure(bg=t["footer"], fg=t["text"])
        self.progress_bg.configure(bg=t["progress_track"])
        if str(self.progress_fill.cget("bg")) not in (SUCCESS, "#DC2626"):
            self.progress_fill.configure(bg=t["accent"])
        self.elapsed_label.configure(bg=t["footer"], fg=t["muted"])
        self.complete_panel.configure(bg=t["success_bg"])
        if self.complete_title is not None:
            self.complete_title.configure(bg=t["success_bg"], fg=SUCCESS)
        for label in self._complete_labels:
            label.configure(bg=t["success_bg"], fg=t["success_text"])
        if self._close_button is not None:
            self._close_button.configure(
                bg=t["button_bg"],
                fg=t["button_fg"],
                activebackground=t["button_active"],
                activeforeground=t["button_fg"],
            )
        if self._error_label is not None:
            self._error_label.configure(bg=t["error_bg"], fg=t["error_fg"])

        for section in self._sections.values():
            self._style_section(section)

    def _style_section(self, section: Dict[str, Any]) -> None:
        t = self._theme
        section["frame"].configure(bg=t["card"])
        section["header"].configure(bg=t["section_bg"])
        section["title_label"].configure(bg=t["section_bg"], fg=t["section_text"])
        status_fg = SUCCESS if section.get("done") else t["spinner"]
        section["status"].configure(bg=t["section_bg"], fg=status_fg)
        section["steps"].configure(bg=t["card"])
        for step in section.get("step_rows", []):
            step["row"].configure(bg=t["card"])
            icon_fg = SUCCESS if step.get("done") else t["spinner"]
            step["icon"].configure(bg=t["card"], fg=icon_fg)
            step["label"].configure(bg=t["card"], fg=t["text"])

    def attach_tracker(self, tracker: ReportProgressTracker) -> None:
        self._tracker = tracker

    def schedule(self, callback: Callable[[], None]) -> None:
        self.root.after(0, callback)

    def _on_close(self) -> None:
        self.exit_code = 0
        self.root.destroy()

    def _scroll_to_bottom(self) -> None:
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _ensure_section(self, section_id: str, title: str) -> Dict[str, Any]:
        if section_id in self._sections:
            return self._sections[section_id]
        row = tk.Frame(self.scroll_inner, bg=self._theme["card"])
        row.pack(fill="x", padx=8, pady=(10, 4))

        header = tk.Frame(row, bg=self._theme["section_bg"])
        header.pack(fill="x")
        title_label = tk.Label(
            header,
            text=title,
            bg=self._theme["section_bg"],
            fg=self._theme["section_text"],
            font=("Helvetica", 11, "bold"),
            anchor="w",
        )
        title_label.pack(side="left", padx=10, pady=8)
        status = tk.Label(
            header,
            text="...",
            bg=self._theme["section_bg"],
            fg=self._theme["spinner"],
            font=("Helvetica", 12, "bold"),
            width=2,
        )
        status.pack(side="right", padx=10, pady=8)

        steps = tk.Frame(row, bg=self._theme["card"])
        steps.pack(fill="x", padx=12, pady=(4, 8))

        section = {
            "frame": row,
            "header": header,
            "title_label": title_label,
            "status": status,
            "steps": steps,
            "done": False,
            "step_rows": [],
        }
        self._sections[section_id] = section
        self._scroll_to_bottom()
        return section

    def _start_spinner(self, target: tk.Label) -> None:
        def tick() -> None:
            if target.winfo_exists():
                target.configure(text=self._spinner_frames[self._spinner_index], fg=self._theme["spinner"])
                self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
                self._spinner_job = self.root.after(120, tick)

        if self._spinner_job:
            self.root.after_cancel(self._spinner_job)
        tick()

    def _stop_spinner(self) -> None:
        if self._spinner_job:
            self.root.after_cancel(self._spinner_job)
            self._spinner_job = None

    def _handle_event(self, event: str, payload: Any) -> None:
        if event == "status":
            self.status_var.set(str(payload))
            return

        if event == "section_start":
            assert isinstance(payload, dict)
            self._ensure_section(payload["id"], payload["title"])
            self.status_var.set(payload["title"])
            return

        if event == "section_complete":
            assert isinstance(payload, dict)
            section = self._sections.get(payload["id"])
            if section:
                section["done"] = True
                section["status"].configure(text="\u2713", fg=SUCCESS)
            return

        if event == "step_start":
            assert isinstance(payload, dict)
            section = self._sections[payload["section_id"]]

            step_row = tk.Frame(section["steps"], bg=self._theme["card"])
            step_row.pack(fill="x", pady=2)
            icon = tk.Label(
                step_row,
                text="|",
                bg=self._theme["card"],
                fg=self._theme["spinner"],
                font=("Helvetica", 11, "bold"),
                width=2,
            )
            icon.pack(side="left")
            label = tk.Label(
                step_row,
                text=payload["label"],
                bg=self._theme["card"],
                fg=self._theme["text"],
                font=("Helvetica", 10),
                anchor="w",
            )
            label.pack(side="left", fill="x", expand=True)
            step_info = {"row": step_row, "icon": icon, "label": label, "done": False}
            section["step_rows"].append(step_info)
            self._active_step = step_info
            self._start_spinner(icon)
            self.status_var.set(payload["label"])
            self._scroll_to_bottom()
            return

        if event == "step_complete":
            assert isinstance(payload, dict)
            if self._active_step and self._active_step.get("icon"):
                self._stop_spinner()
                self._active_step["icon"].configure(text="\u2713", fg=SUCCESS)
                self._active_step["done"] = True
                self._active_step = None
            completed = int(payload.get("completed", 0))
            total = max(1, int(payload.get("total", 1)))
            pct = min(100.0, (completed / total) * 100.0)
            self.progress_text.set(f"{pct:.0f}% complete ({completed}/{total} steps)")
            self.progress_fill.place_configure(relwidth=pct / 100.0)
            elapsed = float(payload.get("elapsed", 0.0))
            self.elapsed_var.set(f"Elapsed: {_format_elapsed(elapsed)}")
            self._scroll_to_bottom()
            return

        if event == "complete":
            self._show_complete(payload if isinstance(payload, dict) else {})
            return

        if event == "fail":
            self._show_fail(str(payload))

    def _show_complete(self, summary: Dict[str, Any]) -> None:
        self._stop_spinner()
        self.status_var.set("Report generation complete")
        self.progress_text.set("100% complete")
        self.progress_fill.configure(bg=SUCCESS)
        self.progress_fill.place_configure(relwidth=1.0)
        elapsed = float(summary.get("elapsed", 0.0))
        self.elapsed_var.set(f"Total time: {_format_elapsed(elapsed)}")

        self.complete_panel.pack(fill="x", pady=(12, 0))
        self.complete_title = tk.Label(
            self.complete_panel,
            text="\u2713  REPORT READY",
            bg=self._theme["success_bg"],
            fg=SUCCESS,
            font=("Helvetica", 14, "bold"),
        )
        self.complete_title.pack(anchor="w", padx=16, pady=(12, 4))
        self._complete_labels.clear()
        success_fg = self._theme["success_text"]
        lines = [
            f"Overall progress: {summary.get('progress_percentage', 'N/A')}%",
            f"Structural: {summary.get('structural_progress_percentage', 'N/A')}%  |  "
            f"Architectural: {summary.get('architectural_progress_percentage', 'N/A')}%",
            f"Current phase: {summary.get('current_phase', 'N/A')}",
            f"PDF saved: {summary.get('pdf_path', 'N/A')}",
            f"Completed in {_format_elapsed(elapsed)}",
        ]
        for line in lines:
            label = tk.Label(
                self.complete_panel,
                text=line,
                bg=self._theme["success_bg"],
                fg=success_fg,
                font=("Helvetica", 10),
                anchor="w",
            )
            label.pack(anchor="w", padx=16, pady=1)
            self._complete_labels.append(label)
        tk.Label(self.complete_panel, text="", bg=self._theme["success_bg"]).pack(pady=6)

        self._close_button = tk.Button(
            self.root,
            text="Close",
            bg=self._theme["button_bg"],
            fg=self._theme["button_fg"],
            activebackground=self._theme["button_active"],
            activeforeground=self._theme["button_fg"],
            font=("Helvetica", 10, "bold"),
            padx=18,
            pady=8,
            command=self._on_close,
        )
        self._close_button.pack(pady=(0, 16))

    def _show_fail(self, message: str) -> None:
        self._stop_spinner()
        self.status_var.set("Report generation failed")
        self.progress_fill.configure(bg="#DC2626")
        self._error_label = tk.Label(
            self.scroll_inner,
            text=f"Error: {message}",
            bg=self._theme["error_bg"],
            fg=self._theme["error_fg"],
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=10,
        )
        self._error_label.pack(fill="x", padx=8, pady=12)
        self.exit_code = 1
        self._close_button = tk.Button(
            self.root,
            text="Close",
            bg=self._theme["button_bg"],
            fg=self._theme["button_fg"],
            activebackground=self._theme["button_active"],
            activeforeground=self._theme["button_fg"],
            font=("Helvetica", 10, "bold"),
            padx=18,
            pady=8,
            command=self._on_close,
        )
        self._close_button.pack(pady=(0, 16))

    def _poll_events(self) -> None:
        if self._tracker is None:
            self._poll_job = self.root.after(80, self._poll_events)
            return
        try:
            while True:
                event, payload = self._tracker._events.get_nowait()
                self._handle_event(event, payload)
        except queue.Empty:
            pass
        self._poll_job = self.root.after(80, self._poll_events)

    def run(self) -> int:
        self._poll_job = self.root.after(80, self._poll_events)
        self.root.mainloop()
        return self.exit_code


def _format_elapsed(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def gui_available() -> bool:
    if not os.getenv("DISPLAY") and not sys.platform.startswith("win"):
        return False
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except tk.TclError:
        return False


def run_with_gui(
    job: Callable[[ReportProgressTracker], int],
    *,
    total_steps: int,
    icon_path: str = DEFAULT_GUI_ICON,
    logo_path: str = DEFAULT_GUI_LOGO,
    initial_theme: str = "light",
) -> int:
    """Run report job on a worker thread while the GUI main loop is active."""
    tracker = ReportProgressTracker(total_steps=total_steps)
    gui = ReportProgressGUI(
        icon_path=icon_path,
        logo_path=logo_path,
        initial_theme=initial_theme,
    )
    tracker.bind_gui(gui)
    result: Dict[str, int] = {"code": 1}

    def worker() -> None:
        try:
            result["code"] = job(tracker)
        except Exception as exc:
            tracker.fail(str(exc))
            result["code"] = 1

    thread = threading.Thread(target=worker, name="report-worker", daemon=True)
    thread.start()
    code = gui.run()
    thread.join(timeout=2.0)
    return code if code != 0 else result["code"]
