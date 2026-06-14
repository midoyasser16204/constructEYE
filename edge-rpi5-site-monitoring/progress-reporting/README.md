# Progress reporting

AI-powered **construction progress analysis** for Raspberry Pi 5 (or any machine with internet): compares live site photos against architectural and structural reference drawings, generates a PDF report, and optionally uploads results to Firebase.

**Script version:** `2.4.0` (`construction_progress_report.py`)

---

## Current folder structure

```
progress-reporting/
├── README.md
├── src/
│   ├── construction_progress_report.py   # Main CLI entry point
│   └── progress_report_gui.py            # Tkinter live progress window
└── output/                               # Generated at runtime (gitignored except .gitkeep)
    ├── construction_reports/             # PDF reports
    └── reference_metrics_cache/          # Cached Moondream reference scans
```

Input images are **not** stored here. Put them in [`../sample-site-images/`](../sample-site-images/README.md) (or any folder you pass on the command line).

Branding logos live in [`../assets/`](../assets/README.md).

---

## What it does

1. Finds **Structural View** and **Architectural View** reference images in your input folder
2. Finds one or more **Building Under Construction** site photos
3. Calls the **Moondream** vision API to extract metrics from references and site images
4. Computes structural and architectural completion percentages and current phase
5. Renders a branded **PDF report**
6. Optionally uploads site image + PDF to **Firebase Storage**, writes a **Firestore** document, and sends an **FCM push notification**

---

## Prerequisites

Install from the **repository root**:

```bash
cd /path/to/construct-eye
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Configure secrets (copy [`../config.example.env`](../config.example.env) → `.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `MOONDREAM_API_KEY` | **Yes** | Moondream cloud API key |
| `FIREBASE_SERVICE_ACCOUNT` | For upload | Path to Firebase admin JSON (keep outside repo) |
| `FIREBASE_STORAGE_BUCKET` | For upload | e.g. `YOUR_PROJECT_ID.appspot.com` |
| `CONSTRUCT_EYE_PROJECT_ID` | For upload | Numeric Firestore project id |
| `CONSTRUCT_EYE_IMAGE_DIR` | Optional | Default input folder (default: `./sample-site-images`) |

Load env vars before running:

```bash
export $(grep -v '^#' .env | xargs)    # Linux / Pi
```

---

## Required input images

In your site folder (e.g. `sample-site-images/`):

| File | Role |
|------|------|
| `Structural View.png` | Structural reference drawing |
| `Architectural View.png` | Architectural reference drawing |
| `Building Under Construction*.png` | One or more live site photos |

The script also accepts filenames containing `structural`, `architectural`, or `building under construction` (case-insensitive). Override with `--structural`, `--architectural`, or `--site`.

Optional branding inside the site folder (legacy fallback):

- `Construct_eye_full.png` — PDF/GUI logo if repo assets are not used
- `Construct_eye_logo.ico` — GUI window icon

---

## How to run

All commands below assume you start in `progress-reporting/src/`.

### 1 — Local PDF only (no Firebase)

```bash
cd progress-reporting/src
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload
```

### 2 — With live progress GUI (Pi display or desktop)

GUI opens automatically when `DISPLAY` is set; force it with `--gui`:

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload \
  --gui
```

Headless / SSH only:

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload \
  --no-gui
```

### 3 — Full pipeline with Firebase upload

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --firebase-key /path/to/firebase-key.json \
  --firebase-bucket YOUR_PROJECT_ID.appspot.com \
  --project-id YOUR_NUMERIC_PROJECT_ID \
  --gui
```

### 4 — Custom logo paths (matches current `assets/` layout)

Code defaults expect `assets/branding/`; if your logo is under `assets/Logo/`:

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload \
  --gui-logo "../../assets/Logo/Construct_eye_logo_picture.png" \
  --pdf-logo "../../assets/Logo/Construct_eye_logo_picture.png"
```

See [`../assets/README.md`](../assets/README.md) for details.

### 5 — Force re-scan of reference drawings

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload \
  --refresh-references
