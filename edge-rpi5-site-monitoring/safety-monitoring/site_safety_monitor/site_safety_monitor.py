"""
Construct Eye — Site safety monitor (PPE, fall, idle) with MJPEG streaming.

Detects helmet/vest violations (Hailo-8), fall hazards (MediaPipe pose),
and extended idle time (centroid tracking). Serves a live web dashboard
and optionally uploads violations to Firebase.

Endpoints:
  GET  /              Browser dashboard
  GET  /mjpeg         MJPEG stream (~5 FPS)
  GET  /jpg           Single JPEG snapshot
  GET  /health        Health check
  POST /stream/enable  Enable MJPEG streaming
  POST /stream/disable Disable MJPEG streaming
  POST /cloud/enable   Enable Firebase uploads
  POST /cloud/disable  Disable Firebase uploads

Run (Pi 5 with rpicam-vid):
  python3 site_safety_monitor.py --camera 0 --enable-window
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime
import json
import logging
import math
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

_SAFETY_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _SAFETY_ROOT.parent
if str(_PROJECT_ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "shared"))

# Quiet TensorFlow / MediaPipe C++ logs on ARM (must run before mediapipe import).
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")

import cv2
import numpy as np
from aiohttp import web

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage

    _FIREBASE_LIB_PRESENT = True
except ImportError:
    _FIREBASE_LIB_PRESENT = False

from firebase_common import (
    DEVICE_LOCATION,
    PROJECT_ID,
    ResolvedLocation,
    SITE_NAME,
    DeviceWeatherUpdater,
    NOTIFICATION_TYPE_PPE_VIOLATION,
    build_ppe_violation_notification,
    detect_device_location,
    get_or_create_device_id,
    notify_project_users,
    register_device,
)

try:
    from hailo_platform import (
        ConfigureParams,
        FormatType,
        HEF,
        HailoSchedulingAlgorithm,
        HailoStreamInterface,
        InferVStreams,
        InputVStreamParams,
        OutputVStreamParams,
        VDevice,
    )
except ImportError as exc:
    print(f"[CRITICAL] [hailo] hailo_platform import failed: {exc}")
    sys.exit(1)

# ═══════════════════════════════════════ CONFIG ═══════════════════════════════════════

# --- Hailo PPE model ---
PPE_HEF_FILE = str(_SAFETY_ROOT / "models" / "yolov8n.hef")
PPE_INPUT_LAYER = "yolov8n/input_layer1"
PPE_OUTPUT_LAYER = "yolov8n/yolov8_nms_postprocess"

# --- Class IDs (YOLOv8n PPE) ---
CLS_HELMET = 0
CLS_PERSON = 1
CLS_VEST = 2

# --- Detection thresholds ---
CONFIDENCE_THRESHOLD = 0.50
EQUIPMENT_IOU_THRESHOLD = 0.20
MODEL_SIZE = 960
SCALE_FACTOR = 640 / MODEL_SIZE

# --- Violation timing ---
RETENTION_TIME_S = 3.0

# --- Idle detection ---
# Threshold raised to 60px to absorb YOLO bounding-box jitter (typically ±25px)
# on a stationary person — anything under 60px is treated as "not moved".
IDLE_DISTANCE_THRESHOLD_PX = 60
IDLE_ALERT_THRESHOLD_S = 30.0
# EMA alpha for centroid smoothing: 0.25 ≈ average over ~4 frames.
# Lower → smoother but more lag; keep ≥0.15 so genuine movement is still detected quickly.
IDLE_SMOOTH_ALPHA = 0.25

# --- Tracking ---
TRACKER_MAX_DISAPPEARED = 15
TRACKER_MAX_DISTANCE_PX = 250

# --- MediaPipe pose ---
MP_MODEL_COMPLEXITY = 0
MP_MIN_DETECTION_CONFIDENCE = 0.5
MP_MIN_TRACKING_CONFIDENCE = 0.5
MP_KEYPOINT_CONFIDENCE = 0.3
# How many pixels the nose may be *above* the hips and still count as fallen.
# At 1280x720 a standing person's nose-to-hip distance is ~180 px, so 80 px
# gives enough slack for a raised head while lying down without false-positives
# on a crouching/leaning person.
FALL_NOSE_HIP_MARGIN_PX = 80

# --- Camera (Pi 5 native via rpicam-vid subprocess) ---
# IMX708 sensor is natively 16:9 (1536x864).
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
# 30fps — the background reader drops frames so the processing loop is
# never blocked; we always get the freshest frame.
CAMERA_FRAMERATE = 30
CAMERA_WARMUP_S = 2.0
CAMERA_READ_FAIL_LOG_INTERVAL_S = 5.0

# --- Pose estimation (MediaPipe CPU) ---
# Running at 320x180 every 3rd frame costs ~3 ms amortised — far less
# CPU than the previous 640x360 every 2nd frame, and produces correct
# skeletons including eyes and face landmarks.
POSE_PROCESS_WIDTH = 320
POSE_PROCESS_HEIGHT = 180
POSE_EVERY_N_FRAMES = 3        # run MediaPipe once, reuse result 2 frames

# --- Local violation storage ---
SNAPSHOT_DIR = str(_SAFETY_ROOT / "output" / "violation_images")
JSON_DIR = str(_SAFETY_ROOT / "output" / "violation_logs")

# --- Dashboard colors (BGR) ---
COLOR_SAFE = (0, 255, 0)
COLOR_UNSAFE = (0, 0, 255)
COLOR_WARNING = (0, 255, 255)
COLOR_IDLE = (0, 165, 255)  # orange
COLOR_HELMET = (255, 255, 0)
COLOR_VEST = (255, 165, 0)
COLOR_BLACK_BG = (0, 0, 0)
COLOR_SKELETON_LINE = (255, 0, 0)
COLOR_SKELETON_JOINT = (0, 255, 255)

# --- MJPEG streaming ---
MJPEG_FPS_SLEEP_S = 0.2   # ~5 FPS over the network
MJPEG_JPEG_QUALITY = 35   # lower = smaller payload = less latency
MJPEG_STREAM_WIDTH = 640  # half resolution for the web stream only
MJPEG_STREAM_HEIGHT = 360
SNAPSHOT_JPEG_QUALITY = 85  # local violation snapshots stay full quality

# --- OpenCV window ---
WINDOW_NAME = "Construct Eye Dashboard"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# --- Firebase defaults ---
DEFAULT_FIREBASE_KEY = None
DEFAULT_FIREBASE_BUCKET = None
FIREBASE_LOCATION = SITE_NAME
DEFAULT_STREAM_LINK = os.getenv("STREAM_LINK", "http://127.0.0.1:8081/mjpeg")

# --- FPS calculation ---
FPS_SAMPLE_FRAMES = 10

# --- Skeleton connections (COCO-17) ---
SKELETON_CONNECTIONS: List[Tuple[int, int]] = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
]

# MediaPipe landmark index mapping to COCO-17 skeleton indices
MP_TO_COCO: Dict[int, Any] = {}

# ═══════════════════════════════ SHARED STATE ═══════════════════════════════════════

_latest_frame: Optional[np.ndarray] = None
_latest_frame_lock = threading.Lock()
_server_started_at = time.time()
_shutdown_event = threading.Event()
_stream_enabled = threading.Event()
_cloud_enabled = threading.Event()

log = logging.getLogger("ppe")

_mp_module: Any = None


@contextlib.contextmanager
def _suppress_native_stderr() -> Any:
    """Hide harmless cpuinfo / TFLite / MediaPipe stderr on Raspberry Pi ARM."""
    try:
        stderr_fd = sys.stderr.fileno()
        saved_fd = os.dup(stderr_fd)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, stderr_fd)
        os.close(devnull_fd)
        try:
            yield
        finally:
            os.dup2(saved_fd, stderr_fd)
            os.close(saved_fd)
    except OSError:
        yield


def _get_mediapipe() -> Any:
    """Lazy-load mediapipe so native stderr can be suppressed during import."""
    global _mp_module
    if _mp_module is None:
        with _suppress_native_stderr():
            import mediapipe as mp

        _mp_module = mp
    return _mp_module


def _configure_logging(level_name: str) -> None:
    """Configure root logging with [LEVEL] [MODULE] format."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] [%(name)s] %(message)s",
        force=True,
    )
    for logger_name in (
        "tensorflow",
        "tensorboard",
        "absl",
        "mediapipe",
        "hailo_platform",
    ):
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def _ensure_output_dirs() -> None:
    """Create local snapshot and JSON directories if missing."""
    for directory in (SNAPSHOT_DIR, JSON_DIR):
        os.makedirs(directory, exist_ok=True)


def _init_mp_landmark_map() -> None:
    """Populate MediaPipe-to-COCO landmark mapping once at import."""
    global MP_TO_COCO
    if MP_TO_COCO:
        return
    pl = _get_mediapipe().solutions.pose.PoseLandmark
    MP_TO_COCO = {
        0: pl.NOSE,
        1: pl.LEFT_EYE_INNER,
        2: pl.RIGHT_EYE_INNER,
        3: pl.LEFT_EAR,
        4: pl.RIGHT_EAR,
        5: pl.LEFT_SHOULDER,
        6: pl.RIGHT_SHOULDER,
        7: pl.LEFT_ELBOW,
        8: pl.RIGHT_ELBOW,
        9: pl.LEFT_WRIST,
        10: pl.RIGHT_WRIST,
        11: pl.LEFT_HIP,
        12: pl.RIGHT_HIP,
        13: pl.LEFT_KNEE,
        14: pl.RIGHT_KNEE,
        15: pl.LEFT_ANKLE,
        16: pl.RIGHT_ANKLE,
    }


