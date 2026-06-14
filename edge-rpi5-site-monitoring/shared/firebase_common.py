"""
Shared Firebase helpers for Construct Eye Pi scripts.

Collections:
  - devices (doc ID = device serial/UUID)
  - notifications
  - users (read fcmToken where projects array contains the site project id; role filters push)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from firebase_admin import firestore

log = logging.getLogger("firebase_common")

# --- Project root (repo root: parent of shared/) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Static project / site configuration (override via environment) ---
# CONSTRUCT_EYE_PROJECT_ID: numeric Firestore project id used in devices/notifications/users
PROJECT_ID = int(os.getenv("CONSTRUCT_EYE_PROJECT_ID", "0"))
# SITE_NAME: human-readable label shown in the mobile app and cloud records
SITE_NAME = os.getenv("SITE_NAME", "YOUR_SITE_NAME")
# DEVICE_LOCATION: fallback address label when GPS/IP geolocation is unavailable
DEVICE_LOCATION = os.getenv("DEVICE_LOCATION", "YOUR_CITY, YOUR_COUNTRY")
# FALLBACK_LATITUDE / FALLBACK_LONGITUDE: default map position when auto-detect fails
FALLBACK_LATITUDE = float(os.getenv("FALLBACK_LATITUDE", "0.0"))
FALLBACK_LONGITUDE = float(os.getenv("FALLBACK_LONGITUDE", "0.0"))
FALLBACK_CITY = os.getenv("FALLBACK_CITY", "YOUR_CITY")
FALLBACK_COUNTRY = os.getenv("FALLBACK_COUNTRY", "YOUR_COUNTRY")
WEATHER_UPDATE_INTERVAL_S = int(os.getenv("WEATHER_UPDATE_INTERVAL_S", str(30 * 60)))

# Optional manual override via env (leave unset for auto-detect on the Pi)
_ENV_LAT = os.getenv("DEVICE_LATITUDE", "").strip()
_ENV_LON = os.getenv("DEVICE_LONGITUDE", "").strip()
DEVICE_LATITUDE: Optional[float] = float(_ENV_LAT) if _ENV_LAT else None
DEVICE_LONGITUDE: Optional[float] = float(_ENV_LON) if _ENV_LON else None

COLLECTION_DEVICES = "devices"
COLLECTION_NOTIFICATIONS = "notifications"
COLLECTION_USERS = "users"

NOTIFICATION_TYPE_PPE_VIOLATION = "ppe_violation"
NOTIFICATION_TYPE_CONSTRUCTION_REPORT = "construction_report"

ROLE_OWNER = "owner"
ROLE_ENGINEER = "engineer"

DEVICE_ID_FILE = PROJECT_ROOT / ".device_id"

# WMO weather interpretation codes (Open-Meteo)
_WMO_DESCRIPTIONS: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def get_or_create_device_id(explicit: Optional[str] = None) -> str:
    """Return stable device document ID (serial, env, or persisted UUID)."""
    if explicit:
        return explicit.strip()
    env_id = os.getenv("DEVICE_ID", "").strip()
    if env_id:
        return env_id
    if DEVICE_ID_FILE.exists():
        stored = DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    new_id = str(uuid.uuid4())
    try:
        DEVICE_ID_FILE.write_text(new_id, encoding="utf-8")
    except OSError as exc:
        log.warning("Could not persist device id file: %s", exc)
    return new_id


def _weather_description(code: int) -> str:
    return _WMO_DESCRIPTIONS.get(code, "Unknown conditions")


class ResolvedLocation:
    """Device position with city-level and neighbourhood-level address parts."""

    __slots__ = (
        "latitude",
        "longitude",
        "label",
        "label_short",
        "city",
        "region",
        "country",
        "source",
        "address_details",
    )

    def __init__(
        self,
        latitude: float,
        longitude: float,
        label: str,
        *,
        label_short: str = "",
        city: str = "",
        region: str = "",
        country: str = "",
        source: str = "auto",
        address_details: Optional[Dict[str, str]] = None,
    ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.label = label
        self.label_short = label_short or _format_short_label(city, region, country)
        self.city = city
        self.region = region
        self.country = country
        self.source = source
        self.address_details = address_details or {}

    def to_details(self) -> Dict[str, Any]:
        details = {
            "city": self.city,
            "region": self.region,
            "governorate": self.region,
            "country": self.country,
            "source": self.source,
            "label": self.label,
            "label_short": self.label_short,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }
        details.update(self.address_details)
        return details


def _dedupe_parts(parts: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for part in parts:
        cleaned = (part or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _format_short_label(city: str, region: str, country: str) -> str:
    parts = _dedupe_parts([city, country])
    if not parts:
        return DEVICE_LOCATION
    if city and country:
        return f"{city}, {country}"
    return ", ".join(parts)


def _format_detailed_label(
    *,
    neighbourhood: str = "",
    suburb: str = "",
    district: str = "",
    city: str = "",
    region: str = "",
    country: str = "",
) -> str:
    """Build a granular label: neighbourhood/suburb/district + city + country."""
    local = _dedupe_parts([neighbourhood, suburb, district])
    city_norm, region_norm, country_norm = _normalize_locality(
        city, region, country, district=district, suburb=suburb or neighbourhood,
    )
    parts = _dedupe_parts(local + [city_norm, country_norm])
    if not parts:
        return DEVICE_LOCATION
    return ", ".join(parts)


def _mentions_giza(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return any(
        token in blob
        for token in ("giza", "gîza", "gizah", "al jizah", "al-jizah", "el giza", "الجيزة")
    )


def _normalize_locality(
    city: str,
    region: str,
    country: str,
    *,
    district: str = "",
    suburb: str = "",
) -> tuple[str, str, str]:
    """
    Prefer specific districts (e.g. Giza) over broad metro labels (e.g. Cairo).
    Common when IP APIs report 'Cairo' for addresses in Giza Governorate.
    """
    district = (district or "").strip()
    suburb = (suburb or "").strip()
    city = (city or "").strip()
    region = (region or "").strip()
    country = (country or "").strip()

    if _mentions_giza(district, suburb, city, region):
        return "Giza", region or "Giza Governorate", country

    if city.lower() == "cairo" and _mentions_giza(region, district, suburb):
        return "Giza", region, country

    if not city and _mentions_giza(region):
        return "Giza", region, country

    return city, region, country


def _resolved_from_parts(
    lat: float,
    lon: float,
    city: str,
    region: str,
    country: str,
    source: str,
    *,
    district: str = "",
    suburb: str = "",
    neighbourhood: str = "",
    postcode: str = "",
    road: str = "",
    display_name: str = "",
    extra: Optional[Dict[str, str]] = None,
) -> ResolvedLocation:
    city, region, country = _normalize_locality(
        city, region, country, district=district, suburb=suburb or neighbourhood,
    )
    address_details = {
        "neighbourhood": (neighbourhood or "").strip(),
        "suburb": (suburb or "").strip(),
        "district": (district or "").strip(),
        "postcode": (postcode or "").strip(),
        "road": (road or "").strip(),
        "display_name": (display_name or "").strip(),
    }
    if extra:
        for key, value in extra.items():
            if value:
                address_details[key] = str(value).strip()

    detailed = _format_detailed_label(
        neighbourhood=address_details["neighbourhood"],
        suburb=address_details["suburb"],
        district=address_details["district"],
        city=city,
        region=region,
        country=country,
    )
    return ResolvedLocation(
        lat,
        lon,
        detailed,
        label_short=_format_short_label(city, region, country),
        city=city,
        region=region,
        country=country,
        source=source,
        address_details=address_details,
    )


def _locality_score(loc: ResolvedLocation) -> int:
    score = 0
    if _mentions_giza(loc.city, loc.region):
        score += 20
    if loc.city and loc.city.lower() != "cairo":
        score += 5
    if loc.city.lower() == "cairo" and not _mentions_giza(loc.region):
        score -= 3
    for key in ("neighbourhood", "suburb", "district", "road", "display_name"):
        if loc.address_details.get(key):
            score += 4
    return score


def _pick_best_location(candidates: List[ResolvedLocation]) -> Optional[ResolvedLocation]:
    if not candidates:
        return None
    ranked = sorted(candidates, key=_locality_score, reverse=True)
    best = ranked[0]
    lat = sum(c.latitude for c in candidates) / len(candidates)
    lon = sum(c.longitude for c in candidates) / len(candidates)

    merged_details: Dict[str, str] = {}
    for loc in ranked:
        for key, value in loc.address_details.items():
            if value and key not in merged_details:
                merged_details[key] = value

    return ResolvedLocation(
        lat,
        lon,
        best.label,
        label_short=best.label_short,
        city=best.city,
        region=best.region,
        country=best.country,
        source=best.source,
        address_details=merged_details,
    )


def _try_gps_location() -> Optional[ResolvedLocation]:
    """Read lat/lon from gpsd/gpspipe when a GPS receiver is attached."""
    try:
        proc = subprocess.run(
            ["gpspipe", "-w", "-n", "8"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("class") not in ("TPV", "POSITION"):
            continue
        lat = payload.get("lat")
        lon = payload.get("lon")
        if lat is None or lon is None:
            continue
        if abs(float(lat)) < 0.01 and abs(float(lon)) < 0.01:
            continue
        return ResolvedLocation(
            float(lat),
            float(lon),
            "GPS fix",
            label_short="GPS fix",
            source="gps",
        )
    return None


def _try_ip_geolocation_ip_api() -> Optional[ResolvedLocation]:
    try:
        response = requests.get(
            "http://ip-api.com/json/",
            params={
                "fields": "status,message,country,regionName,city,district,zip,lat,lon",
            },
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            return None
        lat, lon = data.get("lat"), data.get("lon")
        if lat is None or lon is None:
            return None
        return _resolved_from_parts(
            float(lat),
            float(lon),
            str(data.get("city") or ""),
            str(data.get("regionName") or ""),
            str(data.get("country") or ""),
            "ip-api",
            district=str(data.get("district") or ""),
            postcode=str(data.get("zip") or ""),
        )
    except Exception as exc:
        log.debug("ip-api geolocation failed: %s", exc)
        return None


def _try_ip_geolocation_ipwho() -> Optional[ResolvedLocation]:
    try:
        response = requests.get("https://ipwho.is/", timeout=12)
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            return None
        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is None or lon is None:
            return None
        return _resolved_from_parts(
            float(lat),
            float(lon),
            str(data.get("city") or ""),
            str(data.get("region") or ""),
            str(data.get("country") or ""),
            "ipwho",
            postcode=str(data.get("postal") or data.get("postcode") or ""),
        )
    except Exception as exc:
        log.debug("ipwho geolocation failed: %s", exc)
        return None


def _try_ip_geolocation_ipapi_co() -> Optional[ResolvedLocation]:
    try:
        response = requests.get("https://ipapi.co/json/", timeout=12)
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            return None
        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is None or lon is None:
            return None
        return _resolved_from_parts(
            float(lat),
            float(lon),
            str(data.get("city") or ""),
            str(data.get("region") or ""),
            str(data.get("country_name") or ""),
            "ipapi.co",
            postcode=str(data.get("postal") or ""),
        )
    except Exception as exc:
        log.debug("ipapi.co geolocation failed: %s", exc)
        return None


def _try_ip_geolocation() -> Optional[ResolvedLocation]:
    """Query multiple IP geolocation providers and pick the best locality match."""
    providers = (
        _try_ip_geolocation_ipwho,
        _try_ip_geolocation_ipapi_co,
        _try_ip_geolocation_ip_api,
    )
    candidates: List[ResolvedLocation] = []
    for provider in providers:
        result = provider()
        if result is not None:
            candidates.append(result)

    merged = _pick_best_location(candidates)
    if merged is not None:
        merged.source = "ip"
        log.info(
            "IP geolocation merged %s provider(s): %s (%.4f, %.4f)",
            len(candidates),
            merged.label,
            merged.latitude,
            merged.longitude,
        )
    return merged


def _reverse_geocode_open_meteo(latitude: float, longitude: float) -> Optional[ResolvedLocation]:
    try:
        response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/reverse",
            params={"latitude": latitude, "longitude": longitude, "language": "en"},
            timeout=12,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            return None
        top = results[0]
        return _resolved_from_parts(
            latitude,
            longitude,
            str(top.get("name") or ""),
            str(top.get("admin1") or ""),
            str(top.get("country") or ""),
            "open_meteo",
        )
    except Exception as exc:
        log.debug("Open-Meteo reverse geocode failed: %s", exc)
        return None


def _parse_nominatim_address(
    latitude: float,
    longitude: float,
    data: Dict[str, Any],
    *,
    zoom: int,
) -> ResolvedLocation:
    address = data.get("address") or {}
    city = str(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or ""
    )
    return _resolved_from_parts(
        latitude,
        longitude,
        city,
        str(address.get("state") or address.get("region") or ""),
        str(address.get("country") or ""),
        "nominatim",
        district=str(address.get("city_district") or address.get("district") or address.get("borough") or ""),
        suburb=str(address.get("suburb") or address.get("quarter") or ""),
        neighbourhood=str(address.get("neighbourhood") or address.get("hamlet") or address.get("residential") or ""),
        postcode=str(address.get("postcode") or ""),
        road=str(address.get("road") or address.get("pedestrian") or address.get("footway") or ""),
        display_name=str(data.get("display_name") or ""),
        extra={
            "county": str(address.get("county") or ""),
            "state_district": str(address.get("state_district") or ""),
            "geocode_zoom": str(zoom),
        },
    )


def _reverse_geocode_nominatim(latitude: float, longitude: float) -> Optional[ResolvedLocation]:
    """OpenStreetMap reverse geocode at neighbourhood/street zoom for granular labels."""
    best: Optional[ResolvedLocation] = None
    best_score = -1
    for index, zoom in enumerate((16, 14, 12)):
        if index > 0:
            time.sleep(1.1)
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "json",
                    "addressdetails": 1,
                    "zoom": zoom,
                },
                headers={"User-Agent": "ConstructEye-Pi/1.0 (site-weather)"},
                timeout=12,
            )
            response.raise_for_status()
            candidate = _parse_nominatim_address(
                latitude, longitude, response.json(), zoom=zoom,
            )
            score = _locality_score(candidate)
            if score > best_score:
                best = candidate
                best_score = score
        except Exception as exc:
            log.debug("Nominatim reverse geocode failed at zoom %s: %s", zoom, exc)
    return best


def _reverse_geocode(
    latitude: float,
    longitude: float,
    hint: Optional[ResolvedLocation] = None,
) -> Optional[ResolvedLocation]:
    """Merge reverse-geocode providers; prefer Giza when hinted by IP/GPS."""
    candidates: List[ResolvedLocation] = []
    if hint is not None:
        candidates.append(hint)
    for fn in (_reverse_geocode_nominatim, _reverse_geocode_open_meteo):
        result = fn(latitude, longitude)
        if result is not None:
            candidates.append(result)

    merged = _pick_best_location(candidates)
    if merged is None:
        return None
    merged.source = "reverse_geocode"
    return merged


def detect_device_location(
    *,
    manual_latitude: Optional[float] = None,
    manual_longitude: Optional[float] = None,
    manual_label: Optional[str] = None,
) -> ResolvedLocation:
    """
    Resolve where the Pi is right now.

    Priority: CLI/env manual coords → GPS → IP geolocation → reverse geocode → Giza fallback.
    """
    env_label = os.getenv("DEVICE_LOCATION", "").strip()

    if manual_latitude is not None and manual_longitude is not None:
        refined = _reverse_geocode(manual_latitude, manual_longitude)
        if refined and not manual_label and not env_label:
            refined.source = "manual"
            return refined
        label = manual_label or env_label or DEVICE_LOCATION
        return ResolvedLocation(
            manual_latitude,
            manual_longitude,
            label,
            source="manual",
        )

    if DEVICE_LATITUDE is not None and DEVICE_LONGITUDE is not None:
        refined = _reverse_geocode(DEVICE_LATITUDE, DEVICE_LONGITUDE)
        if refined:
            refined.source = "env"
            if env_label:
                refined.label = env_label
            return refined
        label = env_label or DEVICE_LOCATION
        return ResolvedLocation(
            DEVICE_LATITUDE,
            DEVICE_LONGITUDE,
            label,
            source="env",
        )

    gps = _try_gps_location()
    if gps is not None:
        refined = _reverse_geocode(gps.latitude, gps.longitude, hint=gps)
        if refined:
            refined.source = "gps"
            return refined
        return gps

    ip_loc = _try_ip_geolocation()
    if ip_loc is not None:
        refined = _reverse_geocode(ip_loc.latitude, ip_loc.longitude, hint=ip_loc)
        if refined:
            refined.source = "ip"
            return refined
        return ip_loc

    log.warning("Location auto-detect failed; using fallback %s", DEVICE_LOCATION)
    return ResolvedLocation(
        FALLBACK_LATITUDE,
        FALLBACK_LONGITUDE,
        DEVICE_LOCATION,
        city=FALLBACK_CITY,
        country=FALLBACK_COUNTRY,
        source="fallback",
    )


def fetch_current_weather(
    resolved: ResolvedLocation,
) -> Optional[Dict[str, Any]]:
    """Fetch current weather from Open-Meteo (no API key required)."""
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": resolved.latitude,
                "longitude": resolved.longitude,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=15,
        )
        response.raise_for_status()
        current = response.json().get("current") or {}
        code = int(current.get("weather_code", -1))
        description = _weather_description(code)
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        temp_str = f"{temp:.0f}°C" if temp is not None else "N/A"
        summary = f"{description}, {temp_str} in {resolved.label_short or resolved.label}"
        return {
            "summary": summary,
            "description": description,
            "temperature_c": temp,
            "humidity_pct": humidity,
            "wind_kmh": wind,
            "weather_code": code,
            "location_label": resolved.label,
            "location_label_short": resolved.label_short,
            "latitude": resolved.latitude,
            "longitude": resolved.longitude,
        }
    except Exception as exc:
        log.error("Weather fetch failed: %s", exc)
        return None


def update_device_weather(
    db: "firestore.Client",
    device_id: str,
    *,
    manual_latitude: Optional[float] = None,
    manual_longitude: Optional[float] = None,
    manual_label: Optional[str] = None,
    on_location_resolved: Optional[Callable[[ResolvedLocation], None]] = None,
) -> bool:
    """Detect device location, fetch weather, and write everything to devices/{device_id}."""
    resolved = detect_device_location(
        manual_latitude=manual_latitude,
        manual_longitude=manual_longitude,
        manual_label=manual_label,
    )
    weather = fetch_current_weather(resolved)
    if weather is None:
        return False

    if on_location_resolved is not None:
        on_location_resolved(resolved)

    try:
        from firebase_admin import firestore as fs
    except ImportError:
        return False

    payload: Dict[str, Any] = {
        "location": resolved.label,
        "location_short": resolved.label_short,
        "location_lat": resolved.latitude,
        "location_lon": resolved.longitude,
        "location_details": resolved.to_details(),
        "weather": weather,
        "weather_summary": weather["summary"],
        "weather_updated_at": fs.SERVER_TIMESTAMP,
        "weather_updated_iso": datetime.now(timezone.utc).isoformat(),
    }
    db.collection(COLLECTION_DEVICES).document(device_id).set(payload, merge=True)
    log.info(
        "Device weather updated: %s - %s (%.4f, %.4f via %s)",
        device_id,
        weather["summary"],
        resolved.latitude,
        resolved.longitude,
        resolved.source,
    )
    return True


class DeviceWeatherUpdater:
    """Background thread: re-detect location + refresh weather every 30 minutes."""

    def __init__(
        self,
        db: "firestore.Client",
        device_id: str,
        *,
        manual_latitude: Optional[float] = None,
        manual_longitude: Optional[float] = None,
        manual_label: Optional[str] = None,
        interval_s: int = WEATHER_UPDATE_INTERVAL_S,
        on_location_resolved: Optional[Callable[[ResolvedLocation], None]] = None,
    ) -> None:
        self._db = db
        self._device_id = device_id
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self._manual_label = manual_label
        self._interval_s = max(60, interval_s)
        self._on_location_resolved = on_location_resolved
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="device-weather", daemon=True)
        self._thread.start()
        log.info(
            "Weather updater started (every %ds, auto-locate) for %s",
            self._interval_s,
            self._device_id,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            update_device_weather(
                self._db,
                self._device_id,
                manual_latitude=self._manual_latitude,
                manual_longitude=self._manual_longitude,
                manual_label=self._manual_label,
                on_location_resolved=self._on_location_resolved,
            )
            if self._stop.wait(self._interval_s):
                break


def register_device(
    db: "firestore.Client",
    *,
    device_id: str,
    stream_link: str,
    site_name: str = SITE_NAME,
    resolved: Optional[ResolvedLocation] = None,
    project_id: int = PROJECT_ID,
) -> None:
    """Upsert devices/{device_id} with project and stream metadata."""
    payload: Dict[str, Any] = {
        "project_id": project_id,
        "site_name": site_name,
        "stream_link": stream_link,
    }
    if resolved is not None:
        payload.update(
            {
                "location": resolved.label,
                "location_lat": resolved.latitude,
                "location_lon": resolved.longitude,
                "location_details": resolved.to_details(),
            }
        )
    db.collection(COLLECTION_DEVICES).document(device_id).set(payload, merge=True)
    log.info("Device registered: %s (project_id=%s)", device_id, project_id)


def create_notification(
    db: "firestore.Client",
    *,
    title: str,
    body: str,
    project_id: int = PROJECT_ID,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Write notifications collection document (strict schema + optional extra metadata).

    Core fields: project_id, title, body, handle_status, read_by, timestamp.
    Per-user read state lives in read_by[userId] (ISO timestamp); do not use a
    shared is_read flag — one user marking read must not affect other users.
    """
    try:
        from firebase_admin import firestore as fs
    except ImportError as exc:
        raise RuntimeError("firebase_admin is required") from exc

    doc: Dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "body": body,
        "handle_status": False,
        "read_by": {},
        "timestamp": fs.SERVER_TIMESTAMP,
    }
    if extra:
        doc.update(extra)

    _, doc_ref = db.collection(COLLECTION_NOTIFICATIONS).add(doc)
    log.info("Notification created: %s - %s", doc_ref.id, title)
    return doc_ref.id


