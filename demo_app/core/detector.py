# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Model wrapper: the project's trained emergency-vehicle detector + a COCO vehicle detector.

* EV model  : project/models/yolo_emergency_detector.pt (YOLOv8n, classes
              ambulance / fire brigade / police) -- the existing trained weights,
              loaded unchanged.
* COCO model: yolov8n.pt (Ultralytics pretrained, COCO classes) for ordinary
              vehicles (car, motorcycle, bus, truck), with ByteTrack so each
              vehicle is counted once instead of once per frame.
"""
import os
import time
from pathlib import Path

from .config import EV_MODELS, COCO_MODEL_CANDIDATES, COCO_VEHICLES, default_model_key


def find_coco_weights():
    for p in COCO_MODEL_CANDIDATES:
        if Path(p).exists():
            return str(p)
    return "yolov8n.pt"   # Ultralytics downloads it on first use (internet needed once)


class Detector:
    def __init__(self, dp, model_key=None):
        from ultralytics import YOLO   # imported lazily so the server starts fast
        key = model_key if (model_key in EV_MODELS and EV_MODELS[model_key]["path"].exists()) else default_model_key()
        path = EV_MODELS[key]["path"]
        if not path.exists():
            raise FileNotFoundError(f"Emergency model not found at {path}")
        self.dp = dp
        self.model_key, self.model_path = key, path
        self.ev = YOLO(str(path))
        self.coco = YOLO(find_coco_weights())
        self.ev_names = self.ev.names
        # EVP_DEVICE=cpu (default) | mps (Apple Silicon GPU) | 0 (first NVIDIA GPU)
        self.device = os.environ.get("EVP_DEVICE", "cpu")
        self.lat_ev, self.lat_coco = [], []

    def run(self, frame):
        """Returns (vehicles, ev_boxes). vehicles: [x1,y1,x2,y2,track_id|-1,cls,conf];
        ev_boxes: [x1,y1,x2,y2,conf,cls]."""
        t0 = time.perf_counter()
        r = self.coco.track(frame, persist=True, classes=list(COCO_VEHICLES), conf=self.dp.coco_conf,
                            imgsz=self.dp.imgsz, verbose=False, tracker="bytetrack.yaml",
                            device=self.device)[0]
        t1 = time.perf_counter()
        e = self.ev.predict(frame, conf=self.dp.ev_raw_conf, imgsz=self.dp.imgsz, verbose=False,
                            agnostic_nms=True, device=self.device)[0]
        t2 = time.perf_counter()
        self.lat_coco.append((t1 - t0) * 1000)
        self.lat_ev.append((t2 - t1) * 1000)
        veh = []
        b = r.boxes
        if b is not None and len(b):
            ids = b.id.int().tolist() if b.id is not None else [-1] * len(b)
            for xyxy, c, cf, tid in zip(b.xyxy.tolist(), b.cls.int().tolist(), b.conf.tolist(), ids):
                veh.append([round(v, 1) for v in xyxy] + [int(tid), COCO_VEHICLES.get(c, "car"), round(cf, 3)])
        evb = []
        if e.boxes is not None and len(e.boxes):
            for xyxy, c, cf in zip(e.boxes.xyxy.tolist(), e.boxes.cls.int().tolist(), e.boxes.conf.tolist()):
                evb.append([round(v, 1) for v in xyxy] + [round(cf, 3), self.ev_names[c]])
        return veh, evb
