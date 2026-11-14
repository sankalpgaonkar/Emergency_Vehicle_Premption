# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Default parameters for the demo. Every value here is a modelling choice,
not a measurement; the UI shows them and lets the presenter change them."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = DEMO_DIR.parent
EV_MODEL_PATH = REPO_ROOT / "project" / "models" / "yolo_emergency_detector.pt"
# Emergency-vehicle detectors the app can use.
#   "v2"    best model retrained for this version on the near-duplicate-filtered split (training/) = the default
#   "v2alt" the other architecture trained on the same split (kept for comparison)
#   "v1"    the original project model (2025 v1 training run)
#   "v3"    YOLOv8n trained on the original 1,065 images + 442 new openly licensed images (many Indian), 3 Nov 2026.
#           Selectable only; v2 stays the default. Measured comparison: docs/METHODOLOGY.md section 4.4 / 9.5.
# A small JSON next to each v2 file says which architecture it is (written when the weights are installed).
_MD = REPO_ROOT / "project" / "models"


def _label(path, fallback):
    meta = path.with_suffix(".json")
    if meta.exists():
        try:
            return json.loads(meta.read_text()).get("label", fallback)
        except Exception:
            return fallback
    return fallback


EV_MODELS = {
    "v2": {"path": _MD / "ev_detector_v2_sankalp.pt"},
    "v2alt": {"path": _MD / "ev_detector_v2_alt.pt"},
    "v1": {"path": EV_MODEL_PATH, "label": "v1 · original model (2025)"},
    "v3": {"path": _MD / "ev_detector_v3_sankalp.pt"},
}
EV_MODELS["v2"]["label"] = _label(EV_MODELS["v2"]["path"], "v2 · retrained on near-duplicate-filtered split (Nov 2026)")
EV_MODELS["v2alt"]["label"] = _label(EV_MODELS["v2alt"]["path"], "v2 alternative architecture (Nov 2026)")
EV_MODELS["v3"]["label"] = _label(EV_MODELS["v3"]["path"], "v3 · + Indian images (2026)")

# One-line hint shown under the model dropdown. Numbers are MEASURED (conf 0.5); see docs/METHODOLOGY.md.
EV_MODELS["v2"]["hint"] = "Default. Fewest false alarms on general photos (20/98)."
EV_MODELS["v3"]["hint"] = ("Better on Indian roads & clips (Indian police 11/15 vs 6/15, clips 4/5 vs 3/5); "
                           "more false alarms on general photos (26/98 vs 20/98).")


def default_model_key():
    return "v2" if EV_MODELS["v2"]["path"].exists() else "v1"


# General (COCO) vehicle detector. The EV model only knows 3 emergency classes,
# so ordinary cars/buses/trucks/motorcycles are counted with a COCO model.
COCO_MODEL_CANDIDATES = [DEMO_DIR / "weights" / "yolov8n.pt", REPO_ROOT / "yolov8n.pt",
                         REPO_ROOT / "yolov8s.pt", REPO_ROOT / "yolov8m.pt"]
DATA_DIR = DEMO_DIR / "data"          # uploads + job outputs (git-ignored)
SAMPLES_DIR = DEMO_DIR / "samples"

ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".ogv"}
MAX_UPLOAD_MB = 300
MAX_PROCESS_SECONDS = 180      # longer videos are processed up to this point (stated in the result)

APPROACHES = ["N", "E", "S", "W"]
APPROACH_NAMES = {"N": "North", "E": "East", "S": "South", "W": "West"}
COCO_VEHICLES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
EV_CLASSES = ["ambulance", "fire brigade", "police"]


@dataclass
class DetectionParams:
    process_fps: float = 15.0        # frames per second actually analysed
    imgsz: int = 640
    coco_conf: float = 0.30
    ev_raw_conf: float = 0.20        # everything above this is stored (raw evidence)
    min_track_hits: int = 3          # a vehicle must be seen in >= 3 analysed frames to be counted


@dataclass
class ConfirmParams:
    suspect_conf: float = 0.35       # >= this: shown as SUSPECTED, never preempts
    confirm_conf: float = 0.50       # >= this ...
    confirm_frames: int = 5          # ... in this many consecutive analysed frames => CONFIRMED
    lost_after_s: float = 1.5        # track considered gone after this long without a box
    priority: dict = field(default_factory=lambda: {"ambulance": 1, "fire brigade": 1, "police": 2})


@dataclass
class SignalParams:
    green_ns: float = 20.0
    green_ew: float = 20.0
    yellow: float = 3.0
    all_red: float = 2.0
    preempt_min_green: float = 4.0
    preempt_max_green: float = 45.0
    initial_state: str = "video_red"  # video_red | video_green | NS | EW
    cycle_offset_s: float = 0.0       # seconds into the fixed cycle at t = 0 (0 = start of the initial green)


@dataclass
class SimParams:
    video_approach: str = "N"
    densities: dict = field(default_factory=lambda: {"E": None, "S": None, "W": None})  # veh/min; None = mirror observed
    continue_after_video: bool = True
    camera_distance_m: float = 90.0  # assumed distance from camera to stop line
    approach_length_m: float = 100.0
    tail_s: float = 25.0              # keep simulating this long after the last EV left
    min_duration_s: float = 40.0
    max_duration_s: float = 300.0
    dt: float = 0.1
    seed: int = 7
    drive_side: str = "left"          # India drives on the left
    rescue_lane: bool = True          # ordinary vehicles let the EV pass up to the stop line
    inject: list = field(default_factory=list)   # [{"approach":"E","t":8.0,"cls":"fire brigade"}]


def to_dict(*objs):
    out = {}
    for o in objs:
        out[type(o).__name__] = asdict(o)
    return out
