# Project review — Emergency Vehicle Preemption (v1 → v2)

*Review carried out 3 Nov 2026 on `github.com/sankalpgaonkar/Emergency_Vehicle_Premption` (commit `3e57426`).
Every statement below was checked by running or reading the code on a Linux machine (16 CPU cores, Python 3.11,
Ultralytics 8.4.199, Flask 3.1.3, Flask-SocketIO 5.7.2, SUMO 1.x). Nothing here is estimated.*

## 1. What the project contains

| Part | Files | Status found |
|---|---|---|
| Emergency-vehicle detector (YOLOv8n, 3 classes: ambulance, fire brigade, police) | `project/models/yolo_emergency_detector.pt`, training run in `runs/detect/train/` | **Works.** Loads and runs on CPU at ~14–15 ms per frame. Training log: val mAP50 0.854 at epoch 50 (best 0.888 at epoch 44). |
| Dataset | `project/datasets/emergency_vehicles/` (Roboflow export, 1,065 images) | Present. 94 % of images come from three videos; the original split has near-duplicates across train/test (Section 4). |
| PPO signal agent (Stable-Baselines3) | `project/models/ppo_traffic_model_v2.zip`, `..._v3.zip`, `src/ai_core/train.py` | **Untrained.** Both zips are byte-identical and contain `num_timesteps = 0`, `_n_updates = 0`: the policy was saved before any learning. |
| SUMO scenario (Jaipur junction J5) | `project/sumo_files/*.xml` | Network and routes present; `*.sumocfg` files are excluded by `.gitignore`, so `sumo -c` configs are missing. |
| Live/vision scripts | `src/vision/run_live.py`, `new_run_live.py`, `processor.py`, `emergency_vehicle_detection.py` | Run only with a display and the `transformers` package; see Section 3. |
| Dashboards | `src/api/app.py`, `src/extensions/enhanced_dashboard.py`, `simple_3d_system.py`, `web_3d_visualization.py`, `integrated_3d_system.py`, `unity_3d_integration.py` | Only `enhanced_dashboard.py` starts on a current install (Section 3). |
| Preemption controller (Oct 2026 extension) | `src/extensions/preemption_controller.py` | Works as a wall-clock state machine: 3 detections ≥ 0.50 within 2.5 s → cross-traffic yellow 3.5 s → all-red 1.5 s → emergency green for a fixed 12 s → yellow → all-red → normal. One "emergency lane" vs "cross lane", no approach direction. |
| Sample videos | `project/videos/emergency2.mp4`, `intersection1.mp4`, `intersection2.mp4` | **Synthetic.** 5-second clips of drawn rectangles labelled "CAR"/"AMBULANCE". `intersection1.mp4` and `intersection2.mp4` are identical files (same MD5). |

## 2. Detector results on the sample videos (measured)

Both models were run on every 3rd frame (conf ≥ 0.25 for the EV model, ≥ 0.35 for COCO vehicles):

| Video | Frames | EV model detections | COCO vehicle detections |
|---|---|---|---|
| emergency2.mp4 (repo) | 150 | 0 | 0 |
| intersection1.mp4 (repo) | 150 | 0 | 0 |
| intersection2.mp4 (repo) | 150 | 0 | 0 |

The repository videos cannot demonstrate detection, because they contain no real vehicles. v2 therefore ships five
openly licensed real clips from Wikimedia Commons (`demo_app/samples/CREDITS.md`). With the **original model (v1)**,
measured by the v2 pipeline (15 analysed frames/s, confirmation rule 5 consecutive frames ≥ 0.50):

| Clip (true EV) | Vehicles counted | EV result (v1) |
|---|---|---|
| Edinburgh junction (ambulance) | 21 | confirmed 8.55 s as ambulance (later frames mostly "police"); plus 1 suspected-only track(s), max 0.60 |
| Busy road, night (ambulance) | 19 | confirmed 0.28 s as ambulance |
| New York, night (ambulance) | 16 | suspected only (max 0.74) |
| Tokyo intersection (ambulance) | 34 | confirmed 0.27 s as ambulance; plus 2 suspected-only track(s), max 0.77 |
| Toronto street (fire brigade) | 6 | confirmed 2.87 s as ambulance (later frames mostly "fire brigade"); plus 1 suspected-only track(s), max 0.40 |
| v1 placeholder clip (synthetic drawing) (none) | 0 | nothing |

