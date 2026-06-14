# Sample site images

Input folder for the **construction progress report** generator. Put reference drawings and live site photos here, or point the script at any other directory.

**This folder is intentionally empty in the repo** — add your own images locally before running a report. Do not commit proprietary drawings to a public GitHub repo unless you have permission.

---

## Current folder structure

```
sample-site-images/
└── README.md          # This file only (add your images locally)
```

After you add files:

```
sample-site-images/
├── README.md
├── Structural View.png              # Structural reference (required)
├── Architectural View.png         # Architectural reference (required)
└── site_photo_june_2026.jpg        # One or more site photographs (required)
```

Supported formats: `.png`, `.jpg`, `.jpeg`, `.webp`

---

## What each image is for

| Role | Purpose | Used in report for |
|------|---------|-------------------|
| **Structural reference** | Design/drawing showing structure (columns, slabs, floors) | Target to compare against the live site — structural % |
| **Architectural reference** | Design/drawing showing finishes (facade, windows, roof) | Target to compare against the live site — architectural % |
| **Site photograph(s)** | Current photo of the building on site | AI analysis + PDF comparison panels |

The script sends these images to the **Moondream** vision API. You need `MOONDREAM_API_KEY` set (see [`../config.example.env`](../config.example.env)).

---

## How the script finds your files

When you run `construction_progress_report.py`, it scans the folder automatically.

### Structural reference

Picked if the **filename contains** (case-insensitive):

- `structural` or `structure`

Examples: `Structural View.png`, `structure_plan.jpg`

Override: `--structural /path/to/file.png`

### Architectural reference

Picked if the **filename contains**:

- `architectural` or `architecture`

Examples: `Architectural View.png`, `architecture_elevation.png`

Override: `--architectural /path/to/file.png`

### Site photograph(s)

**Every other image** in the folder that is **not** a reference drawing.

The script excludes files whose names contain:

- `structural`, `structure`, `architectural`, `architecture`, `reference`, or `design`

So site photos can have **any other filename** — for example:

- `site_photo_june_2026.jpg`
- `Building Under Construction.png` *(works, but not required in the name)*
- `IMG_4521.jpeg`

Reference images are also excluded by path after they are selected, even if the name would otherwise qualify.

Process one site photo only:

```bash
--site /path/to/one_site_photo.jpg
```

---

## How to run

From `progress-reporting/src/` (paths relative to that directory):

### Default folder (this directory)

```bash
cd progress-reporting/src
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload
```

If unset, the script default folder is `sample-site-images/` at the **repo root** (via `CONSTRUCT_EYE_IMAGE_DIR`).

### Custom folder

```bash
python3 construction_progress_report.py /path/to/my-project-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload \
  --gui
```

### Explicit image paths

```bash
python3 construction_progress_report.py /path/to/folder \
  --structural /path/to/folder/structure.png \
  --architectural /path/to/folder/facade.png \
  --site /path/to/folder/live_site.jpg \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --no-upload
```

### With Firebase upload

```bash
python3 construction_progress_report.py ../../sample-site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --firebase-key /path/to/firebase-key.json \
  --firebase-bucket YOUR_PROJECT_ID.appspot.com \
  --project-id YOUR_NUMERIC_PROJECT_ID
```

Full details: [`../progress-reporting/README.md`](../progress-reporting/README.md)

---

## Expected output (when images are valid)

```
[INFO] construction_progress_report.py v2.4.0
[INFO] Structural reference:  Structural View.png
[INFO] Architectural reference: Architectural View.png
[INFO] Site images: 1
[INFO] Structural reference metrics: will scan with AI
[INFO] Architectural reference metrics: will scan with AI
...
[PDF] Saved: .../progress-reporting/output/construction_reports/construct_eye_report_....pdf
[DONE] Overall 67.3% | Structural 72.1% | Architectural 58.4% | Phase: Structural Works
```

Second run may show `using saved cache` for references if they have not changed.

---

## Common errors

| Message | Cause | Fix |
|---------|-------|-----|
| `Folder not found` | Path wrong or folder missing | Create `sample-site-images/` or pass a valid path |
| `Structural reference image not found` | No file with `structural`/`structure` in name | Rename or use `--structural` |
| `Architectural reference image not found` | No file with `architectural`/`architecture` in name | Rename or use `--architectural` |
| `No site photograph found` | Only reference images in folder | Add at least one photo that is not a reference |
| `MOONDREAM_API_KEY is not set` | Missing API key | Set env var or `--moondream-key` |

---

## Optional branding in this folder

If you place logos here, the progress report may use them instead of repo assets:

| File | Used for |
|------|----------|
| `Construct_eye_full.png` | PDF cover logo (legacy fallback) |
| `Construct_eye_logo.ico` | GUI window icon (legacy fallback) |

Preferred branding location: [`../assets/`](../assets/README.md)

---

## Privacy / GitHub

- Keep real project drawings and site photos **local** or in a **private** storage bucket.
- This directory should contain only `README.md` in the public repo.
- Add images on each machine where you run reports (`git pull` will not bring them).

---

## Related

- Progress report CLI and flags: [`../progress-reporting/README.md`](../progress-reporting/README.md)
- Repository overview: [`../README.md`](../README.md)
