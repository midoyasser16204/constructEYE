# Safety monitoring

Real-time **construction site safety** pipeline for **Raspberry Pi 5 + Hailo-8**. One program covers three detection streams plus live streaming and cloud alerts:

| Stream | Technology | What it detects |
|--------|------------|-----------------|
| **PPE** | Hailo-8 + YOLOv8n | Missing helmet or safety vest |
| **Fall** | MediaPipe Pose (CPU) | Worker lying down / fall posture |
| **Idle** | Centroid tracking | Worker stationary for 30+ seconds |

Also provides an **MJPEG web dashboard** (port 8081), optional **HDMI preview**, and **Firebase** violation upload with push notifications.

---

## Current folder structure

```
safety-monitoring/
├── README.md
├── site_safety_monitor/
│   └── site_safety_monitor.py    # Main entry point (PPE + fall + idle + stream)
├── models/
│   ├── yolov8n.hef               # Hailo model used at runtime
│   ├── best.pt / best.onnx       # Optional exports
│   └── yolov8-ppe-training/      # Training artifacts (reference only)
└── output/                       # Created at runtime
    ├── violation_images/         # JPEG snapshots on alert
    └── violation_logs/           # JSON metadata per violation
```

---

## Prerequisites

From the **repository root**:

```bash
pip install -r requirements.txt
```

Also required on the Pi (not on PyPI):

- **HailoRT / hailo_platform** — PPE inference on the AI HAT
- **rpicam-apps** — Pi Camera Module (`rpicam-vid`)
- **MediaPipe** — fall detection (installed via requirements.txt)

Configure Firebase (optional) via [`../config.example.env`](../config.example.env):

```bash
export FIREBASE_SERVICE_ACCOUNT=/path/to/firebase-key.json
export FIREBASE_STORAGE_BUCKET=YOUR_PROJECT_ID.appspot.com
export CONSTRUCT_EYE_PROJECT_ID=YOUR_NUMERIC_PROJECT_ID
```

---

## How to run

All commands start in `safety-monitoring/site_safety_monitor/`.

### 1 — Local test (camera + HDMI window, no cloud, no stream)

```bash
cd safety-monitoring/site_safety_monitor
python3 site_safety_monitor.py \
  --camera 0 \
  --enable-window \
  --disable-cloud \
  --disable-stream \
  --log-level INFO
```

### 2 — Web dashboard only (phone/PC view, no Firebase)

```bash
python3 site_safety_monitor.py \
  --camera 0 \
  --disable-cloud \
  --log-level INFO
```

Open `http://<pi-ip>:8081` in a browser.

### 3 — Full deployment (PPE + fall + idle + stream + Firebase)

```bash
python3 site_safety_monitor.py \
  --camera 0 \
  --firebase-service-account /path/to/firebase-key.json \
  --firebase-storage-bucket YOUR_PROJECT_ID.appspot.com \
  --project-id YOUR_NUMERIC_PROJECT_ID \
  --log-level WARNING
```

### 4 — USB webcam instead of Pi camera

```bash
python3 site_safety_monitor.py \
  --camera 1 \
  --skip-camera-test \
  --enable-window \
  --disable-cloud
```

### 5 — Headless background service (SSH)

```bash
nohup python3 site_safety_monitor.py \
  --camera 0 \
  --firebase-service-account /path/to/firebase-key.json \
  --firebase-storage-bucket YOUR_PROJECT_ID.appspot.com \
  --log-level INFO \
  > ~/site_safety.log 2>&1 &
```

Stop: `pkill -f site_safety_monitor.py`

---

