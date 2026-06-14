<p align="center">
  <img src="assets/Logo/Construct_eye_logo_picture.png" alt="Construct Eye logo" width="320"/>
</p>

# Construct Eye

Construct Eye is an edge-AI construction site monitoring system built for **Raspberry Pi 5 + Hailo-8**. It combines:

- **Safety monitoring** — real-time PPE (helmet/vest), fall, and idle-time detection with MJPEG streaming
- **Progress reporting** — AI-driven structural/architectural site analysis, PDF reports, and Firebase sync
- **Shared cloud layer** — Firebase Firestore, Storage, FCM push notifications, device weather

This repository is organized for **GitHub publication**. Sensitive values (API keys, Firebase buckets, site IDs) are replaced with placeholders. Copy [`config.example.env`](config.example.env) to `.env` and fill in your values before deployment.

---

## Deployed device

Raspberry Pi 5 with camera and Hailo-8 AI HAT, running the Construct Eye safety and reporting stack:

<p align="center">
  <img src="assets/device/Actual%20device%20picture.png" alt="Construct Eye Raspberry Pi 5 deployment" width="560"/>
</p>

<p align="center"><em>Construct Eye edge device — Pi 5, AI HAT, and site camera</em></p>

---

## Repository layout

| Path | Purpose |
|------|---------|
| [`shared/`](shared/README.md) | Firebase helpers, notifications, geolocation, weather |
| [`safety-monitoring/`](safety-monitoring/README.md) | PPE, fall, and idle detection + MJPEG live stream |
| [`progress-reporting/`](progress-reporting/README.md) | Construction progress report generator + GUI |
| [`sample-site-images/`](sample-site-images/README.md) | Input folder for reference drawings and site photos |
| [`assets/`](assets/README.md) | Logo, branding, and device photos |
| [`config.example.env`](config.example.env) | Environment variable template (copy → `.env`) |
| [`requirements.txt`](requirements.txt) | Python dependencies |

Runnable code:

- `safety-monitoring/site_safety_monitor/site_safety_monitor.py`
- `progress-reporting/src/construction_progress_report.py`

---

## Quick start (Raspberry Pi 5)

### 1. Install dependencies

```bash
cd /path/to/construct-eye
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Install **HailoRT / hailo_platform** separately per Hailo documentation (required for safety monitoring).

### 2. Configure secrets

```bash
cp config.example.env .env
# Edit .env with your Firebase bucket, Moondream key, project id, etc.
export $(grep -v '^#' .env | xargs)    # Linux / Pi
```

Place your Firebase service account JSON **outside** the repo (e.g. `~/secrets/firebase-key.json`):

```bash
export FIREBASE_SERVICE_ACCOUNT=~/secrets/firebase-key.json
```

### 3. Run safety monitoring (PPE + fall + idle)

```bash
cd safety-monitoring/site_safety_monitor
python3 site_safety_monitor.py \
  --camera 0 \
  --enable-window \
  --firebase-service-account "$FIREBASE_SERVICE_ACCOUNT" \
  --firebase-storage-bucket "YOUR_PROJECT_ID.appspot.com" \
  --project-id "$CONSTRUCT_EYE_PROJECT_ID"
```

Local test without cloud:

```bash
python3 site_safety_monitor.py --camera 0 --enable-window --disable-cloud --disable-stream
```

**Expected output (terminal):**

```
[INFO] [camera] === Camera self-test PASSED ===
[INFO] [ppe] PPE model loaded (input: yolov8n/input_layer1)
[INFO] [ppe] Browser preview: http://0.0.0.0:8081/
[INFO] [ppe] MJPEG stream:    http://0.0.0.0:8081/mjpeg
```

Open `http://<pi-ip>:8081` in a browser for the live dashboard.

### 4. Run construction progress report

Add images to [`sample-site-images/`](sample-site-images/README.md) (structural + architectural references + site photo), then:

```bash
cd progress-reporting/src
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key "$MOONDREAM_API_KEY" \
  --firebase-key "$FIREBASE_SERVICE_ACCOUNT" \
  --firebase-bucket "YOUR_PROJECT_ID.appspot.com" \
  --gui
```

Local PDF only:

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key "$MOONDREAM_API_KEY" \
  --no-upload
```

**Expected output (terminal):**

```
[INFO] construction_progress_report.py v2.4.0
[INFO] Structural reference:  Structural View.png
[INFO] Architectural reference: Architectural View.png
[INFO] Site images: 1
...
[PDF] Saved: .../progress-reporting/output/construction_reports/construct_eye_report_....pdf
[DONE] Overall 67.3% | Structural 72.1% | Architectural 58.4% | Phase: Structural Works
```

---

## Hardware requirements

| Component | Used by |
|-----------|---------|
| Raspberry Pi 5 | Both modules |
| Hailo-8 AI HAT | Safety monitoring (PPE inference on NPU) |
| Pi Camera Module (IMX708) | Safety monitoring (`--camera 0`) |
| HDMI display (optional) | `--enable-window` / `--gui` |
| Internet | Moondream API (reports), Firebase (optional cloud sync) |

---

## Documentation index

| Topic | Link |
|-------|------|
| Safety monitoring (PPE, fall, idle, stream) | [`safety-monitoring/README.md`](safety-monitoring/README.md) |
| Progress reporting | [`progress-reporting/README.md`](progress-reporting/README.md) |
| Sample input images | [`sample-site-images/README.md`](sample-site-images/README.md) |
| Shared Firebase helpers | [`shared/README.md`](shared/README.md) |
| Logo and assets | [`assets/README.md`](assets/README.md) |

---

## License

Add your license here before publishing.