The v1 model works on real footage but makes class errors and low-confidence false detections; the confirmation rule
keeps those from triggering preemption. The new models are compared with it in `docs/METHODOLOGY.md` §9.1.

## 3. Bugs and broken pieces found

1. **Sample videos are placeholders** (above). Anything shown with them is not real detection.
2. **PPO models are untrained** (`num_timesteps = 0` inside both zips; v2 and v3 are the same file). Any "AI decision"
   shown by `run_live.py` / `run_with_sumo.py` comes from a randomly initialised network.
3. **State mismatch in `run_live.py`** (still present): the policy input is built as raw video zone counts concatenated
   with part of the SUMO observation, so the counts overwrite the phase/density slots of the 19-value sumo-rl observation,
   unscaled. Even a trained policy would receive meaningless inputs.
4. **Fallback fake data**: if SUMO cannot start, `run_live.py` silently switches to a built-in `MockSumoEnv`; and random "demo traffic" is injected by `run_live.py` every 200 frames when nothing is detected (lines ~405–411), and
   random zone counts are generated in another branch (lines ~376–385). Any measurement must switch these off.
5. **Dashboards crash on current Flask-SocketIO**: `src/api/app.py`, `simple_3d_system.py`, `web_3d_visualization.py` and `integrated_3d_system.py`
   stop with `RuntimeError: The Werkzeug web server is not designed to run in production` (Flask-SocketIO ≥ 5.3 requires
   `allow_unsafe_werkzeug=True` for the development server).
6. **Heavy hidden dependency**: `processor.py` imports `transformers` (an image classifier used only to give vehicles
   cosmetic names). Without it, `run_live.py`, `new_run_live.py`, `integrated_3d_system.py`, `unity_3d_integration.py`
   and `debug_zones.py` fail at import.
7. **Display required**: `emergency_vehicle_detection.py` and `run_live.py` use `cv2.imshow`; `run_with_sumo.py` starts
   `sumo-gui`. They abort on a machine without a display. `emergency_vehicle_detection.py` also downloads `yolov8m.pt`
   (50 MB) at start-up.
8. **Missing SUMO configs**: `.gitignore` excludes `*.sumocfg`, so `jaipur.sumocfg` / `baseline.sumocfg` are not in the repo.
9. **Mac-only paths**: `integrated_3d_system.py` and `unity_3d_integration.py` default `SUMO_HOME` to
   `/opt/homebrew/share/sumo`; the SUMO `.net.xml` headers contain absolute macOS paths (harmless comments).
10. **Results files are not comparable**: `baseline_results*.csv` (cumulative time loss spread over the hour) and
    `results*.csv` (instantaneous waiting time) measure different things, so no improvement percentage can be read from them.
11. **`launch.py`** asks for keyboard input in interactive mode (fails when run non-interactively). `--component` works.
12. **Broken link**: `config.json` points to `github.com/sankalpgaonkar/AI-Traffic-Management-System`, which returns 404.
13. **Hard-coded Flask `SECRET_KEY` strings** in six scripts. Low risk for a local demo; read them from an environment
    variable before any deployment.
14. **No real tests**: `test_model_loading.py` checks imports; `test_dashboard_connection.py` needs a running server.

What works: the detector itself, `enhanced_dashboard.py` (port 5002), `preemption_controller.py`,
`test_model_loading.py`, and the SUMO network with `sumo-rl`.

## 4. Dataset: near-duplicates and low source diversity (measured)

**Near-duplicates across the original split.** Most images are frames from a few videos, split at random. Each image
was reduced to a 256-bit difference hash (dHash). At a near-duplicate threshold of ≤ 20 differing bits,
**48 / 107 test images and 115 / 213 validation images have a near-duplicate in the training set** (median distance
from a test image to its nearest training image: 23 bits). Accuracy on that split mostly measures recognition of frames
the model has already seen.

**Source diversity.** The Roboflow file names show where the images come from (`training/dataset_audit.py`):