## CLI parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--camera` | `0` | `0` = Pi camera (`rpicam-vid`); `1+` = USB webcam; or RTSP URL |
| `--http-host` | `0.0.0.0` | Web server bind address |
| `--http-port` | `8081` | Web server port |
| `--enable-window` | off | Open OpenCV preview on HDMI (do not use headless) |
| `--disable-stream` | off | Start with MJPEG streaming off |
| `--disable-cloud` | off | Start with Firebase uploads off |
| `--firebase-service-account` | none | Path to Firebase admin JSON |
| `--firebase-storage-bucket` | none | e.g. `YOUR_PROJECT_ID.appspot.com` |
| `--project-id` | `CONSTRUCT_EYE_PROJECT_ID` env | Firestore project id |
| `--device-id` | auto UUID | Device document id in Firestore |
| `--stream-link` | `http://127.0.0.1:8081/mjpeg` | Live stream URL stored on device record |
| `--location` | auto-detect | Manual location label override |
| `--weather-lat` / `--weather-lon` | auto-detect | Manual GPS coordinates for weather |
| `--skip-camera-test` | off | Skip startup `rpicam-vid` self-test |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, or `WARNING` |

---

## Detection streams (what the code does)

### PPE (Hailo-8, every frame)

- Model: `../models/yolov8n.hef`
- Classes: helmet, person, safety vest
- Violation after **3 seconds** without required PPE
- Labels: `SAFE`, `CHECKING Ns`, `VIOLATION (No Helmet)`, etc.

### Fall (MediaPipe, every 3rd frame)

- Pose keypoints at 320×180, scaled to 1280×720
- Fall when nose drops near hip level (`FALL_NOSE_HIP_MARGIN_PX = 80`)
- **Immediate** alert — no 3-second wait
- Label: `FALLEN ALERT!` + top banner

### Idle (tracker, every frame)

- EMA-smoothed centroid; movement threshold **60 px**
- Alert after **30 s** without significant movement
- Label: `IDLE ALERT: Ns` (orange)

---

## Expected output

### Terminal (startup)

```
[INFO] [camera] === Camera self-test PASSED ===
[INFO] [ppe] PPE model loaded (input: yolov8n/input_layer1)
[INFO] [pose] MediaPipe Pose ready (complexity=0, input=320x180 every 3 frames)
[INFO] [ppe] First camera frame received (1280x720)
[INFO] [ppe] Browser preview: http://0.0.0.0:8081/
[INFO] [ppe] MJPEG stream:    http://0.0.0.0:8081/mjpeg
```

### Terminal (violation, cloud on)

```
[INFO] [ppe] Violation saved locally: ID0_20250614_143022.jpg
[INFO] [cloud] Upload success for person ID 0 (violation=..., notification linked)
```

### Browser dashboard

Live annotated video: bounding boxes, skeleton overlay, compliance panel, alert banners (`VIOLATION ALERT`, `FALLEN ALERT`, `IDLE ALERT`).

### Local files

| Path | Contents |
|------|----------|
| `output/violation_images/ID*.jpg` | Frame snapshot when alert fires |
| `output/violation_logs/ID*.json` | Person id, missing PPE, fall/idle flags, timestamp |

---

## HTTP endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | HTML dashboard with stream/cloud toggles |
| GET | `/mjpeg` | Live MJPEG (~5 FPS) |
| GET | `/jpg` | Single JPEG snapshot |
| GET | `/health` | JSON: uptime, frame status, stream/cloud flags |
| POST | `/stream/enable` | Turn MJPEG on |
| POST | `/stream/disable` | Turn MJPEG off |
| POST | `/cloud/enable` | Turn Firebase uploads on |
| POST | `/cloud/disable` | Turn Firebase uploads off |

**Runtime control example:**

```bash
curl http://<pi-ip>:8081/health
curl -X POST http://<pi-ip>:8081/stream/enable
curl -X POST http://<pi-ip>:8081/cloud/disable
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Camera self-test fails | Check `rpicam-vid`; use `--skip-camera-test` for USB/RTSP |
| `hailo_platform import failed` | Install HailoRT on the Pi |
| Blank browser stream | Wait 2–3 s after start; check `/health` → `"has_frame": true` |
| Window crash over SSH | Remove `--enable-window`; use browser at `:8081` |
| No cloud uploads | Pass both `--firebase-service-account` and `--firebase-storage-bucket` |

---

## Related

- [ML models](models/README.md)
- [Firebase helpers](../shared/README.md)
- [Repository overview](../README.md)
