# Copyright (c) 2026 Sankalp Gaonkar
"""Compare emergency-vehicle detectors on the SAME data.

1. Near-duplicate-filtered test split made by make_clean_split.py      (box-level mAP, per class)
2. Original Roboflow test split (has near-duplicates of train) (box-level mAP, for reference only)
3. External photos from Wikimedia Commons, unseen by both models (image-level: was the right class found?)
4. CPU latency, one 640-px image, batch 1

Usage:
  python training/eval_detectors.py --models project/models/yolo_emergency_detector.pt project/models/ev_detector_v2_sankalp.pt \
      --clean datasets_clean/data.yaml --external external_test --out training/eval
NOTE: a model trained on the original split has seen some of the clean-split test images during training, so its
number on (1) is optimistic; (3) is the fair comparison for that model.
"""
import argparse, json, statistics, time
from pathlib import Path
import torch
from ultralytics import YOLO

NAMES = ["ambulance", "fire brigade", "police"]


def box_eval(model, data, split, out, tag):
    m = model.val(data=data, split=split, imgsz=640, batch=16, device="cpu", plots=False, verbose=False,
                  project=str(out), name=tag, exist_ok=True)
    per = {}
    for i, c in enumerate(m.box.ap_class_index.tolist()):
        p, r, ap50, ap = m.box.class_result(i)
        per[NAMES[c]] = {"precision": round(float(p), 3), "recall": round(float(r), 3),
                         "mAP50": round(float(ap50), 3), "mAP50_95": round(float(ap), 3)}
    return {"mAP50": round(float(m.box.map50), 3), "mAP50_95": round(float(m.box.map), 3),
            "precision": round(float(m.box.mp), 3), "recall": round(float(m.box.mr), 3), "per_class": per,
            "images": int(m.seen) if hasattr(m, "seen") else None}


def external_eval(model, root, manifest):
    items = json.loads(Path(manifest).read_text())
    res = {}
    for thr in (0.25, 0.5):
        stats = {"ambulance": [0, 0], "fire brigade": [0, 0], "any_ev_on_positives": [0, 0], "false_alarm_on_negatives": [0, 0],
                 "misclass_on_positives": [0, 0]}
        for it in items:
            r = model.predict(str(Path(root) / it["file"]), conf=thr, imgsz=640, verbose=False, device="cpu", agnostic_nms=True)[0]
            found = {model.names[int(c)] for c in r.boxes.cls.tolist()} if r.boxes is not None else set()
            lab = it["label"]
            if lab == "none":
                stats["false_alarm_on_negatives"][0] += bool(found); stats["false_alarm_on_negatives"][1] += 1
            else:
                stats[lab][0] += lab in found; stats[lab][1] += 1
                stats["any_ev_on_positives"][0] += bool(found); stats["any_ev_on_positives"][1] += 1
                stats["misclass_on_positives"][0] += bool(found) and lab not in found; stats["misclass_on_positives"][1] += 1
        res[f"conf>={thr}"] = {k: {"hits": a, "of": b, "rate": round(a / b, 3) if b else None} for k, (a, b) in stats.items()}
    return res


def latency(model, img, n=60):
    torch.set_num_threads(4)
    for _ in range(5):
        model.predict(img, imgsz=640, verbose=False, device="cpu")
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); model.predict(img, imgsz=640, verbose=False, device="cpu"); ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return {"median_ms": round(statistics.median(ts), 2), "p95_ms": round(ts[int(0.95 * len(ts)) - 1], 2), "threads": 4}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--clean", required=True)
    ap.add_argument("--orig", default=None, help="data.yaml for the original split (absolute paths)")
    ap.add_argument("--external", default=None)
    ap.add_argument("--manifest", default=str(Path(__file__).parent / "external_test_manifest.json"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "eval"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    report = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "models": {}}
    for mp in a.models:
        model = YOLO(mp); tag = Path(mp).stem
        print("==", tag, flush=True)
        r = {"clean_test": box_eval(model, a.clean, "test", out, tag + "_clean_test"),
             "clean_val": box_eval(model, a.clean, "val", out, tag + "_clean_val")}
        if a.orig:
            r["original_test"] = box_eval(model, a.orig, "test", out, tag + "_orig_test")
        if a.external:
            r["external"] = external_eval(model, a.external, a.manifest)
            first = json.loads(Path(a.manifest).read_text())[0]["file"]
            r["latency"] = latency(model, str(Path(a.external) / first))
        report["models"][tag] = r
        print(json.dumps(r, indent=1), flush=True)
    (out / "detector_comparison.json").write_text(json.dumps(report, indent=1))
    print("wrote", out / "detector_comparison.json")


if __name__ == "__main__":
    main()
