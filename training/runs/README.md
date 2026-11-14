# Training runs (3 Nov 2026)

| Folder | Model | Weights kept |
|---|---|---|
| `ev_detector_v2/` | A: YOLOv8n, near-duplicate-filtered split | `weights/best.pt` (epoch 76) |
| `ev_detector_v2_yolo11n/` | B: YOLO11n, same split | `weights/best.pt` (epoch 63); also installed as `project/models/ev_detector_v2_alt.pt` |
| `ev_detector_v2_all_yolov8n/` | C: YOLOv8n, all 1,065 images (app default) | final epoch, installed as `project/models/ev_detector_v2_sankalp.pt` (not duplicated here) |

Duplicate `last.pt` files were removed to keep the download small. The COCO starting weights (`yolov8n.pt`, `yolo11n.pt`)
are downloaded automatically by Ultralytics when `training/train_ev_detector.py` runs.
`train_info.json` gives the training time; `args.yaml` the exact settings; `results.csv` every epoch.