def _set_latest_frame(frame_bgr: np.ndarray) -> None:
    """Store the most recent annotated frame for HTTP streaming."""
    global _latest_frame
    with _latest_frame_lock:
        _latest_frame = frame_bgr.copy()


def _get_latest_frame_copy() -> Optional[np.ndarray]:
    """Return a thread-safe copy of the latest frame, or None."""
    with _latest_frame_lock:
        return None if _latest_frame is None else _latest_frame.copy()


def push_frame(frame_bgr: np.ndarray) -> None:
    """Publish an annotated frame to the shared MJPEG buffer."""
    _set_latest_frame(frame_bgr)


# ═══════════════════════════════ CLOUD UPLOADER ═════════════════════════════════════

class CloudUploader:
    """Non-blocking Firebase Storage + Firestore violation uploader."""

    def __init__(
        self,
        key_path: Optional[str],
        bucket_name: Optional[str],
        *,
        stream_link: str = DEFAULT_STREAM_LINK,
        device_id: Optional[str] = None,
        project_id: int = PROJECT_ID,
        site_name: str = SITE_NAME,
        manual_location_label: Optional[str] = None,
        manual_latitude: Optional[float] = None,
        manual_longitude: Optional[float] = None,
    ) -> None:
        self._log = logging.getLogger("cloud")
        self._initialized = False
        self.db = None
        self.bucket = None
        self.project_id = project_id
        self.site_name = site_name
        self.location = manual_location_label or DEVICE_LOCATION
        self.latitude = 0.0
        self.longitude = 0.0
        self._manual_location_label = manual_location_label
        self._manual_latitude = manual_latitude
        self._manual_longitude = manual_longitude
        self.stream_link = stream_link
        self.device_id = get_or_create_device_id(device_id)
        self.weather_updater: Optional[DeviceWeatherUpdater] = None

        if not _FIREBASE_LIB_PRESENT:
            self._log.warning("firebase_admin not installed; cloud uploads unavailable")
            return
        if not key_path or not bucket_name:
            self._log.info("Firebase credentials not provided; cloud uploads unavailable")
            return
        if not os.path.exists(key_path):
            self._log.error("Service account key not found: %s", key_path)
            return

        try:
            cred = credentials.Certificate(key_path)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
            self.db = firestore.client()
            self.bucket = storage.bucket()
            initial = detect_device_location(
                manual_latitude=self._manual_latitude,
                manual_longitude=self._manual_longitude,
                manual_label=self._manual_location_label,
            )
            self._apply_resolved_location(initial)
            register_device(
                self.db,
                device_id=self.device_id,
                stream_link=self.stream_link,
                site_name=self.site_name,
                resolved=initial,
                project_id=self.project_id,
            )
            self.weather_updater = DeviceWeatherUpdater(
                self.db,
                self.device_id,
                manual_latitude=self._manual_latitude,
                manual_longitude=self._manual_longitude,
                manual_label=self._manual_location_label,
                on_location_resolved=self._apply_resolved_location,
            )
            self.weather_updater.start()
            self._initialized = True
            self._log.info(
                "Connected to Firebase project: %s (device=%s, project_id=%s)",
                cred.project_id,
                self.device_id,
                self.project_id,
            )
        except Exception as exc:
            self._log.error("Firebase init failed: %s", exc)

    def _apply_resolved_location(self, resolved: ResolvedLocation) -> None:
        """Keep in-memory location in sync with auto-detected device position."""
        self.location = resolved.label
        self.latitude = resolved.latitude
        self.longitude = resolved.longitude

    def shutdown(self) -> None:
        """Stop background weather updates."""
        if self.weather_updater is not None:
            self.weather_updater.stop()
            self.weather_updater = None

    @property
    def ready(self) -> bool:
        """True when Firebase SDK is initialized and cloud toggle is on."""
        return self._initialized and _cloud_enabled.is_set()

    def upload_violation(
        self,
        person_id: int,
        missing_items: List[str],
        local_image_path: str,
        *,
        is_fallen: bool = False,
        idle_seconds: int = 0,
    ) -> None:
        """Upload violation snapshot and metadata in a background daemon thread."""
        if not self.ready:
            return

        def _task() -> None:
            try:
                filename = os.path.basename(local_image_path)
                blob = self.bucket.blob(f"violations/{filename}")
                blob.upload_from_filename(local_image_path)
                blob.make_public()
                doc_data = {
                    "person_id": person_id,
                    "project_id": self.project_id,
                    "site_name": self.site_name,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                    "datetime": datetime.datetime.now().isoformat(),
                    "missing_items": missing_items,
                    "image_url": blob.public_url,
                    "status": "OPEN",
                    "location": self.location,
                    "is_fallen": is_fallen,
                    "idle_seconds": idle_seconds,
                }
                _, violation_ref = self.db.collection("violations").add(doc_data)
                violation_id = violation_ref.id

                title, body = build_ppe_violation_notification(
                    missing_items,
                    is_fallen=is_fallen,
                    idle_seconds=idle_seconds,
                    person_id=person_id,
                )
                notify_project_users(
                    self.db,
                    title=title,
                    body=body,
                    project_id=self.project_id,
                    notification_extra={
                        "type": NOTIFICATION_TYPE_PPE_VIOLATION,
                        "violation_id": violation_id,
                        "person_id": person_id,
                        "image_url": blob.public_url,
                        "missing_items": missing_items,
                        "is_fallen": is_fallen,
                        "idle_seconds": idle_seconds,
                    },
                    fcm_data={
                        "type": NOTIFICATION_TYPE_PPE_VIOLATION,
                        "violation_id": violation_id,
                    },
                )
                self._log.info(
                    "Upload success for person ID %s (violation=%s, notification linked)",
                    person_id,
                    violation_id,
                )
            except Exception as exc:
                self._log.error("Upload failed for person ID %s: %s", person_id, exc)

        threading.Thread(target=_task, daemon=True).start()


# ═══════════════════════════════ STICKY TRACKER ═══════════════════════════════════

