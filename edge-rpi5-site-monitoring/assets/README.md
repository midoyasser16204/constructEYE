# Assets

Static images used by the progress-report GUI, PDF reports, and project documentation.

## Current folder structure

```
assets/
├── Logo/
│   └── Construct_eye_logo_picture.png   # Construct Eye logo (PNG)
├── device/
│   └── Actual device picture.png        # Photo of the deployed hardware
└── README.md
```

| File | Size role | Used for |
|------|-----------|----------|
| `Logo/Construct_eye_logo_picture.png` | Brand logo | Progress GUI header, PDF cover/logo |
| `device/Actual device picture.png` | Hardware photo | README / documentation illustrations |

There is **no `.ico` file** in this folder right now. The progress GUI can fall back to the PNG for the window icon, or you can add one (see below).

## How the code finds these files

By default, the progress report scripts look under `assets/branding/` with lowercase names:

| Code default | Actual file today |
|--------------|-------------------|
| `assets/branding/construct_eye_logo.png` | `assets/Logo/Construct_eye_logo_picture.png` |
| `assets/branding/construct_eye_logo.ico` | *(not present)* |

Until paths are aligned, point the apps at the real files with environment variables (from the repo root):

```bash
export CONSTRUCT_EYE_GUI_LOGO="./assets/Logo/Construct_eye_logo_picture.png"
export CONSTRUCT_EYE_PDF_LOGO="./assets/Logo/Construct_eye_logo_picture.png"
# Optional — only if you add a .ico file:
# export CONSTRUCT_EYE_GUI_ICON="./assets/Logo/construct_eye_logo.ico"
```

Or pass flags when running the progress report:

```bash
cd progress-reporting/src
python3 construction_progress_report.py /path/to/site-images \
  --moondream-key YOUR_MOONDREAM_API_KEY \
  --gui-logo "../../assets/Logo/Construct_eye_logo_picture.png" \
  --pdf-logo "../../assets/Logo/Construct_eye_logo_picture.png"
```

## Recommended layout (optional, matches code defaults)

For zero-config runs, you can reorganize once to match what the Python defaults expect:

```bash
# From repo root
mkdir -p assets/branding
cp "assets/Logo/Construct_eye_logo_picture.png" assets/branding/construct_eye_logo.png
# If you have a window icon file:
# cp /path/to/your/icon.ico assets/branding/construct_eye_logo.ico
```

Target layout after rename:

```
assets/
├── branding/
│   ├── construct_eye_logo.png
│   └── construct_eye_logo.ico    # optional
└── device/
    └── device_photo.png          # optional rename of Actual device picture.png
```

After that, the defaults in `config.example.env` work without extra flags:

```bash
export CONSTRUCT_EYE_GUI_ICON=./assets/branding/construct_eye_logo.ico
export CONSTRUCT_EYE_GUI_LOGO=./assets/branding/construct_eye_logo.png
export CONSTRUCT_EYE_PDF_LOGO=./assets/branding/construct_eye_logo.png
```

## GitHub note

Image files are safe to commit (no secrets). Use clear, lowercase filenames in `assets/branding/` before publishing if you want a cleaner public repo.

## No run command

These are static files — not executed directly. See [`../progress-reporting/README.md`](../progress-reporting/README.md) for how they are loaded at runtime.