def user_receives_push_for_notification(
    user_data: Dict[str, Any],
    notification_type: Optional[str],
) -> bool:
    """
    Role-based push routing:
      - owner: construction progress reports only
      - engineer: all notification types (PPE, idle, fall, reports)
    """
    role = str(user_data.get("role") or "").strip().lower()
    if notification_type == NOTIFICATION_TYPE_CONSTRUCTION_REPORT:
        return role in (ROLE_OWNER, ROLE_ENGINEER)
    if notification_type == NOTIFICATION_TYPE_PPE_VIOLATION:
        return role == ROLE_ENGINEER
    return role == ROLE_ENGINEER


def fetch_fcm_tokens_for_project(
    db: "firestore.Client",
    project_id: int = PROJECT_ID,
    notification_type: Optional[str] = None,
) -> List[str]:
    """Return fcmToken values for project users who should receive this notification type."""
    tokens: List[str] = []
    project_key = str(project_id)
    try:
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter

            query = db.collection(COLLECTION_USERS).where(
                filter=FieldFilter("projects", "array_contains", project_key)
            )
        except ImportError:
            query = db.collection(COLLECTION_USERS).where(
                "projects", "array_contains", project_key
            )
        for snap in query.stream():
            data = snap.to_dict() or {}
            if not user_receives_push_for_notification(data, notification_type):
                continue
            token = data.get("fcmToken") or data.get("fcm_token")
            if token and isinstance(token, str) and token.strip():
                tokens.append(token.strip())
    except Exception as exc:
        log.error("Failed to query users for FCM tokens: %s", exc)
    return tokens