class StickyTracker:
    """Centroid-based multi-object tracker with violation and idle state."""

    def __init__(
        self,
        max_disappeared: int = TRACKER_MAX_DISAPPEARED,
        max_distance: float = TRACKER_MAX_DISTANCE_PX,
    ) -> None:
        self.next_object_id = 0
        self.objects: OrderedDict[int, Tuple[int, int]] = OrderedDict()
        self.disappeared: OrderedDict[int, int] = OrderedDict()
        self.state_data: OrderedDict[int, Dict[str, Any]] = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid: Tuple[int, int], det_data: Dict[str, Any]) -> None:
        """Register a new tracked person."""
        now = time.time()
        oid = self.next_object_id
        self.objects[oid] = centroid
        self.disappeared[oid] = 0

        is_fallen = det_data.get("is_fallen", False)
        currently_safe = det_data.get("safe", False) and not is_fallen

        if is_fallen:
            status = "VIOLATION"
            violation_start = now
            # Mark uploaded=True immediately so the next frame's _compute_status
            # does not re-trigger the upload.
            uploaded = True
            trigger_upload = True
        elif currently_safe:
            status = "SAFE"
            violation_start = None
            uploaded = False
            trigger_upload = False
        else:
            status = "WARNING"
            violation_start = now
            uploaded = False
            trigger_upload = False

        self.state_data[oid] = {
            "violation_start": violation_start,
            "status_text": status,
            "det_data": det_data,
            "box": det_data["box"],
            "keypoints": det_data.get("keypoints"),
            "is_fallen": is_fallen,
            "idle_start_time": None,
            "idle_duration_s": 0.0,
            "is_idle_alert": False,
            "smooth_centroid": centroid,
            "last_centroid": centroid,
            "last_moved_time": now,
            "uploaded": uploaded,
            "trigger_upload": trigger_upload,
        }
        self.next_object_id += 1

    def deregister(self, object_id: int) -> None:
        """Remove a tracked person that has disappeared."""
        del self.objects[object_id]
        del self.disappeared[object_id]
        del self.state_data[object_id]

    def _compute_status(
        self,
        det: Dict[str, Any],
        old_state: Dict[str, Any],
        now: float,
    ) -> Tuple[str, Optional[float], bool, bool]:
        """Compute violation status, timers, and upload trigger for one person."""
        is_fallen = det.get("is_fallen", False)
        currently_safe = det.get("safe", False) and not is_fallen
        violation_start = old_state.get("violation_start")
        uploaded_flag = old_state.get("uploaded", False)
        trigger_upload = False

        if is_fallen:
            if not uploaded_flag:
                trigger_upload = True
                uploaded_flag = True
            return "VIOLATION", violation_start or now, uploaded_flag, trigger_upload

        if currently_safe:
            # Reset uploaded so a future violation on this same ID triggers a new upload
            return "SAFE", None, False, False

        if violation_start is None:
            return "WARNING", now, uploaded_flag, False

        elapsed = now - violation_start
        if elapsed >= RETENTION_TIME_S:
            if not uploaded_flag:
                trigger_upload = True
                uploaded_flag = True
            return "VIOLATION", violation_start, uploaded_flag, trigger_upload

        countdown = int(RETENTION_TIME_S - elapsed) + 1
        return f"CHECKING {countdown}s", violation_start, uploaded_flag, False

    def update(self, detections: List[Dict[str, Any]]) -> OrderedDict[int, Dict[str, Any]]:
        """Match detections to tracked IDs and update per-person state."""
        if not detections:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.state_data

        input_centroids = np.zeros((len(detections), 2), dtype=int)
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det["box"]
            input_centroids[i] = (int((x1 + x2) / 2), int((y1 + y2) / 2))

        if not self.objects:
            for i in range(len(input_centroids)):
                self.register(tuple(input_centroids[i]), detections[i])
            return self.state_data

        object_ids = list(self.objects.keys())
        object_centroids = list(self.objects.values())

        dist_matrix = np.array([
            [math.hypot(oc[0] - ic[0], oc[1] - ic[1]) for ic in input_centroids]
            for oc in object_centroids
        ])

        if dist_matrix.size == 0:
            return self.state_data

        rows = dist_matrix.min(axis=1).argsort()
        cols = dist_matrix.argmin(axis=1)[rows]
        used_rows: set[int] = set()
        used_cols: set[int] = set()

        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if dist_matrix[row, col] > self.max_distance:
                continue

            object_id = object_ids[row]
            centroid = tuple(input_centroids[col])
            self.objects[object_id] = centroid
            self.disappeared[object_id] = 0

            det = detections[col]
            old_state = self.state_data[object_id]
            now = time.time()

            # ── Idle detection with EMA-smoothed centroid ─────────────────────────
            # Raw centroid jitters ±20-30 px per frame even on a stationary person.
            # We smooth it with an EMA so the comparison is much more stable.
            prev_smooth = old_state.get("smooth_centroid", centroid)
            smooth_centroid = (
                int(IDLE_SMOOTH_ALPHA * centroid[0] + (1 - IDLE_SMOOTH_ALPHA) * prev_smooth[0]),
                int(IDLE_SMOOTH_ALPHA * centroid[1] + (1 - IDLE_SMOOTH_ALPHA) * prev_smooth[1]),
            )

            last_centroid = old_state.get("last_centroid", smooth_centroid)
            idle_start_time = old_state.get("idle_start_time")
            movement = math.hypot(
                smooth_centroid[0] - last_centroid[0],
                smooth_centroid[1] - last_centroid[1],
            )

            if movement > IDLE_DISTANCE_THRESHOLD_PX:
                # Genuine movement — reset the idle timer and store new reference
                last_centroid = smooth_centroid
                idle_start_time = None
            elif idle_start_time is None:
                # Person hasn't exceeded threshold yet — start the idle clock
                idle_start_time = now

            idle_duration_s = 0.0 if idle_start_time is None else (now - idle_start_time)
            is_idle_alert = idle_duration_s >= IDLE_ALERT_THRESHOLD_S

            status_text, violation_start, uploaded_flag, trigger_upload = self._compute_status(
                det, old_state, now
            )

            self.state_data[object_id] = {
                "violation_start": violation_start,
                "status_text": status_text,
                "det_data": det,
                "box": det["box"],
                "keypoints": det.get("keypoints"),
                "is_fallen": det.get("is_fallen", False),
                "idle_start_time": idle_start_time,
                "idle_duration_s": idle_duration_s,
                "is_idle_alert": is_idle_alert,
                "smooth_centroid": smooth_centroid,
                "last_centroid": last_centroid,
                "last_moved_time": now,
                "uploaded": uploaded_flag,
                "trigger_upload": trigger_upload,
            }

            used_rows.add(row)
            used_cols.add(col)

        for row in set(range(dist_matrix.shape[0])) - used_rows:
            oid = object_ids[row]
            self.disappeared[oid] += 1
            if self.disappeared[oid] > self.max_disappeared:
                self.deregister(oid)

        for col in set(range(dist_matrix.shape[1])) - used_cols:
            self.register(tuple(input_centroids[col]), detections[col])

        return self.state_data


# ═══════════════════════════════ DETECTION HELPERS ════════════════════════════════