| Source family (file-name prefix) | Images | Classes |
|---|---|---|
| `frame-NNN` (video frames) | 490 | 284 ambulance, 208 police, 1 fire brigade |
| `sjnskj (N)` (video frames) | 280 | police only |
| `csm-sc-N-` (video frames) | 230 | ambulance only |
| single web images | 65 | 34 ambulance, 17 police, 15 fire brigade |

So **94 % of the dataset comes from three video sources**, two of which contain only one class each, and fire brigade
has 16 images in total. A detector trained on this data can learn the scenes rather than the vehicles.

**v2 split.** `training/make_clean_split.py` groups near-duplicates (≤ 20 bits, union-find, 574 groups) and keeps
each group inside one split: 745 train / 160 val / 160 test, no test image within 20 bits of a training image. This
removes the exact repeats but **not** the same scenes. 34 of the 160 test images are still within 30 bits of a training
image, and visual inspection confirms they show the same scene a moment later. Stricter thresholds (40 bits, tried)
still leave same-scene pairs, because flashing lights change the hash while the scene stays the same. **A truly
leakage-free split of this dataset is not possible without dropping whole sources.** Therefore:

* the in-dataset test score is reported as a *within-source* score, and
* the fair measure of generalisation is the **external test set**: 152 Wikimedia Commons photographs that neither model
  has seen (see the methodology, §3.2 and §9.1).

## 5. Secrets scan

Searched the working tree and full git history of this repository for API keys, tokens and passwords
(patterns for Google, GitHub, OpenAI and RapidAPI keys, plus `api_key`, `secret`, `token`, `password`).

* No live key or token is committed in this repository. `project/src/vision/apikeys.txt` is listed in `.gitignore`
  and is not in the history.
* Hard-coded Flask `SECRET_KEY` strings (item 13 above).
* The earlier public v1 repository (2025) still contains `project/src/vision/apikeys.txt` with what looks like a
  RapidAPI key. It should be revoked.
  It is not used by v2.

## 6. Provenance and third-party components

### 6.1 Origin of the code

The v1 code base (the original codebase and detector) was first published on 14 Oct 2025 in an earlier public
repository (no licence file), then continued in this repository (created 3 Nov 2026, MIT licence file). A file-by-file comparison (byte-identical check, then `diff`):

| Category | Files |
|---|---|
| Identical to the 2025 v1 repository | 48 tracked files outside the dataset, including `runs/detect/train/*` (training curves and `results.csv`), the whole dataset folder, `assests/*`, SUMO routes, `processor.py`'s siblings, results CSVs |
| Same as 2025 apart from an added author line / SUMO_HOME default | `src/api/app.py`, `simple_3d_system.py`, `web_3d_visualization.py`, `integrated_3d_system.py`, `unity_3d_integration.py`, `vision/emergency_vehicle_detection.py`, `requirements.txt` (+yt-dlp), `config.json`, `3D_SYSTEM_GUIDE.md`, `QUICK_START.md`, SUMO `.net.xml` (paths) |
| Changed in 2026 (20–40 changed lines each) | `launch.py`, `vision/run_live.py` (adds a SUMO_HOME default and a `MockSumoEnv` fallback that simulates traffic when SUMO is missing), `vision/processor.py`, `README.md`, `.gitignore` |
| Added in this repository (Oct–Nov 2026) | `src/extensions/` (detection engine, preemption controller, video processor, enhanced dashboard), `project/models/*.zip` (untrained PPO), `project/models/yolo_emergency_detector.pt`, `project/videos/*`, `results/preemption_logs/`, `LICENSE` |
| New in v2 (this rebuild) | `demo_app/`, `training/`, `docs/`, `README_DEMO.md`, `NEW_COMPONENTS.md`, `CONTRIBUTORS.md`, `project/models/ev_detector_v2_sankalp.pt`, `training/runs/ev_detector_v2/` |

Note on the detector: `project/models/yolo_emergency_detector.pt` is byte-identical (MD5 `175bdbbfe2b6853a95968510dddf3829`)
to `runs/detect/train/weights/last.pt` of the 2025 repository, and this repository's `runs/detect/train/results.csv` is
identical to the 2025 one (`args.yaml` differs only in `save_dir`). The v1 detector is therefore the 2025 v1 training run.
The v2 detector was trained afresh on 3 Nov 2026 (`training/`), see the methodology document.

