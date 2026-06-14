# Shared modules

Common Python utilities used by both **safety monitoring** and **progress reporting**.

## Contents

| File | Description |
|------|-------------|
| `firebase_common.py` | Firebase Firestore/FCM helpers, device registration, weather updates, notification builders |

## What this code does

- Registers edge devices in Firestore (`devices` collection)
- Creates in-app notifications and sends FCM push messages to project users
- Auto-detects device location (GPS → IP → reverse geocode) and refreshes weather every 30 minutes
- Builds notification title/body text for PPE violations, falls, idle alerts, and progress reports

## Configuration (environment variables)

Set these in `.env` (see root `config.example.env`):

| Variable | Placeholder | Description |
|----------|-------------|-------------|
| `CONSTRUCT_EYE_PROJECT_ID` | `0` | Numeric project id stored in Firestore documents |
| `SITE_NAME` | `YOUR_SITE_NAME` | Human-readable site label |
| `DEVICE_LOCATION` | `YOUR_CITY, YOUR_COUNTRY` | Fallback address when geolocation fails |
| `FALLBACK_LATITUDE` | `0.0` | Default latitude when auto-detect fails |
| `FALLBACK_LONGITUDE` | `0.0` | Default longitude when auto-detect fails |
| `DEVICE_ID` | (auto UUID) | Stable device document id |

## How other modules import this

Scripts add `shared/` to `sys.path` automatically. You can also run with:

```bash
export PYTHONPATH="/path/to/construct-eye/shared:$PYTHONPATH"
python3 your_script.py
```

## No standalone run command

This folder is a **library**, not an executable. Run the applications in `safety-monitoring/site_safety_monitor/` or `progress-reporting/src/` instead.