def pair_equipment(
    persons: List[Dict[str, Any]],
    equipment: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Pair helmet/vest detections to persons via IoU overlap."""
    for person in persons:
        person["has_helmet"] = False
        person["has_vest"] = False
        person["safe"] = False
        person.setdefault("is_fallen", False)

    for equip in equipment:
        best_ratio = 0.0
        best_person: Optional[Dict[str, Any]] = None
        e_box = equip["box"]

        for person in persons:
            p_box = person["box"]
            x_a = max(e_box[0], p_box[0])
            y_a = max(e_box[1], p_box[1])
            x_b = min(e_box[2], p_box[2])
            y_b = min(e_box[3], p_box[3])
            inter_area = max(0, x_b - x_a) * max(0, y_b - y_a)
            equip_area = (e_box[2] - e_box[0]) * (e_box[3] - e_box[1])
            if equip_area <= 0:
                continue
            ratio = inter_area / equip_area
            if ratio > EQUIPMENT_IOU_THRESHOLD and ratio > best_ratio:
                best_ratio = ratio
                best_person = person

        if best_person is None:
            continue
        if equip["cls_id"] == CLS_HELMET:
            best_person["has_helmet"] = True
        elif equip["cls_id"] == CLS_VEST:
            best_person["has_vest"] = True

    for person in persons:
        person["safe"] = person["has_helmet"] and person["has_vest"]
    return persons


def _box_iou(box_a: List[int], box_b: List[int]) -> float:
    """Compute intersection-over-union for two bounding boxes."""
    x_a = max(box_a[0], box_b[0])
    y_a = max(box_a[1], box_b[1])
    x_b = min(box_a[2], box_b[2])
    y_b = min(box_a[3], box_b[3])
    inter_area = max(0, x_b - x_a) * max(0, y_b - y_a)
    area_a = max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1])
    area_b = max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1])
    denom = area_a + area_b - inter_area
    return 0.0 if denom <= 0 else inter_area / denom


def _box_centroid(box: List[int]) -> Tuple[float, float]:
    """Return the center point of a bounding box."""
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def mediapipe_pose_people(
    frame_bgr: np.ndarray,
    pose_results: Any,
) -> List[Dict[str, Any]]:
    """Convert MediaPipe Pose results to internal person dicts with keypoints."""
    if pose_results is None or pose_results.pose_landmarks is None:
        return []

    h, w = frame_bgr.shape[:2]
    landmarks = pose_results.pose_landmarks.landmark
    keypoints = np.zeros((17, 3), dtype=np.float32)
    xs: List[float] = []
    ys: List[float] = []

    for coco_idx, mp_landmark in MP_TO_COCO.items():
        point = landmarks[int(mp_landmark)]
        x_px = float(point.x) * w
        y_px = float(point.y) * h
        conf = float(point.visibility) if hasattr(point, "visibility") else 1.0
        keypoints[coco_idx] = (x_px, y_px, conf)
        if conf > MP_KEYPOINT_CONFIDENCE:
            xs.append(x_px)
            ys.append(y_px)

    if not xs or not ys:
        return []

    x1 = int(max(0, min(w, min(xs))))
    y1 = int(max(0, min(h, min(ys))))
    x2 = int(max(0, min(w, max(xs))))
    y2 = int(max(0, min(h, max(ys))))

    nose_y = float(keypoints[0][1])
    hip_ys = [
        float(keypoints[i][1])
        for i in (11, 12)
        if float(keypoints[i][2]) > MP_KEYPOINT_CONFIDENCE
    ]
    # Fallen when nose is at or below (hip_y - FALL_NOSE_HIP_MARGIN_PX),
    # i.e. the nose may be up to FALL_NOSE_HIP_MARGIN_PX above the hips
    # and still count as fallen — handles a slightly raised head while on the ground.
    is_fallen = bool(hip_ys) and all(nose_y > (hip_y - FALL_NOSE_HIP_MARGIN_PX) for hip_y in hip_ys)

    return [{"box": [x1, y1, x2, y2], "keypoints": keypoints, "is_fallen": is_fallen}]


def pair_fall_status(
    persons: List[Dict[str, Any]],
    pose_people: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge pose keypoints and fall status onto PPE person detections."""
    for person in persons:
        person["is_fallen"] = False
        person["keypoints"] = None

    for pose_person in pose_people:
        best_person: Optional[Dict[str, Any]] = None
        best_iou = 0.0

        for person in persons:
            iou = _box_iou(person["box"], pose_person["box"])
            if iou > best_iou:
                best_iou = iou
                best_person = person

        if best_person is None and persons:
            pose_cx, pose_cy = _box_centroid(pose_person["box"])
            best_person = min(
                persons,
                key=lambda p: math.hypot(
                    _box_centroid(p["box"])[0] - pose_cx,
                    _box_centroid(p["box"])[1] - pose_cy,
                ),
            )

        if best_person is not None:
            best_person["keypoints"] = pose_person.get("keypoints")
            if pose_person.get("is_fallen"):
                best_person["is_fallen"] = True

    return persons


def draw_skeleton(frame: np.ndarray, keypoints: np.ndarray) -> None:
    """Draw COCO-17 skeleton lines and joint circles on the frame."""
    for start_idx, end_idx in SKELETON_CONNECTIONS:
        if (
            keypoints[start_idx][2] > MP_KEYPOINT_CONFIDENCE
            and keypoints[end_idx][2] > MP_KEYPOINT_CONFIDENCE
        ):
            pt1 = (int(keypoints[start_idx][0]), int(keypoints[start_idx][1]))
            pt2 = (int(keypoints[end_idx][0]), int(keypoints[end_idx][1]))
            cv2.line(frame, pt1, pt2, COLOR_SKELETON_LINE, 2)
            cv2.circle(frame, pt1, 4, COLOR_SKELETON_JOINT, -1)


def _build_person_label(
    obj_id: int,
    status_text: str,
    det: Dict[str, Any],
    is_fallen: bool,
    idle_duration_s: float,
    is_idle_alert: bool,
) -> Tuple[str, Tuple[int, int, int]]:
    """Build per-person label text and color."""
    if is_fallen:
        label = f"ID:{obj_id} FALLEN ALERT!"
        color = COLOR_UNSAFE
    elif status_text == "SAFE":
        label = f"ID:{obj_id} SAFE"
        color = COLOR_SAFE
    elif status_text == "WARNING" or "CHECKING" in status_text:
        label = f"ID:{obj_id} {status_text}"
        color = COLOR_WARNING
    elif status_text == "VIOLATION":
        missing = []
        if not det.get("has_helmet"):
            missing.append("No Helmet")
        if not det.get("has_vest"):
            missing.append("No Vest")
        suffix = f" ({', '.join(missing)})" if missing else ""
        label = f"ID:{obj_id} VIOLATION{suffix}"
        color = COLOR_UNSAFE
    else:
        label = f"ID:{obj_id} {status_text}"
        color = COLOR_WARNING

    if is_idle_alert:
        label += f" - IDLE ALERT: {int(idle_duration_s)}s"
        color = COLOR_IDLE

    return label, color


def draw_dashboard(
    frame: np.ndarray,
    tracked_people: Dict[int, Dict[str, Any]],
    equipment: List[Dict[str, Any]],
    fps: float,
) -> np.ndarray:
    """Render PPE dashboard overlay with counts, labels, and alert banners."""
    h, w = frame.shape[:2]

    for item in equipment:
        color = COLOR_HELMET if item["cls_id"] == CLS_HELMET else COLOR_VEST
        x1, y1, x2, y2 = item["box"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    total_people = len(tracked_people)
    violation_count = 0
    any_fallen = False
    any_idle_alert = False

    for obj_id, data in tracked_people.items():
        det = data["det_data"]
        x1, y1, x2, y2 = data.get("box", det["box"])
        status_text = data["status_text"]
        is_fallen = bool(data.get("is_fallen", False))
        idle_duration_s = float(data.get("idle_duration_s", 0.0) or 0.0)
        is_idle_alert = bool(data.get("is_idle_alert", False))

        if is_fallen:
            any_fallen = True
            violation_count += 1
        elif status_text == "VIOLATION":
            violation_count += 1

        if is_idle_alert:
            any_idle_alert = True

        label, label_color = _build_person_label(
            obj_id, status_text, det, is_fallen, idle_duration_s, is_idle_alert
        )
        box_color = COLOR_UNSAFE if is_fallen or status_text == "VIOLATION" else label_color
        if status_text == "SAFE" and not is_idle_alert:
            box_color = COLOR_SAFE
        elif "CHECKING" in status_text or status_text == "WARNING":
            box_color = COLOR_WARNING

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)

        is_alert = is_fallen or status_text == "VIOLATION" or is_idle_alert
        icon_slot = 26 if is_alert else 0   # px reserved left of text for the △ icon

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        label_x1 = x1
        label_y1 = y1 - 25
        label_x2 = x1 + tw + 10 + icon_slot
        cv2.rectangle(frame, (label_x1, label_y1), (label_x2, y1), label_color, -1)

        if is_alert:
            icon_cx = label_x1 + icon_slot // 2
            icon_cy = label_y1 + (y1 - label_y1) // 2
            _draw_alert_icon(frame, icon_cx, icon_cy, size=9, color=(255, 220, 0))

        cv2.putText(
            frame, label, (x1 + 5 + icon_slot, y1 - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2,
        )

        if data.get("keypoints") is not None:
            draw_skeleton(frame, data["keypoints"])

    compliant_count = total_people - violation_count

    panel_w, panel_h = 260, 180
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + panel_w, 10 + panel_h), COLOR_BLACK_BG, -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    y_start = 40
    line_spacing = 30
    cv2.putText(
        frame, "SITE MONITORING", (25, y_start),
        cv2.FONT_HERSHEY_TRIPLEX, 0.6, (255, 255, 255), 1,
    )
    cv2.line(frame, (25, y_start + 8), (25 + panel_w - 30, y_start + 8), (150, 150, 150), 1)
    cv2.putText(
        frame, f"Persons: {total_people}", (25, y_start + 15 + line_spacing),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1,
    )
    cv2.putText(
        frame, f"Compliant: {compliant_count}", (25, y_start + 15 + line_spacing * 2),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_SAFE, 1,
    )
    cv2.putText(
        frame, f"Violations: {violation_count}", (25, y_start + 15 + line_spacing * 3),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_UNSAFE, 1,
    )

    cv2.putText(
        frame, f"FPS: {fps:.1f}", (w - 150, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
    )
    cv2.putText(
        frame, datetime.datetime.now().strftime("%H:%M:%S"), (w - 150, 60),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2,
    )

    banner_y = 80
    if violation_count > 0:
        _draw_banner(frame, w, banner_y, "VIOLATION ALERT", COLOR_UNSAFE)
        banner_y += 60

    if any_fallen:
        _draw_banner(frame, w, banner_y, "FALLEN ALERT", COLOR_UNSAFE)
        banner_y += 60

    if any_idle_alert:
        _draw_banner(frame, w, banner_y, "IDLE ALERT", COLOR_IDLE)

    return frame


def _draw_alert_icon(
    frame: np.ndarray,
    cx: int,
    cy: int,
    size: int,
    color: Tuple[int, int, int] = (255, 220, 0),
) -> None:
    """Draw a filled warning triangle with '!' centred at (cx, cy).

    The triangle points upward (△). A thin black border is drawn around it
    and a black '!' is placed inside so it reads clearly on any background.
    ``size`` is the half-height of the triangle in pixels.
    """
    pts = np.array([
        [cx,          cy - size],          # apex
        [cx - size,   cy + size],          # bottom-left
        [cx + size,   cy + size],          # bottom-right
    ], dtype=np.int32)

    cv2.fillPoly(frame, [pts], color)
    cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 0), thickness=1)

    font_scale = max(0.3, size / 18.0)
    (tw, th), _ = cv2.getTextSize("!", cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
    cv2.putText(
        frame, "!",
        (cx - tw // 2, cy + size // 2 + 1),
        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1, cv2.LINE_AA,
    )


def _draw_banner(
    frame: np.ndarray,
    frame_width: int,
    y_pos: int,
    message: str,
    bg_color: Tuple[int, int, int],
) -> None:
    """Draw a top-right alert banner on the dashboard with a warning icon."""
    (tw, th), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_TRIPLEX, 0.8, 2)
    icon_slot = 36          # pixels reserved on the left of the banner for the icon
    box_h = th + 25
    box_x1 = frame_width - tw - 40 - icon_slot
    box_x2 = frame_width - 10
    box_y2 = y_pos + box_h

    cv2.rectangle(frame, (box_x1, y_pos), (box_x2, box_y2), bg_color, -1)

    icon_cx = box_x1 + icon_slot // 2
    icon_cy = y_pos + box_h // 2
    _draw_alert_icon(frame, icon_cx, icon_cy, size=11, color=(255, 220, 0))

    cv2.putText(
        frame, message, (frame_width - tw - 30, y_pos + th + 10),
        cv2.FONT_HERSHEY_TRIPLEX, 0.8, (255, 255, 255), 2,
    )


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -88.0, 88.0)))


# Cache pre-built anchor grids so they are only computed once per grid size
_anchor_cache: Dict[Tuple[int, int], np.ndarray] = {}


def _make_anchors(gh: int, gw: int) -> np.ndarray:
    """Return (gh*gw, 2) grid centre points in grid-cell units (0.5-based)."""
    key = (gh, gw)
    if key not in _anchor_cache:
        gy, gx = np.mgrid[0:gh, 0:gw]
        _anchor_cache[key] = np.stack(
            [gx.astype(np.float32) + 0.5, gy.astype(np.float32) + 0.5], axis=-1,
        ).reshape(-1, 2)
    return _anchor_cache[key]


def _dfl_decode(pred: np.ndarray, reg_max: int = 16) -> np.ndarray:
    """Decode Distribution Focal Loss box predictions to (l, t, r, b) distances."""
    n = pred.shape[0]
    p = pred.reshape(n, 4, reg_max)
    p = p - p.max(axis=2, keepdims=True)        # numerical stability
    e = np.exp(p)
    soft = e / e.sum(axis=2, keepdims=True)     # softmax over reg_max
    weights = np.arange(reg_max, dtype=np.float32)
    return (soft * weights).sum(axis=2)          # (n, 4)


# Log pose tensor shapes only once at startup
_pose_shape_logged = False


