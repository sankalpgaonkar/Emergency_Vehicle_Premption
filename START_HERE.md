# Emergency Vehicle Preemption: start here

This folder is the COMPLETE project: original code + SUMO files + Roboflow dataset + v1/v2/v3 models + the demo app + training scripts + docs.

## Run it in Antigravity (or VS Code)
1. Unzip all 3 parts into the SAME place. They merge into one `Emergency_Vehicle_Preemption` folder.
2. In Antigravity: File > Open Folder > choose `Emergency_Vehicle_Preemption`.
3. Open the terminal (Ctrl+` ) and run:
   - Mac/Linux: `./run_mac.sh`
   - Windows: `run_windows.bat`
   The first run creates `.venv` and installs the packages (needs Python 3.10-3.12 and internet, about 5-10 min). Later runs start in seconds.
4. Open http://127.0.0.1:5050 and click Run on "Toronto - fire truck responding".

You can also use Run and Debug (left sidebar) > "Run EV demo app" once `.venv` exists, and select the `.venv` Python interpreter if asked.

## Models (dropdown in the app)
- v2: default, fewest false alarms on general photos
- v3: + Indian images, better on Indian roads and clips
- v1: the original 2025 detector
- v2alt: YOLO11n

## Check everything works
`source .venv/bin/activate && python -m pytest -q demo_app/tests` should show 29 passed.

## Where things are
- `demo_app/`: the web demo (detection + junction simulation)
- `project/`: original SUMO simulation, models, dataset (`project/datasets`)
- `training/`: retrain/evaluate scripts
- `docs/`: methodology (PDF + MD), review, results, image credits
- `README_DEMO.md`: full guide + 3-minute presentation script
