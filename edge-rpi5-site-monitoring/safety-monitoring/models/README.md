# ML models

Model weights and training artifacts for PPE detection.

## Deployment model (required on Pi)

| File | Format | Purpose |
|------|--------|---------|
| `yolov8n.hef` | Hailo HEF | **Production inference** on Hailo-8 NPU |
| `best.pt` | PyTorch | Optional — desktop re-export / retraining |
| `best.onnx` | ONNX | Optional — cross-platform export |

The safety monitor loads **`yolov8n.hef`** automatically from this folder.

> **GitHub note:** Large weight files are in `.gitignore`. Use Git LFS, a release download, or copy from your training machine to the Pi at:
> `safety-monitoring/models/yolov8n.hef`

## Training artifacts

`yolov8-ppe-training/` contains YOLOv8s training outputs:

- `args.yaml` — training hyperparameters (paths sanitized to placeholders)
- `results.csv`, `results.png` — metrics curves
- `weights/` — checkpoint `.pt` files and exported TFLite/SavedModel

These are **reference only** for documentation and retraining — not used at runtime on the Pi.

## Re-export to Hailo HEF

After retraining, compile your best weights to `.hef` using the Hailo Model Zoo / Dataflow Compiler toolchain, then replace `yolov8n.hef`.

## Class labels (PPE model)

| ID | Class |
|----|-------|
| 0 | Helmet |
| 1 | Person |
| 2 | Safety vest |

## No standalone run command

Models are consumed by `../site_safety_monitor/site_safety_monitor.py`. See [safety monitoring README](../README.md).