def send_push_notifications(
    *,
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> int:
    """
    Send FCM push to the given tokens. Returns count of successful sends.
    Requires firebase_admin.messaging.
    """
    tokens = list(dict.fromkeys(tokens))
    if not tokens:
        log.info("No FCM tokens for project_id=%s; skipping push", PROJECT_ID)
        return 0

    try:
        from firebase_admin import messaging
    except ImportError:
        log.warning("firebase_admin.messaging unavailable; skipping FCM push")
        return 0

    notification = messaging.Notification(title=title, body=body)
    payload = {str(k): str(v) for k, v in (data or {}).items()}
    success = 0
    # Batch in chunks of 500 (FCM multicast limit)
    chunk_size = 500
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i : i + chunk_size]
        try:
            message = messaging.MulticastMessage(
                notification=notification,
                data=payload,
                tokens=chunk,
            )
            response = messaging.send_each_for_multicast(message)
            success += response.success_count
            if response.failure_count:
                log.info(
                    "FCM partial failure: %s/%s failed in batch "
                    "(stale tokens are normal; users should reopen the app)",
                    response.failure_count,
                    len(chunk),
                )
        except Exception as exc:
            log.error("FCM multicast send failed: %s", exc)
    log.info("FCM sent: %s/%s successful", success, len(tokens))
    return success