**Licence of the v1 code.** The 2025 repository has no licence file; this repository has an MIT `LICENSE`.

### 6.2 Third-party libraries, models, data and media

| Component | Used for | Licence | What it means here |
|---|---|---|---|
| **Ultralytics YOLOv8** (`ultralytics` package, `yolov8n.pt` COCO weights) | detection, tracking, training | **AGPL-3.0** (Enterprise licence available from Ultralytics) | Free for study and open-source projects. If you **distribute** the app, or run it as a **network service** for others, you must make the complete source of the combined program available under AGPL-3.0. Ultralytics states that "all Ultralytics YOLO trained models fall under the AGPL-3.0 License by default" (https://www.ultralytics.com/license), so both detectors here (v1 and v2) do too, unless an Enterprise licence is bought. Keeping the project open-source on GitHub satisfies this; a closed commercial product would need the Enterprise licence. Your own MIT-licensed files stay MIT, but the combined program, as distributed, follows AGPL-3.0. |
| ByteTrack (via Ultralytics) | vehicle tracking | MIT (original), shipped inside Ultralytics | — |
| PyTorch / torchvision | inference/training | BSD-style (PyTorch licence; bundled parts list Apache-2.0, MIT and others) | — |
| OpenCV (`opencv-python-headless`) | video reading/drawing | Apache-2.0 | — |
| Flask | web server | BSD-3-Clause | — |
| imageio-ffmpeg / FFmpeg | transcoding (bundled ffmpeg binary) | imageio-ffmpeg BSD-2-Clause; the FFmpeg binary is LGPL/GPL depending on build | Fine for running; if you redistribute the ffmpeg binary itself, keep its licence notice. |
| Stable-Baselines3 | PPO (v1) | MIT | — |
| sumo-rl | RL environment (v1) | MIT | — |
| Eclipse SUMO | traffic simulation (v1) | EPL-2.0 (with GPL-2.0-or-later secondary licence) | Using SUMO as a tool imposes nothing on your code. |
| Roboflow "Emergency vehicle" dataset v1, `universe.roboflow.com/jd-s39ap/emergency-vehicle-crigt` | training data | **CC BY 4.0** (stated in `data.yaml` and `README.roboflow.txt`) | Attribution required: credit the dataset (author handle `jd-s39ap`, Roboflow Universe, CC BY 4.0) in the paper and README. Individual images were collected by that user; their original sources are not documented. |
| Sample clips in `demo_app/samples/` | demo videos | CC BY 4.0, CC BY-SA 4.0, CC BY 3.0 (per file) | Credit each author as in `demo_app/samples/CREDITS.md`. Re-encoded copies of CC BY-SA clips stay CC BY-SA. |
| `transformers` + DeiT classifier (v1 `processor.py`) | cosmetic vehicle names | Apache-2.0 | Not used by v2. |

v2 copies no code from other projects. Ideas from comparable open-source projects (Section 7) were re-implemented
independently. Several of those projects are AGPL-3.0 or have no licence at all, so their code must not be copied.

## 7. Comparable projects and what v2 took from them

See `docs/research/comparable_projects.md` for the full list (URLs, licences, what each actually does). Ideas used in v2:

* **Confirmation over consecutive frames** and **holding green until the EV has cleared** rather than for a fixed time
  (described in FWZ8804/greencorridor, implemented in kafle1/relay).
* **Always yellow + all-red before a conflicting green**. Some projects switch conflicting lights straight to red
  (e.g. Gianvi-lan/carla-emergency-preemption), which signal standards do not allow (MUTCD 11th ed., Sections 4F.18–4F.19).
* **Same arrivals, fixed-time vs preemption** comparison (kafle1/relay `compare.html`; CARLA project's benchmark design).
* **Maximum preemption hold** so a stuck detection cannot freeze the junction (kafle1/relay `max_preempt`).
* **Priority + arrival-order queue for several EVs** (CARLA project's multi-vehicle test).