def _parse_pose_detections(
    infer_results: Dict[str, Any],
    frame_shape: Tuple[int, ...],
) -> List[Dict[str, Any]]:
    """Decode 9-head YOLOv8-pose Hailo output into person dicts.

    The model emits 3 groups × 3 tensors per scale:
      conv43/57/70  →  box DFL (1, H, W, 64)
      conv44/58/71  →  objectness (1, H, W, 1)
      conv45/59/72  →  keypoints  (1, H, W, 51)

    Strides: 8 (80×80), 16 (40×40), 32 (20×20) for a 640-input model.
    """
    global _pose_shape_logged
    fh, fw = frame_shape[:2]

    # ── Step 1: group tensors by grid size ──────────────────────────────────
    by_grid: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}
    for name, raw in infer_results.items():
        arr = np.asarray(raw, dtype=np.float32)
        if arr.shape[0] == 1:
            arr = arr[0]        # remove batch dim → (H, W, C)
        if arr.ndim != 3:
            continue
        gh, gw, _ = arr.shape
        by_grid.setdefault((gh, gw), {})[name] = arr

    if not _pose_shape_logged:
        for (gh, gw), tensors in by_grid.items():
            for name, arr in tensors.items():
                log.info(
                    "Pose tensor '%s': grid=%dx%d channels=%d "
                    "range=[%.3f, %.3f]",
                    name, gh, gw, arr.shape[2], arr.min(), arr.max(),
                )
        _pose_shape_logged = True

    # ── Step 2: decode each scale ───────────────────────────────────────────
    candidates: List[Dict[str, Any]] = []

    for (gh, gw), tensors in by_grid.items():
        stride = POSE_MODEL_SIZE // gh          # 8, 16, or 32

        # Identify tensors by channel count
        box_arr = conf_arr = kpt_arr = None
        for arr in tensors.values():
            c = arr.shape[2]
            if c == 1:
                conf_arr = arr
            elif c == POSE_NUM_KEYPOINTS * 3:   # 51
                kpt_arr = arr
            elif c == 64 or c == 4:
                box_arr = arr

        if conf_arr is None or box_arr is None:
            continue

        n = gh * gw
        conf_flat = conf_arr.reshape(n)

        # Sigmoid if values are logits
        if conf_flat.max() > 1.0 or conf_flat.min() < 0.0:
            conf_flat = _sigmoid(conf_flat)

        valid_idx = np.where(conf_flat >= POSE_CONFIDENCE_THRESHOLD)[0]
        if valid_idx.size == 0:
            continue

        anchors = _make_anchors(gh, gw)                   # (n, 2) grid units
        valid_anchors = anchors[valid_idx]
        valid_confs   = conf_flat[valid_idx]
        box_flat      = box_arr.reshape(n, -1)[valid_idx]  # (m, 64 or 4)

        # ── Decode bounding boxes ────────────────────────────────────────
        if box_flat.shape[1] == 64:
            ltrb = _dfl_decode(box_flat)                   # (m, 4) in grid units
            bx1 = np.clip((valid_anchors[:, 0] - ltrb[:, 0]) * stride * fw / POSE_MODEL_SIZE, 0, fw)
            by1 = np.clip((valid_anchors[:, 1] - ltrb[:, 1]) * stride * fh / POSE_MODEL_SIZE, 0, fh)
            bx2 = np.clip((valid_anchors[:, 0] + ltrb[:, 2]) * stride * fw / POSE_MODEL_SIZE, 0, fw)
            by2 = np.clip((valid_anchors[:, 1] + ltrb[:, 3]) * stride * fh / POSE_MODEL_SIZE, 0, fh)
        else:
            # cx, cy, w, h (may be in model-pixel or normalised space)
            cx, cy, bw, bh = (box_flat[:, i] for i in range(4))
            if cx.max() > 1.5:
                cx, cy, bw, bh = cx / POSE_MODEL_SIZE, cy / POSE_MODEL_SIZE, bw / POSE_MODEL_SIZE, bh / POSE_MODEL_SIZE
            bx1 = np.clip((cx - bw / 2) * fw, 0, fw)
            by1 = np.clip((cy - bh / 2) * fh, 0, fh)
            bx2 = np.clip((cx + bw / 2) * fw, 0, fw)
            by2 = np.clip((cy + bh / 2) * fh, 0, fh)

        # ── Decode keypoints ─────────────────────────────────────────────
        kpt_decoded: Optional[np.ndarray] = None
        if kpt_arr is not None:
            kpt_flat = kpt_arr.reshape(n, POSE_NUM_KEYPOINTS * 3)[valid_idx]  # (m, 51)
            kpts = kpt_flat.reshape(-1, POSE_NUM_KEYPOINTS, 3)                # (m, 17, 3)

            kx_raw = kpts[:, :, 0]
            ky_raw = kpts[:, :, 1]
            kv_raw = kpts[:, :, 2]

            # Standard YOLOv8-pose keypoint format (from official PyTorch impl):
            #   kx_final = (tanh(kx_raw) * 2 + anchor_x) * stride
            # The Hailo model outputs raw tanh logits.
            # tensor range [-10.6, 7.8] confirms logit space (tanh clips to ±1).
            kx_px = np.clip(
                (np.tanh(kx_raw) * 2 + valid_anchors[:, 0:1]) * stride * fw / POSE_MODEL_SIZE,
                0, fw,
            )
            ky_px = np.clip(
                (np.tanh(ky_raw) * 2 + valid_anchors[:, 1:2]) * stride * fh / POSE_MODEL_SIZE,
                0, fh,
            )

            # Visibility: always apply sigmoid (raw logits from Hailo)
            kv = _sigmoid(kv_raw)

            kpt_decoded = np.stack(
                [kx_px, ky_px, kv], axis=2,
            ).astype(np.float32)                            # (m, 17, 3)

        # ── Build detection dicts ────────────────────────────────────────
        for i in range(len(valid_idx)):
            ix1, iy1, ix2, iy2 = int(bx1[i]), int(by1[i]), int(bx2[i]), int(by2[i])
            if ix2 <= ix1 or iy2 <= iy1:
                continue

            kps = (
                kpt_decoded[i]
                if kpt_decoded is not None
                else np.zeros((POSE_NUM_KEYPOINTS, 3), dtype=np.float32)
            )
            nose_y = float(kps[0, 1])
            hip_ys = [float(kps[j, 1]) for j in (11, 12) if float(kps[j, 2]) > MP_KEYPOINT_CONFIDENCE]
            is_fallen = bool(hip_ys) and all(nose_y > (hy - FALL_NOSE_HIP_MARGIN_PX) for hy in hip_ys)

            candidates.append({
                "box": [ix1, iy1, ix2, iy2],
                "score": float(valid_confs[i]),
                "keypoints": kps,
                "is_fallen": is_fallen,
            })

    # ── Greedy NMS across all scales ────────────────────────────────────────
    if len(candidates) < 2:
        return candidates
    candidates.sort(key=lambda d: d["score"], reverse=True)
    kept: List[Dict[str, Any]] = []
    suppressed: set = set()
    for i, det in enumerate(candidates):
        if i in suppressed:
            continue
        kept.append(det)
        for j in range(i + 1, len(candidates)):
            if j not in suppressed and _box_iou(det["box"], candidates[j]["box"]) > POSE_NMS_IOU_THRESHOLD:
                suppressed.add(j)
    return kept


def _get_input_layer_name(network_group: Any, hint: str) -> str:
    """Return the configured input vstream name, auto-discovering if needed.

    Falls back to `hint` if the API query fails (e.g. older HailoRT versions).
    Also logs the actual layer names at DEBUG level so you can see them.
    """
    try:
        infos = network_group.get_input_vstream_infos()
        names = [info.name for info in infos]
        log.debug("Input vstream names: %s", names)
        if names:
            if hint in names:
                return hint
            log.info("Config layer '%s' not found; using discovered '%s'", hint, names[0])
            return names[0]
    except Exception as exc:
        log.debug("Could not query vstream infos (%s); using hint '%s'", exc, hint)
    return hint


def _get_output_layer_names(network_group: Any) -> List[str]:
    """Return all output vstream names for a network group."""
    try:
        infos = network_group.get_output_vstream_infos()
        names = [info.name for info in infos]
        log.debug("Output vstream names: %s", names)
        return names
    except Exception:
        return []


