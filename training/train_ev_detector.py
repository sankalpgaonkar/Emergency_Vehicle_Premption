# Copyright (c) 2026 Sankalp Gaonkar

"""Train a fresh YOLOv8n emergency-vehicle detector (ambulance / fire brigade / police)
from COCO-pretrained yolov8n.pt on the near-duplicate-filtered split made by make_clean_split.py.

Usage:  python training/train_ev_detector.py --data <split>/data.yaml --epochs 60
"""
import argparse, json, time, platform
from ultralytics import YOLO
ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--weights", default="yolov8n.pt")
ap.add_argument("--epochs", type=int, default=60)
ap.add_argument("--imgsz", type=int, default=640)
ap.add_argument("--batch", type=int, default=16)
ap.add_argument("--device", default="cpu")
ap.add_argument("--project", default="training/runs")
ap.add_argument("--name", default="ev_detector_v2")
ap.add_argument("--patience", type=int, default=20)
a = ap.parse_args()
t0 = time.time()
model = YOLO(a.weights)
model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device, project=a.project,
            name=a.name, exist_ok=True, patience=a.patience, seed=0, deterministic=True, workers=8, plots=True)
info = {"train_seconds": round(time.time() - t0, 1), "args": vars(a), "machine": platform.platform(),
        "processor": platform.processor()}
open(f"{a.project}/{a.name}/train_info.json", "w").write(json.dumps(info, indent=1))
print("TRAINING_DONE", json.dumps(info))