def notify_project_users(
    db: "firestore.Client",
    *,
    title: str,
    body: str,
    project_id: int = PROJECT_ID,
    notification_extra: Optional[Dict[str, Any]] = None,
    fcm_data: Optional[Dict[str, str]] = None,
) -> str:
    """
    Create Firestore notification and push to project users (filtered by role).
    Returns the new notification document ID.
    """
    notif_id = create_notification(
        db,
        title=title,
        body=body,
        project_id=project_id,
        extra=notification_extra,
    )
    notification_type = (notification_extra or {}).get("type")
    tokens = fetch_fcm_tokens_for_project(
        db,
        project_id=project_id,
        notification_type=notification_type,
    )
    push_data = dict(fcm_data or {})
    push_data.setdefault("notification_id", notif_id)
    send_push_notifications(tokens=tokens, title=title, body=body, data=push_data)
    return notif_id


def build_ppe_violation_notification(
    missing_items: List[str],
    *,
    is_fallen: bool = False,
    idle_seconds: int = 0,
    person_id: int = 0,
) -> tuple[str, str]:
    """Dynamic title/body for PPE safety violations."""
    items = list(missing_items or [])
    if is_fallen:
        title = "Safety Alert: Fall Detected"
        body = (
            f"AI detected a fall hazard for tracked person #{person_id}. "
            "Immediate site response required."
        )
        return title, body

    if idle_seconds >= 30 and not items:
        title = "Safety Alert: Extended Idle Time"
        body = (
            f"Worker #{person_id} idle for {idle_seconds}s. "
            "Supervisor check recommended."
        )
        return title, body

    if "No Helmet" in items and "No Vest" in items:
        title = "Safety Alert: PPE Violation"
        body = (
            f"Person #{person_id} missing helmet and safety vest. "
            "Corrective action required on site."
        )
    elif "No Helmet" in items:
        title = "Safety Alert: Missing Helmet"
        body = f"Person #{person_id} detected without a safety helmet."
    elif "No Vest" in items:
        title = "Safety Alert: Missing Safety Vest"
        body = f"Person #{person_id} detected without a high-visibility vest."
    else:
        title = "Safety Alert: Site Violation"
        body = (
            f"Person #{person_id}: "
            + (", ".join(items) if items else "PPE compliance issue detected.")
        )
    return title, body


def build_construction_report_notification(
    progress_percentage: float,
    current_phase: str,
    site_image_name: str,
) -> tuple[str, str]:
    """Dynamic title/body when a construction progress report is published."""
    title = "Progress Report Ready"
    body = (
        f"New site analysis for {site_image_name}: "
        f"{progress_percentage:.1f}% complete — phase: {current_phase}."
    )
    return title, body