def _parse_ppe_detections(
    infer_results: Dict[str, Any],
    frame_shape: Tuple[int, ...],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse Hailo NMS output into person and equipment bounding boxes."""
    raw_persons: List[Dict[str, Any]] = []
    raw_equipment: List[Dict[str, Any]] = []

    if PPE_OUTPUT_LAYER not in infer_results:
        return raw_persons, raw_equipment

    data = infer_results[PPE_OUTPUT_LAYER]
    if isinstance(data, list) and data:
        data = data[0]

    h, w = frame_shape[:2]
    for cls_id, cls_dets in enumerate(data):
        for box in cls_dets:
            ymin, xmin, ymax, xmax, score = box
            if score < CONFIDENCE_THRESHOLD:
                continue
            xmin *= SCALE_FACTOR
            xmax *= SCALE_FACTOR
            ymin *= SCALE_FACTOR
            ymax *= SCALE_FACTOR
            x1 = max(0, int(xmin * w))
            y1 = max(0, int(ymin * h))
            x2 = min(w, int(xmax * w))
            y2 = min(h, int(ymax * h))
            entry = {"box": [x1, y1, x2, y2], "cls_id": cls_id, "score": float(score)}
            if cls_id == CLS_PERSON:
                raw_persons.append(entry)
            else:
                raw_equipment.append(entry)

    return raw_persons, raw_equipment


class OpenCVCameraSource:
    """Fallback camera source for USB cameras, files, or RTSP URLs."""

    def __init__(self, source: Union[str, int]) -> None:
        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera source: {source}")
        log.info("OpenCV camera opened: %s", source)

    def read_rgb(self) -> Optional[np.ndarray]:
        """Read a BGR frame and convert to RGB."""
        ret, frame_bgr = self._cap.read()
        if not ret or frame_bgr is None:
            return None
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def release(self) -> None:
        self._cap.release()
        log.info("OpenCV camera released")


def _read_exact_bytes(stream: BinaryIO, num_bytes: int) -> Optional[bytes]:
    """Read exactly num_bytes from a blocking stream, or None on EOF."""
    chunks: List[bytes] = []
    remaining = num_bytes
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _log_rpicam_failure(proc: subprocess.Popen[bytes], reason: str) -> None:
    """Log rpicam-vid exit code and stderr when frame capture fails."""
    exit_code = proc.poll()
    stderr_text = ""
    if proc.stderr is not None:
        try:
            stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            pass
    if stderr_text:
        log.error("%s (exit=%s): %s", reason, exit_code, stderr_text)
    else:
        log.error("%s (exit=%s)", reason, exit_code)


def camera_selftest(width: int = CAMERA_WIDTH, height: int = CAMERA_HEIGHT) -> bool:
    """Run a quick camera self-test before starting the main loop.

    Launches rpicam-vid for 3 seconds, reads one YUV420 frame, converts
    it to RGB, and saves a JPEG to /tmp/camera_selftest.jpg so you can
    verify the image visually.  Returns True on success, False on any
    failure.
    """
    cam_log = logging.getLogger("camera")
    frame_bytes = width * height * 3 // 2
    cmd = [
        "rpicam-vid",
        "-t", "0",
        "--width", str(width),
        "--height", str(height),
        "--framerate", "30",
        "--nopreview",
        "--codec", "yuv420",
        "-o", "-",
    ]
    cam_log.info("=== Camera self-test starting ===")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except FileNotFoundError:
        cam_log.error("FAIL: rpicam-vid not found - install rpicam-apps")
        return False

    time.sleep(CAMERA_WARMUP_S)

    if proc.poll() is not None:
        stderr = proc.stderr.read().decode("utf-8", errors="replace").strip() if proc.stderr else ""
        cam_log.error("FAIL: rpicam-vid exited (code %s): %s", proc.returncode, stderr)
        return False

    cam_log.info("OK:   rpicam-vid running (pid %s)", proc.pid)

    raw = _read_exact_bytes(proc.stdout, frame_bytes)  # type: ignore[arg-type]
    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()

    if raw is None or len(raw) != frame_bytes:
        got = len(raw) if raw else 0
        cam_log.error(
            "FAIL: incomplete frame (%d bytes received, expected %d)",
            got, frame_bytes,
        )
        return False

    cam_log.info("OK:   frame bytes received (%d)", frame_bytes)

    try:
        yuv = np.frombuffer(raw, dtype=np.uint8).reshape((height * 3 // 2, width))
        rgb = cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB_I420)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        out_path = "/tmp/camera_selftest.jpg"
        cv2.imwrite(out_path, bgr)
        centre = rgb[height // 2, width // 2].tolist()
        cam_log.info(
            "OK:   converted to RGB %s, centre pixel RGB=%s",
            rgb.shape, centre,
        )
        cam_log.info("OK:   snapshot saved to %s", out_path)
    except Exception as exc:
        cam_log.error("FAIL: frame conversion error: %s", exc)
        return False

    cam_log.info("=== Camera self-test PASSED ===")
    return True


class RpicamReader:
    """Background thread that drains rpicam-vid stdout and keeps only the latest frame.

    Reading in a separate thread means the processing loop never blocks waiting
    for the camera pipe — it always picks up the most recently decoded frame and
    old frames are silently discarded.  This eliminates the lag that builds up
    when inference is slower than the camera frame rate.
    """

    def __init__(self) -> None:
        self._frame_bytes = CAMERA_WIDTH * CAMERA_HEIGHT * 3 // 2
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._latest_rgb: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def start(self) -> None:
        """Launch rpicam-vid and begin reading frames in the background."""
        cmd = [
            "rpicam-vid",
            "-t", "0",
            "--width", str(CAMERA_WIDTH),
            "--height", str(CAMERA_HEIGHT),
            "--framerate", str(CAMERA_FRAMERATE),
            "--nopreview",
            "--codec", "yuv420",
            "-o", "-",
        ]
        log.info(
            "Starting rpicam-vid reader (%dx%d @ %dfps)...",
            CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FRAMERATE,
        )
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        if self._proc.stdout is None:
            self._proc.terminate()
            raise RuntimeError("rpicam-vid stdout pipe unavailable")

        time.sleep(CAMERA_WARMUP_S)
        if self._proc.poll() is not None:
            _log_rpicam_failure(self._proc, "rpicam-vid exited during warmup")
            raise RuntimeError("rpicam-vid failed to start")

        log.info(
            "rpicam-vid running (%dx%d yuv420, %d bytes/frame)",
            CAMERA_WIDTH, CAMERA_HEIGHT, self._frame_bytes,
        )
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self._started = True

    def _read_loop(self) -> None:
        """Continuously decode YUV420 frames; keep only the latest."""
        assert self._proc is not None and self._proc.stdout is not None
        while not self._stop_event.is_set():
            if self._proc.poll() is not None:
                _log_rpicam_failure(self._proc, "rpicam-vid exited unexpectedly")
                break
            raw = _read_exact_bytes(self._proc.stdout, self._frame_bytes)
            if raw is None or len(raw) != self._frame_bytes:
                break
            yuv = np.frombuffer(raw, dtype=np.uint8).reshape(
                (CAMERA_HEIGHT * 3 // 2, CAMERA_WIDTH),
            )
            rgb = cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB_I420)
            with self._lock:
                self._latest_rgb = rgb

    def get_frame(self) -> Optional[np.ndarray]:
        """Return the most recent RGB frame, or None if none available yet."""
        with self._lock:
            return self._latest_rgb

    def stop(self) -> None:
        """Stop the reader thread and terminate rpicam-vid."""
        self._stop_event.set()
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            log.info("rpicam-vid process terminated")
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def _save_violation(
    frame: np.ndarray,
    obj_id: int,
    data: Dict[str, Any],
    fps: float,
    uploader: Optional[CloudUploader],
) -> None:
    """Save local snapshot/JSON and optionally upload to Firebase."""
    det = data["det_data"]
    is_fallen = bool(data.get("is_fallen", False))
    idle_seconds = int(data.get("idle_duration_s", 0.0) or 0.0)

    missing: List[str] = []
    if not det.get("has_helmet"):
        missing.append("No Helmet")
    if not det.get("has_vest"):
        missing.append("No Vest")

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img_filename = f"ID{obj_id}_{timestamp_str}.jpg"
    json_filename = f"ID{obj_id}_{timestamp_str}.json"
    img_path = os.path.join(SNAPSHOT_DIR, img_filename)
    json_path = os.path.join(JSON_DIR, json_filename)

    save_frame = frame.copy()
    draw_dashboard(save_frame, {obj_id: data}, [], fps)
    cv2.imwrite(img_path, save_frame)

    json_data = {
        "id": obj_id,
        "time": timestamp_str,
        "missing": missing,
        "image_path": img_path,
        "is_fallen": is_fallen,
        "idle_seconds": idle_seconds,
    }
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(json_data, fh, indent=2)

    log.info("Violation saved locally: %s", img_filename)
    if uploader is not None:
        uploader.upload_violation(
            obj_id, missing, img_path,
            is_fallen=is_fallen,
            idle_seconds=idle_seconds,
        )


# ═══════════════════════════════ DETECTION LOOP ═══════════════════════════════════

def detection_loop(
    camera_src: Union[str, int],
    uploader: Optional[CloudUploader],
) -> None:
    """Main detection thread: PPE on Hailo-8 NPU, pose on MediaPipe CPU.

    Architecture:
      - Hailo-8: PPE detection (helmet/vest) — full resolution, every frame
      - MediaPipe: pose estimation at 320x180, every 3rd frame (reuse between)
      - Background RpicamReader keeps the frame pipe drained at 30fps so the
        main loop always processes the newest frame with no backlog.
    """
    pose_log = logging.getLogger("pose")
    tracker = StickyTracker()

    # ── MediaPipe pose (CPU, lightweight) ────────────────────────────────────
    mp_pose_mod = _get_mediapipe().solutions.pose
    with _suppress_native_stderr():
        pose_cpu = mp_pose_mod.Pose(
            static_image_mode=False,
            model_complexity=MP_MODEL_COMPLEXITY,
            min_detection_confidence=MP_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MP_MIN_TRACKING_CONFIDENCE,
            smooth_landmarks=True,
            enable_segmentation=False,
            smooth_segmentation=False,
        )
    pose_log.info(
        "MediaPipe Pose ready (complexity=%d, input=%dx%d every %d frames)",
        MP_MODEL_COMPLEXITY, POSE_PROCESS_WIDTH, POSE_PROCESS_HEIGHT, POSE_EVERY_N_FRAMES,
    )

    params = VDevice.create_params()
    params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN

    with VDevice(params) as target:
        # ── PPE model on Hailo ───────────────────────────────────────────────
        hef_ppe = HEF(PPE_HEF_FILE)
        cfg_ppe = ConfigureParams.create_from_hef(hef_ppe, interface=HailoStreamInterface.PCIe)
        ng_ppe = target.configure(hef_ppe, cfg_ppe)[0]
        ppe_input_layer = _get_input_layer_name(ng_ppe, PPE_INPUT_LAYER)
        in_ppe = InputVStreamParams.make(ng_ppe, format_type=FormatType.UINT8)
        out_ppe = OutputVStreamParams.make(ng_ppe, format_type=FormatType.FLOAT32)
        log.info("PPE model loaded (input: %s)", ppe_input_layer)

        # ── Camera ───────────────────────────────────────────────────────────
        src = int(camera_src) if isinstance(camera_src, str) and camera_src.isdigit() else camera_src
        rpicam_reader: Optional[RpicamReader] = None
        camera_opencv: Optional[OpenCVCameraSource] = None

        if src == 0:
            rpicam_reader = RpicamReader()
            try:
                rpicam_reader.start()
            except Exception as exc:
                log.error("Failed to start rpicam-vid: %s", exc)
                pose_cpu.close()
                return
        else:
            try:
                camera_opencv = OpenCVCameraSource(src)
            except RuntimeError as exc:
                log.error("%s", exc)
                pose_cpu.close()
                return

        fps_start = time.time()
        frame_count = 0
        pose_warmed = False
        fps = 0.0
        got_first_frame = False
        pose_skip_counter = 0
        last_pose_people: List[Dict[str, Any]] = []
        # Scale factors: 320x180 → 1280x720
        pose_sx = CAMERA_WIDTH / POSE_PROCESS_WIDTH
        pose_sy = CAMERA_HEIGHT / POSE_PROCESS_HEIGHT

        try:
            with InferVStreams(ng_ppe, in_ppe, out_ppe) as infer_ppe:
                while not _shutdown_event.is_set():
                    if rpicam_reader is not None:
                        frame_rgb = rpicam_reader.get_frame()
                    else:
                        assert camera_opencv is not None
                        frame_rgb = camera_opencv.read_rgb()

                    if frame_rgb is None:
                        time.sleep(0.005)
                        continue

                    if not got_first_frame:
                        got_first_frame = True
                        log.info(
                            "First camera frame received (%dx%d)",
                            frame_rgb.shape[1], frame_rgb.shape[0],
                        )

                    # ── Hailo PPE (every frame) ───────────────────────────
                    input_ppe = cv2.resize(frame_rgb, (MODEL_SIZE, MODEL_SIZE))
                    batch_ppe = np.expand_dims(input_ppe, axis=0)
                    res_ppe = infer_ppe.infer({ppe_input_layer: batch_ppe})
                    raw_persons, raw_equipment = _parse_ppe_detections(res_ppe, frame_rgb.shape)

                    # ── MediaPipe pose (320x180, every 3rd frame) ─────────
                    pose_skip_counter += 1
                    if pose_skip_counter >= POSE_EVERY_N_FRAMES:
                        pose_skip_counter = 0
                        small = cv2.resize(frame_rgb, (POSE_PROCESS_WIDTH, POSE_PROCESS_HEIGHT))
                        if not pose_warmed:
                            with _suppress_native_stderr():
                                results = pose_cpu.process(small)
                            pose_warmed = True
                        else:
                            results = pose_cpu.process(small)
                        raw_pose = mediapipe_pose_people(
                            np.zeros((POSE_PROCESS_HEIGHT, POSE_PROCESS_WIDTH, 3), np.uint8),
                            results,
                        )
                        # Scale keypoints and boxes back to full frame size
                        for p in raw_pose:
                            p["box"] = [
                                int(p["box"][0] * pose_sx), int(p["box"][1] * pose_sy),
                                int(p["box"][2] * pose_sx), int(p["box"][3] * pose_sy),
                            ]
                            if p.get("keypoints") is not None:
                                p["keypoints"][:, 0] *= pose_sx
                                p["keypoints"][:, 1] *= pose_sy
                        last_pose_people = raw_pose
                        if last_pose_people:
                            pose_log.info("Pose: %d person(s) detected", len(last_pose_people))

                    # ── Draw + track ──────────────────────────────────────
                    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                    for person in last_pose_people:
                        kps = person.get("keypoints")
                        if kps is not None:
                            draw_skeleton(frame, kps)

                    paired = pair_equipment(raw_persons, raw_equipment)
                    paired = pair_fall_status(paired, last_pose_people)
                    tracked = tracker.update(paired)

                    for obj_id, data in tracked.items():
                        if data.get("trigger_upload"):
                            _save_violation(frame, obj_id, data, fps, uploader)
                            data["trigger_upload"] = False
                            if obj_id in tracker.state_data:
                                tracker.state_data[obj_id]["trigger_upload"] = False

                    frame = draw_dashboard(frame, tracked, raw_equipment, fps)

                    frame_count += 1
                    if frame_count % FPS_SAMPLE_FRAMES == 0:
                        elapsed = time.time() - fps_start
                        fps = FPS_SAMPLE_FRAMES / elapsed if elapsed > 0 else 0.0
                        fps_start = time.time()
                        log.debug("Processing FPS: %.1f", fps)

                    push_frame(frame)

        finally:
            if rpicam_reader is not None:
                rpicam_reader.stop()
            if camera_opencv is not None:
                camera_opencv.release()
            pose_cpu.close()
            log.info("Detection loop stopped")


# ═══════════════════════════════ DISPLAY WINDOW ════════════════════════════════════

async def opencv_window_task() -> None:
    """Show live dashboard on the main thread (required for OpenCV/Qt on Pi)."""
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, WINDOW_WIDTH, WINDOW_HEIGHT)
    log.info("OpenCV display window opened (press 'q' to quit)")

    try:
        while not _shutdown_event.is_set():
            frame = _get_latest_frame_copy()
            if frame is not None:
                display = cv2.resize(frame, (WINDOW_WIDTH, WINDOW_HEIGHT))
                cv2.imshow(WINDOW_NAME, display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                _shutdown_event.set()
                break
            await asyncio.sleep(0.03)
    finally:
        cv2.destroyAllWindows()
        log.info("OpenCV display window closed")


# ═══════════════════════════════ HTTP HANDLERS ════════════════════════════════════

def _streaming_disabled_response() -> web.Response:
    """Return 503 when MJPEG/JPEG streaming is toggled off."""
    return web.Response(status=503, text="Streaming disabled")


async def index(request: web.Request) -> web.Response:
    """Serve browser dashboard with stream status and toggle controls."""
    stream_on = _stream_enabled.is_set()
    cloud_on = _cloud_enabled.is_set()
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>Construct Eye — PPE Dashboard</title>
    <style>
      body {{ font-family: system-ui, Arial, sans-serif; margin: 0; background: #0b0f14; color: #e6edf3; }}
      header {{ padding: 12px 16px; background: #111826; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
      main {{ padding: 16px; display:grid; gap:16px; }}
      .card {{ background: #0f1724; border: 1px solid #1f2a3a; border-radius: 10px; overflow:hidden; }}
      .card h2 {{ margin:0; padding: 12px 14px; font-size:14px; font-weight:600; color:#aab7c5; border-bottom: 1px solid #1f2a3a; }}
      .content {{ padding: 14px; }}
      img {{ width: 100%; height: auto; display:block; background:#000; min-height:240px; }}
      code {{ background: #0b1220; border: 1px solid #1f2a3a; padding: 2px 6px; border-radius: 6px; }}
      a {{ color: #9cc2ff; text-decoration: none; }}
      .row {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
      .status {{ color: #9fb2c3; font-size: 13px; }}
      .badge {{ padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
      .on {{ background: #14532d; color: #86efac; }}
      .off {{ background: #450a0a; color: #fca5a5; }}
      button {{ cursor:pointer; background:#334155; border:none; color:white; padding:8px 12px; border-radius:8px; font-weight:600; }}
      button:hover {{ background:#475569; }}
    </style>
  </head>
  <body>
    <header>
      <div style="font-weight:700">Construct Eye</div>
      <span id="streamBadge" class="badge {'on' if stream_on else 'off'}">
        Stream: {'ENABLED' if stream_on else 'DISABLED'}
      </span>
      <span id="cloudBadge" class="badge {'on' if cloud_on else 'off'}">
        Cloud: {'ENABLED' if cloud_on else 'DISABLED'}
      </span>
      <div class="row">
        <a class="status" href="/health">/health</a>
        <a class="status" href="/jpg">/jpg</a>
      </div>
    </header>
    <main>
      <div class="card">
        <h2>Live MJPEG Feed</h2>
        <div class="content">
          <div class="row" style="margin-bottom:10px">
            <button id="streamToggle">{'Disable Stream' if stream_on else 'Enable Stream'}</button>
            <button id="cloudToggle">{'Disable Cloud' if cloud_on else 'Enable Cloud'}</button>
            <span class="status">URL: <code>/mjpeg</code></span>
          </div>
          <img id="mjpeg" alt="MJPEG stream" {'src="/mjpeg?ts=" + str(int(time.time()))' if stream_on else ''}/>
        </div>
      </div>
    </main>
    <script>
      const streamBadge = document.getElementById('streamBadge');
      const cloudBadge = document.getElementById('cloudBadge');
      const streamBtn = document.getElementById('streamToggle');
      const cloudBtn = document.getElementById('cloudToggle');
      const img = document.getElementById('mjpeg');
      let streamOn = {'true' if stream_on else 'false'};
      let cloudOn = {'true' if cloud_on else 'false'};

      async function toggleStream() {{
        const endpoint = streamOn ? '/stream/disable' : '/stream/enable';
        const resp = await fetch(endpoint, {{ method: 'POST' }});
        const data = await resp.json();
        streamOn = data.enabled;
        streamBadge.textContent = 'Stream: ' + (streamOn ? 'ENABLED' : 'DISABLED');
        streamBadge.className = 'badge ' + (streamOn ? 'on' : 'off');
        streamBtn.textContent = streamOn ? 'Disable Stream' : 'Enable Stream';
        img.src = streamOn ? '/mjpeg?ts=' + Date.now() : '';
      }}

      async function toggleCloud() {{
        const endpoint = cloudOn ? '/cloud/disable' : '/cloud/enable';
        const resp = await fetch(endpoint, {{ method: 'POST' }});
        const data = await resp.json();
        cloudOn = data.enabled;
        cloudBadge.textContent = 'Cloud: ' + (cloudOn ? 'ENABLED' : 'DISABLED');
        cloudBadge.className = 'badge ' + (cloudOn ? 'on' : 'off');
        cloudBtn.textContent = cloudOn ? 'Disable Cloud' : 'Enable Cloud';
      }}

      streamBtn.addEventListener('click', toggleStream);
      cloudBtn.addEventListener('click', toggleCloud);
    </script>
  </body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def health(request: web.Request) -> web.Response:
    """Return uptime and frame availability."""
    frame = _get_latest_frame_copy()
    payload = {
        "ok": True,
        "uptime_s": round(time.time() - _server_started_at, 1),
        "has_frame": frame is not None,
        "stream_enabled": _stream_enabled.is_set(),
        "cloud_enabled": _cloud_enabled.is_set(),
    }
    return web.json_response(payload)


async def jpg(request: web.Request) -> web.Response:
    """Return a single JPEG snapshot of the latest frame."""
    if not _stream_enabled.is_set():
        return _streaming_disabled_response()

    frame = _get_latest_frame_copy()
    if frame is None:
        return web.Response(status=503, text="No frames yet")

    ok, jpg_buf = cv2.imencode(
        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), SNAPSHOT_JPEG_QUALITY],
    )
    if not ok:
        return web.Response(status=500, text="JPEG encode failed")
    return web.Response(body=jpg_buf.tobytes(), content_type="image/jpeg")


async def mjpeg(request: web.Request) -> web.Response:
    """Stream annotated frames as multipart MJPEG at ~10 FPS."""
    if not _stream_enabled.is_set():
        return _streaming_disabled_response()

    boundary = "frame"
    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={boundary}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )
    try:
        await resp.prepare(request)
    except Exception:
        return resp

    while True:
        try:
            if not _stream_enabled.is_set():
                break

            frame = _get_latest_frame_copy()
            if frame is None:
                await asyncio.sleep(0.05)
                continue

            small = cv2.resize(frame, (MJPEG_STREAM_WIDTH, MJPEG_STREAM_HEIGHT))
            ok, jpg_buf = cv2.imencode(
                ".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), MJPEG_JPEG_QUALITY],
            )
            if not ok:
                await asyncio.sleep(0.02)
                continue

            payload = jpg_buf.tobytes()
            await resp.write(
                (
                    f"--{boundary}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(payload)}\r\n\r\n"
                ).encode("utf-8")
                + payload
                + b"\r\n"
            )
            await asyncio.sleep(MJPEG_FPS_SLEEP_S)
        except (ConnectionResetError, asyncio.CancelledError, AttributeError):
            break
        except Exception:
            break
    return resp


async def stream_enable(request: web.Request) -> web.Response:
    """Enable MJPEG streaming at runtime."""
    _stream_enabled.set()
    logging.getLogger("stream").info("Streaming enabled")
    return web.json_response({"enabled": True})


async def stream_disable(request: web.Request) -> web.Response:
    """Disable MJPEG streaming at runtime."""
    _stream_enabled.clear()
    logging.getLogger("stream").info("Streaming disabled")
    return web.json_response({"enabled": False})


async def cloud_enable(request: web.Request) -> web.Response:
    """Enable Firebase cloud uploads at runtime."""
    _cloud_enabled.set()
    logging.getLogger("cloud").info("Cloud upload enabled")
    return web.json_response({"enabled": True})


async def cloud_disable(request: web.Request) -> web.Response:
    """Disable Firebase cloud uploads at runtime."""
    _cloud_enabled.clear()
    logging.getLogger("cloud").info("Cloud upload disabled")
    return web.json_response({"enabled": False})


# ═══════════════════════════════ MAIN ═══════════════════════════════════════════════

async def async_main() -> None:
    """Parse CLI args, start detection thread, and run the aiohttp server."""
    parser = argparse.ArgumentParser(
        description="Construct Eye — site safety monitor (PPE, fall, idle) with MJPEG streaming",
    )
    parser.add_argument("--camera", default="0", help="Camera index or URL (default: 0)")
    parser.add_argument("--http-host", default="0.0.0.0", help="HTTP bind host")
    parser.add_argument("--http-port", type=int, default=8081, help="HTTP port")
    parser.add_argument("--enable-window", action="store_true", help="Show local OpenCV window")
    parser.add_argument("--disable-stream", action="store_true", help="Start with streaming OFF")
    parser.add_argument("--disable-cloud", action="store_true", help="Start with Firebase OFF")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--firebase-service-account", default=DEFAULT_FIREBASE_KEY,
        help="Path to Firebase service account JSON",
    )
    parser.add_argument(
        "--firebase-storage-bucket", default=DEFAULT_FIREBASE_BUCKET,
        help="Firebase Storage bucket name",
    )
    parser.add_argument(
        "--device-id", default=os.getenv("DEVICE_ID"),
        help="Device serial/UUID for devices collection (auto-generated if omitted)",
    )
    parser.add_argument(
        "--stream-link", default=DEFAULT_STREAM_LINK,
        help="Live MJPEG URL stored in devices collection",
    )
    parser.add_argument(
        "--project-id", type=int, default=PROJECT_ID,
        help="Active project id for Firestore filtering (default: CONSTRUCT_EYE_PROJECT_ID env)",
    )
    parser.add_argument(
        "--location", default=None,
        help="Optional fixed location label; omit to auto-detect from GPS/IP",
    )
    parser.add_argument(
        "--weather-lat", type=float, default=None,
        help="Optional fixed latitude; omit to auto-detect from GPS/IP",
    )
    parser.add_argument(
        "--weather-lon", type=float, default=None,
        help="Optional fixed longitude; omit to auto-detect from GPS/IP",
    )
    parser.add_argument(
        "--skip-camera-test",
        action="store_true",
        help="Skip the camera self-test at startup",
    )
    args = parser.parse_args()

    _configure_logging(args.log_level)
    _ensure_output_dirs()
    _init_mp_landmark_map()

    # Camera self-test — runs before Hailo so failures are obvious
    src = int(args.camera) if args.camera.isdigit() else args.camera
    if src == 0 and not args.skip_camera_test:
        ok = camera_selftest()
        if not ok:
            log.error(
                "Camera self-test FAILED. Fix the camera, then re-run.\n"
                "  Skip with: --skip-camera-test\n"
                "  Quick shell check: rpicam-vid -t 3000 --nopreview "
                "--codec yuv420 -o /dev/null"
            )
            sys.exit(1)

    if args.disable_stream:
        _stream_enabled.clear()
    else:
        _stream_enabled.set()

    uploader: Optional[CloudUploader] = None
    if args.disable_cloud:
        _cloud_enabled.clear()
        logging.getLogger("cloud").info("Cloud upload disabled (offline mode)")
    else:
        _cloud_enabled.set()
        stream_link = args.stream_link
        if "{host}" in stream_link or "{port}" in stream_link:
            stream_link = stream_link.format(host=args.http_host, port=args.http_port)
        if args.http_host in ("0.0.0.0", ""):
            stream_link = stream_link.replace("127.0.0.1", "localhost")
        if args.firebase_service_account and args.firebase_storage_bucket:
            uploader = CloudUploader(
                args.firebase_service_account,
                args.firebase_storage_bucket,
                stream_link=stream_link,
                device_id=args.device_id,
                project_id=args.project_id,
                manual_location_label=args.location,
                manual_latitude=args.weather_lat,
                manual_longitude=args.weather_lon,
            )
        else:
            logging.getLogger("cloud").info(
                "Cloud upload disabled (offline mode) - no Firebase credentials provided",
            )
            _cloud_enabled.clear()

    det_thread = threading.Thread(
        target=detection_loop,
        args=(args.camera, uploader),
        daemon=True,
    )
    det_thread.start()

    window_task: Optional[asyncio.Task[None]] = None
    if args.enable_window:
        window_task = asyncio.create_task(opencv_window_task())

    await asyncio.sleep(2)

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/jpg", jpg)
    app.router.add_get("/mjpeg", mjpeg)
    app.router.add_post("/stream/enable", stream_enable)
    app.router.add_post("/stream/disable", stream_disable)
    app.router.add_post("/cloud/enable", cloud_enable)
    app.router.add_post("/cloud/disable", cloud_disable)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.http_host, args.http_port)
    await site.start()

    log.info("Browser preview: http://%s:%s/", args.http_host, args.http_port)
    log.info("MJPEG stream:    http://%s:%s/mjpeg", args.http_host, args.http_port)
    log.info("Health check:    http://%s:%s/health", args.http_host, args.http_port)
    log.info("Press Ctrl+C to stop")

    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Shutting down cleanly...")
    finally:
        _shutdown_event.set()
        if uploader is not None:
            uploader.shutdown()
        if window_task is not None:
            window_task.cancel()
            try:
                await window_task
            except asyncio.CancelledError:
                pass
        try:
            await runner.cleanup()
        except Exception:
            pass
        det_thread.join(timeout=5.0)


if __name__ == "__main__":
    asyncio.run(async_main())
