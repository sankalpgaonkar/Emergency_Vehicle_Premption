<!-- Copyright (c) 2026 Sankalp Gaonkar -->
# New components in v2 (Nov 2026)

Everything listed here was written for v2. All new files carry the header `Copyright (c) 2026 Sankalp Gaonkar`.
No original project file was modified except a note at the top of `README.md` pointing to `README_DEMO.md`, and six
lines at the end of `.gitignore` (seven since v3 was added) so that the new model files are not ignored by its `*.pt` rule.

| Path | What it is |
|---|---|
| `demo_app/app.py` | Flask server: upload, sample runs, job status, result, re-simulation, CSV export. |
| `demo_app/core/config.py` | Every parameter of the demo (thresholds, signal timing, simulation assumptions) in one place. |
| `demo_app/core/video_io.py` | File validation and browser-friendly H.264 transcoding (ffmpeg / imageio-ffmpeg). |
| `demo_app/core/detector.py` | Loads the EV detector (v2 or v1) + COCO YOLOv8n with ByteTrack; per-frame inference with timing. |
| `demo_app/core/ev_confirm.py` | EV tracking and the confirmation rule (SUSPECTED / CONFIRMED), nested-box suppression, causal class vote. |
| `demo_app/core/signal_controller.py` | Fixed-time cycle + preemption state machine (clearance, exclusive EV green, multi-EV queue, recovery, max hold). |
| `demo_app/core/simulation.py` | Four-approach microscopic simulation (IDM car-following, left-hand traffic, rescue-lane passing) and metrics. |
| `demo_app/core/pipeline.py` | Job orchestration: video → detections → tracks/counts → confirmation → two simulations → `result.json`. |
| `demo_app/static/` | Single-page dashboard (HTML/CSS/vanilla JS, no external libraries or CDNs): video overlay, intersection canvas, timeline, gauge, charts, event log, controls, dark/light theme. |
| `demo_app/evaluate.py` | Batch evaluation for the paper (measured detection results + simulated sweeps → JSON/CSV/Markdown). |
| `demo_app/tests/` | 29 pytest tests: controller safety invariants, confirmation rule, simulation, API and error handling, model selection (v3 loads and detects). |
| `demo_app/samples/` | Five CC-licensed real clips (Wikimedia Commons, credits in `CREDITS.md`) + the original placeholder clip. |
| `demo_app/weights/yolov8n.pt` | Ultralytics COCO-pretrained YOLOv8n (third-party, AGPL-3.0), for ordinary vehicles. |
| `training/make_clean_split.py` | Near-duplicate-aware re-split of the dataset (difference hash + union-find). |
| `training/train_ev_detector.py` | Reproducible training of the v2 detector. |
| `training/dataset_audit.py` | Source families and train/test similarity of the dataset. |
| `training/make_all_data_yaml.py` | Builds the all-images training set for the deployment model. |
| `training/bench_latency.py` | CPU latency of several models under identical conditions. |
| `training/eval_detectors.py` | v1 vs v2 on the clean split, the original split and external Wikimedia photos; CPU latency. |
| `training/external_test_manifest.json` | List, labels and credits of the 152 external test photos (download links included). |
| `training/runs/` | Training curves, confusion matrices, `results.csv`, `args.yaml` of the three v2 training runs (YOLOv8n and YOLO11n on the filtered split; YOLOv8n on all images). |
| `project/models/ev_detector_v2_sankalp.pt` (+ `.json`) | v2 default emergency-vehicle detector (see README_DEMO §7). |
| `project/models/ev_detector_v2_alt.pt` (+ `.json`) | YOLO11n detector trained on the same split, for comparison. |
| `project/models/ev_detector_v3_sankalp.pt` (+ `.json`) | v3 detector (added 3 Nov 2026): YOLOv8n on the 1,065 images + 442 new openly licensed images, many Indian. Selectable; v2 stays the default (README_DEMO §7.1). |
| `docs/data_credits/` | Per-image source, author and licence of the new images used to train v3. |
| `training/yolov8n.pt`, `training/yolo11n.pt` | Ultralytics COCO-pretrained starting weights (third-party, AGPL-3.0). |
| `docs/PROJECT_REVIEW.md` | Review of v1: what runs, bugs, measured results, leakage, secrets, provenance and licences. |
| `docs/ARCHITECTURE.md` | System architecture with diagrams. |
| `docs/METHODOLOGY.md` / `.pdf` | Research-paper-ready methodology, measured vs simulated results, experiments, limitations. |
| `docs/research/` | Comparable projects and verified references. |
| `docs/screenshots/` | Screenshots of the v2 dashboard. |
| `docs/demo/EVP_v2_demo.mp4` | 63-second screen recording of the demo (Toronto clip, default model). |
| `docs/figures/` | Architecture and state-machine diagrams (PNG). |
| `docs/results/` | Raw evaluation outputs used in the methodology (`docs/results/v3/` for v3). |
| `README_DEMO.md` | Setup (macOS, Windows, Linux), demo script, troubleshooting. |

## New dependencies

`flask`, `imageio-ffmpeg`, `lap` (plus `ultralytics`, already used in v1). Licences are listed in
`docs/PROJECT_REVIEW.md` §6.2. The v2 app does **not** need `transformers`, `sumo`, `sumo-rl`, `stable-baselines3`
or `flask-socketio`.
