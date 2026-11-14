# Raw results (3 Nov 2026)

| File | Content |
|---|---|
| `dataset_audit.json` | source families and train/test similarity (`training/dataset_audit.py`) |
| `detector_eval_*.json` | in-dataset and external-photo evaluation per model (`training/eval_detectors.py`); `original_test` values are on the leaky original split and are for reference only |
| `clips_*.json / .csv / .md` | `demo_app/evaluate.py` on the six clips for C (key v2), B (key v2alt) and v1: measured tracks, confirmation sweep and every simulated run |
| `clips_measured_A_yolov8n_split.json` | measured clip results for model A (re-analysed from its stored detections with the final confirmation code) |
| `latency_cpu.json` | `training/bench_latency.py` |

Models: v1 = project/models/yolo_emergency_detector.pt; A = training/runs/ev_detector_v2/weights/best.pt;
B = project/models/ev_detector_v2_alt.pt; C = project/models/ev_detector_v2_sankalp.pt.