```

---

## CLI parameters

| Flag | Default | Description |
|------|---------|-------------|
| `folder` | `../../sample-site-images` (from `src/`) | Directory with reference + site photos |
| `--architectural` | auto-detect | Path to architectural reference |
| `--structural` | auto-detect | Path to structural reference |
| `--site` | all matches | Process a single site image only |
| `--location` | `DEVICE_LOCATION` env | Location label in report |
| `--reports-dir` | `../output/construction_reports` | PDF output directory |
| `--reference-cache-dir` | `../output/reference_metrics_cache` | Cached reference AI metrics |
| `--moondream-key` | `MOONDREAM_API_KEY` env | **Required** — Moondream API key |
| `--firebase-key` | `FIREBASE_SERVICE_ACCOUNT` env | Firebase admin JSON path |
| `--firebase-bucket` | `FIREBASE_STORAGE_BUCKET` env | Storage bucket name |
| `--no-upload` | off | Skip Firebase upload |
| `--project-id` | `CONSTRUCT_EYE_PROJECT_ID` env | Firestore project id |
| `--device-id` | auto UUID | Device document id in Firestore |
| `--stream-link` | `STREAM_LINK` env | Optional live stream URL on device record |
| `--gui` | auto if `DISPLAY` set | Show Tkinter progress window |
| `--no-gui` | off | Terminal-only mode |
| `--refresh-references` | off | Ignore cache; re-scan reference images |
| `--gui-icon` | env / assets | Window icon (`.ico` or `.png`) |
| `--gui-logo` | env / assets | Header logo in progress window |
| `--gui-theme` | `light` | Initial theme: `light` or `dark` |
| `--pdf-logo` | env / assets | Logo on PDF cover and inner pages |

---

## Expected output

### Terminal (startup)

```
[INFO] construction_progress_report.py v2.4.0
[INFO] Live progress window enabled
[INFO] Structural reference:  Structural View.png
[INFO] Architectural reference: Architectural View.png
[INFO] Site images: 1
[INFO] Structural reference metrics: using saved cache
[INFO] Architectural reference metrics: using saved cache
```

First run (no cache yet) shows `will scan with AI` instead of `using saved cache`.

### Terminal (during analysis)

```
[AI] Part 1 - Structural reference analysis
[AI] Part 2 - Architectural reference analysis
[AI] Part 1 - Structural site analysis
[AI] Part 2 - Architectural site analysis
[PDF] Saved: .../progress-reporting/output/construction_reports/construct_eye_report_YYYYMMDD_HHMMSS_SiteName.pdf
```

### Terminal (completion)

```
[DONE] Overall 67.3% | Structural 72.1% | Architectural 58.4% | Phase: Structural Works
[TIME] Report took 4m 12s (252.0s total - AI analysis, PDF, no upload)
```

With Firebase:

```
[INIT] Firebase connected (project_id=..., device=...)
[TIME] Report took 4m 45s (285.0s total - AI analysis, PDF, Firebase upload)
```

### GUI

Step-by-step sections with spinners, green checkmarks, bottom progress bar, and a **REPORT READY** summary (overall %, structural/architectural %, phase, PDF path, elapsed time).

### Files created locally

| Path | Contents |
|------|----------|
| `output/construction_reports/construct_eye_report_*.pdf` | Generated PDF |
| `output/reference_metrics_cache/*.json` | Cached reference metrics (speeds up later runs) |

### Cloud (when upload enabled)

| Destination | Contents |
|-------------|----------|
| Firebase Storage `construction_progress/` | Site photograph |
| Firebase Storage `construction_reports/pdf/` | PDF file |
| Firestore `construction_reports` | Report metadata + URLs |
| Firestore `notifications` + FCM | Push to owners/engineers |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `MOONDREAM_API_KEY is not set` | Export key or pass `--moondream-key` |
| `Folder not found` | Create `sample-site-images/` or pass a valid path |
| `Structural reference image not found` | Add `Structural View.png` or use `--structural` |
| `Cannot resolve api.moondream.ai` | Check Pi/desktop internet and DNS |
| `FIREBASE_SERVICE_ACCOUNT is not set` | Pass `--firebase-key` or use `--no-upload` |
| GUI fails over SSH | Use `--no-gui` |

---

## Related documentation

- Input image layout: [`../sample-site-images/README.md`](../sample-site-images/README.md)
- Logos and icons: [`../assets/README.md`](../assets/README.md)
- Firebase helpers: [`../shared/README.md`](../shared/README.md)
- Repository overview: [`../README.md`](../README.md)
