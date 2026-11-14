# Copyright (c) 2026 Sankalp Gaonkar
"""CPU latency of several detectors under identical conditions (same process, same image, 4 threads).
Usage: python training/bench_latency.py image.jpg model1.pt model2.pt ...
"""
import json, platform, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from eval_detectors import latency
from ultralytics import YOLO
img = sys.argv[1]
out = {"image": img, "machine": platform.platform(), "models": {}}
for rep in range(2):            # two rounds, alternating, to even out background load
    for mp in sys.argv[2:]:
        r = latency(YOLO(mp), img, n=60)
        out["models"].setdefault(mp.rsplit("/", 1)[-1], []).append(r)
print(json.dumps(out, indent=1))
