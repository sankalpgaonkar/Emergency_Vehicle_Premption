# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""End-to-end job: uploaded video -> detections -> EV confirmation -> two simulations.

Everything a job produces is written to data/jobs/<job_id>/:
    video.mp4      browser-playable copy (the detector runs on this exact file)
    result.json    detections per analysed frame, EV tracks, counts, both simulations
    preview.jpg    latest annotated frame while processing
"""
import json
import math
import threading
import time
import traceback
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import cv2

from . import config as C
from .ev_confirm import confirm_tracks, track_summary, iou
from .simulation import build_arrivals, simulate
from .video_io import probe, transcode_for_browser, VideoError

JOBS = {}
_LOCK = threading.Lock()
_RUN_SLOT = threading.Semaphore(1)      # one video analysed at a time (CPU bound)


def new_job(src_path, original_name, settings=None):
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = C.DATA_DIR / "jobs" / jid
    d.mkdir(parents=True, exist_ok=True)
    job = {"id": jid, "name": original_name, "status": "queued", "stage": "Queued", "progress": 0.0,
           "dir": str(d), "src": str(src_path), "created": time.time(), "error": None, "settings": settings or {},
           "notes": []}
    with _LOCK:
        JOBS[jid] = job
    th = threading.Thread(target=_run, args=(job,), daemon=True)
    th.start()
    return job


def load_existing():
    """Re-register finished jobs after a server restart so their links keep working."""
    root = C.DATA_DIR / "jobs"
    if not root.exists():
        return 0
    n = 0
    for d in sorted(root.iterdir()):
        if (d / "result.json").exists() and d.name not in JOBS:
            meta = {}
            try:
                meta = json.loads((d / "job.json").read_text())
            except Exception:
                pass
            JOBS[d.name] = {"id": d.name, "name": meta.get("name", d.name), "status": "done", "stage": "Done",
                            "progress": 1.0, "dir": str(d), "src": meta.get("src", ""), "created": d.stat().st_mtime,
                            "error": None, "settings": meta.get("settings", {}), "notes": []}
            n += 1
    return n


def public(job):
    return {k: v for k, v in job.items() if k not in ("dir", "src")}


def _set(job, **kw):
    with _LOCK:
        job.update(kw)


def _run(job):
    with _RUN_SLOT:
        try:
            process_video(job)
        except VideoError as e:
            _set(job, status="error", error=str(e), stage="Could not process this video")
        except Exception as e:   # unexpected: keep the server alive, show the reason
            traceback.print_exc()
            _set(job, status="error", error=f"Processing failed: {type(e).__name__}: {e}", stage="Failed")


def _draw_preview(frame, veh, evs, t):
    img = frame.copy()
    for x1, y1, x2, y2, tid, cls, cf in veh:
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (90, 200, 120), 2)
    for b in evs:
        col = (60, 60, 240) if b[4] >= 0.5 else (0, 190, 255)
        cv2.rectangle(img, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), col, 3)
        cv2.putText(img, f"{b[5]} {b[4]:.2f}", (int(b[0]), max(14, int(b[1]) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    col, 2)
    cv2.putText(img, f"t={t:5.1f}s", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return img


def process_video(job):
    from .detector import Detector
    d = Path(job["dir"])
    dp = C.DetectionParams()
    _set(job, status="running", stage="Checking the file", progress=0.01)
    info0 = probe(job["src"])
    if info0["duration"] and info0["duration"] > C.MAX_PROCESS_SECONDS:
        job["notes"].append(f"Video is {info0['duration']:.0f}s long; the first {C.MAX_PROCESS_SECONDS}s are analysed.")
    _set(job, stage="Converting for the browser", progress=0.03, source_info=info0)
    vid = d / "video.mp4"
    transcode_for_browser(job["src"], vid, C.MAX_PROCESS_SECONDS, log_path=d / "ffmpeg.log")
    info = probe(vid)
    _set(job, stage="Loading models", progress=0.06, video_info=info)
    det = Detector(dp, (job.get("settings") or {}).get("model"))
    cap = cv2.VideoCapture(str(vid))
    fps = info["fps"]
    n_total = info["frames"] or int((info["duration"] or 60) * fps)
    step = 1.0 / dp.process_fps
    next_t = 0.0
    frames = []
    idx = 0
    t_start = time.perf_counter()
    last_prev = 0.0
    W, H = info["width"], info["height"]
    _set(job, stage="Detecting vehicles", progress=0.08)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        t = idx / fps if pos <= 0 and idx > 0 else (pos - 1.0 / fps if pos > 0 else 0.0)
        t = max(0.0, t)
        idx += 1
        if t + 1e-6 < next_t:
            continue
        next_t += step
        veh, evb = det.run(frame)
        frames.append({"t": round(t, 3), "veh": veh, "ev": evb})
        now = time.perf_counter()
        if now - last_prev > 0.6:
            last_prev = now
            cv2.imwrite(str(d / "preview.jpg"), _draw_preview(frame, veh, evb, t), [cv2.IMWRITE_JPEG_QUALITY, 70])
            elapsed = now - t_start
            _set(job, progress=0.08 + 0.82 * min(1.0, idx / max(1, n_total)),
                 stage=f"Detecting vehicles — frame {idx}/{n_total}",
                 live={"t": round(t, 2), "vehicles": len(veh),
                       "ev": max((b[4] for b in evb), default=0.0),
                       "fps": round(len(frames) / elapsed, 1) if elapsed > 0 else None})
    cap.release()
    proc_s = time.perf_counter() - t_start
    if not frames:
        raise VideoError("No frames could be read from the converted video.")
    duration = info["duration"] or frames[-1]["t"] + step
    perf = {"frames_analysed": len(frames), "processing_seconds": round(proc_s, 2),
            "analysed_fps": round(len(frames) / proc_s, 2) if proc_s > 0 else None,
            "coco_ms_median": _median(det.lat_coco), "ev_ms_median": _median(det.lat_ev),
            "coco_ms_p95": _pct(det.lat_coco, 95), "ev_ms_p95": _pct(det.lat_ev, 95),
            "video_seconds": duration, "frame_size": [W, H],
            "ev_model": det.model_key, "ev_model_file": det.model_path.name, "torch_threads": _threads()}
    _set(job, stage="Confirming emergency vehicles", progress=0.92)
    analysis = analyse(frames, duration, W, H)
    analysis["perf"] = perf
    analysis["video_info"] = info
    analysis["source_info"] = info0
    (d / "frames.json").write_text(json.dumps(frames))
    _set(job, stage="Running the intersection simulation", progress=0.95)
    sims = run_sims(analysis, job.get("settings") or {})
    result = {"job": job["id"], "name": job["name"], "analysis": analysis, "sim": sims,
              "notes": job["notes"] + analysis["notes"] + sims["notes"]}
    (d / "result.json").write_text(json.dumps(result))
    (d / "job.json").write_text(json.dumps({"name": job["name"], "settings": job.get("settings"), "src": job["src"]}))
    _set(job, status="done", stage="Done", progress=1.0)


def _threads():
    try:
        import torch
        return torch.get_num_threads()
    except Exception:
        return None


def _median(xs):
    return round(sorted(xs)[len(xs) // 2], 2) if xs else None


def _pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(math.ceil(p / 100 * len(s))) - 1)], 2)


def analyse(frames, duration, W, H, cp=None):
    """Turn raw per-frame detections into tracks, counts and EV candidates."""
    cp = cp or C.ConfirmParams()
    dp = C.DetectionParams()
    notes = []
    ev_tracks, ev_per_frame = confirm_tracks(frames, cp)
    # ordinary vehicle tracks from ByteTrack ids
    tr = defaultdict(lambda: {"hits": 0, "cls": Counter(), "first_t": None, "last_t": None, "boxes": []})
    for fi, fr in enumerate(frames):
        for x1, y1, x2, y2, tid, cls, cf in fr["veh"]:
            if tid < 0:
                continue
            r = tr[tid]
            r["hits"] += 1
            r["cls"][cls] += cf
            r["first_t"] = fr["t"] if r["first_t"] is None else r["first_t"]
            r["last_t"] = fr["t"]
            r["boxes"].append((fi, [x1, y1, x2, y2]))
    # link COCO tracks to EV tracks (same vehicle seen by both models)
    ev_box_by_frame = defaultdict(list)
    for fi, lst in enumerate(ev_per_frame):
        for e in lst:
            ev_box_by_frame[fi].append(e)
    linked = {}
    for tid, r in tr.items():
        votes = Counter()
        for fi, box in r["boxes"]:
            for e in ev_box_by_frame.get(fi, []):
                if iou(box, e["box"]) > 0.35:
                    votes[e["tid"]] += 1
        if votes:
            etid, nv = votes.most_common(1)[0]
            if nv >= max(2, 0.4 * r["hits"]):
                linked[tid] = etid
    t_first_frame = frames[0]["t"]
    vehicles = []
    for tid, r in sorted(tr.items(), key=lambda kv: kv[1]["first_t"]):
        if r["hits"] < dp.min_track_hits:
            continue
        cls = r["cls"].most_common(1)[0][0]
        vehicles.append({"tid": tid, "cls": cls, "first_t": r["first_t"], "last_t": r["last_t"], "hits": r["hits"],
                         "ev_link": linked.get(tid), "initial": r["first_t"] <= t_first_frame + 0.25})
    evs = [track_summary(t) for t in ev_tracks if t.hits >= 2]
    confirmed = [e for e in evs if e["confirmed_t"] is not None]
    suspected = [e for e in evs if e["confirmed_t"] is None and e["suspected_t"] is not None]
    # counts: ordinary vehicles that are not the same object as a confirmed/suspected EV
    ev_ids_shown = {e["tid"] for e in confirmed + suspected}
    ordinary = [v for v in vehicles if v["ev_link"] not in ev_ids_shown]
    counts = Counter(v["cls"] for v in ordinary)
    for e in confirmed:
        counts[e["cls"]] += 1
    per_frame = []
    counted = {v["tid"] for v in ordinary}
    boxes = []
    for fr in frames:
        boxes.append([[int(x1), int(y1), int(x2), int(y2), tid, cls, 1 if tid in counted else 0]
                      for x1, y1, x2, y2, tid, cls, cf in fr["veh"]])
    for fi, fr in enumerate(frames):
        c = Counter(v[5] for v in fr["veh"])
        best = max(ev_per_frame[fi], key=lambda e: e["conf"], default=None)
        per_frame.append({"t": fr["t"], "n": len(fr["veh"]), "c": dict(c),
                          "ev": best["conf"] if best else 0.0, "ev_cls": best["cls"] if best else None,
                          "ev_state": best["state"] if best else None,
                          "streak": max((e["streak"] for e in ev_per_frame[fi]), default=0)})
    if not frames or not any(fr["veh"] for fr in frames):
        notes.append("No ordinary vehicles were detected in the video; the video approach is filled only "
                     "by the density settings.")
    if not confirmed and not suspected:
        notes.append("No emergency vehicle was detected" + (" (only weak candidate boxes below the suspect threshold)" if evs else "")
                     + ", so no preemption is triggered (expected for normal traffic).")
    elif not confirmed:
        notes.append("An emergency vehicle was SUSPECTED but never met the confirmation rule "
                     f"({cp.confirm_frames} consecutive analysed frames ≥ {cp.confirm_conf:.2f}); "
                     "no preemption was triggered.")
    if len(confirmed) > 1:
        notes.append(f"{len(confirmed)} emergency vehicles confirmed; requests are served in order of priority, "
                     "then confirmation time.")
    obs_rate = len(ordinary) / duration * 60.0 if duration > 0 else 0.0
    mix = Counter(v["cls"] for v in ordinary)
    return {"duration": round(duration, 2), "frame_w": W, "frame_h": H,
            "vehicles": vehicles, "ordinary_count": len(ordinary), "counts": dict(counts),
            "ev_tracks": evs, "ev_confirmed": confirmed, "ev_suspected": suspected,
            "ev_per_frame": ev_per_frame, "per_frame": per_frame, "boxes": boxes,
            "observed_rate_vpm": round(obs_rate, 1), "class_mix": dict(mix) or {"car": 1},
            "confirm_params": asdict(cp), "notes": notes}


def run_sims(analysis, settings):
    sp = C.SimParams()
    sig = C.SignalParams()
    cp = C.ConfirmParams()
    for k, v in (settings.get("sim") or {}).items():
        if hasattr(sp, k):
            setattr(sp, k, v)
    for k, v in (settings.get("signal") or {}).items():
        if hasattr(sig, k):
            setattr(sig, k, v)
    notes = []
    duration_v = analysis["duration"]
    rate = analysis["observed_rate_vpm"]
    cap = 30.0
    rate_used = min(rate, cap)
    if rate > cap:
        notes.append(f"Observed flow ({rate:.0f} veh/min, short clip) is capped at {cap:.0f} veh/min "
                     "for the extrapolated and mirrored arrivals so the simulated junction stays below saturation.")
    detected = []
    for v in analysis["vehicles"]:
        is_ev_link = v["ev_link"] in {e["tid"] for e in analysis["ev_confirmed"] + analysis["ev_suspected"]}
        if is_ev_link:
            continue
        detected.append({"t": v["first_t"], "cls": v["cls"], "initial": v["initial"]})
    ev_confirm = {}
    for e in analysis["ev_confirmed"]:
        eid = f"V{e['tid']}"
        detected.append({"t": e["first_t"], "cls": e["cls"], "is_ev": True, "ev_id": eid, "conf": e["confirmed_conf"],
                         "initial": False})
        ev_confirm[eid] = (e["confirmed_t"], e["confirmed_conf"])
    for e in analysis["ev_suspected"]:
        detected.append({"t": e["first_t"], "cls": "car", "suspected": True, "initial": False})
    last_ev = max([e["confirmed_t"] for e in analysis["ev_confirmed"]] +
                  [float(i.get("t", 0)) for i in (sp.inject or [])] + [0.0])
    duration = max(sp.min_duration_s, duration_v + 25.0, (last_ev + 70.0) if last_ev else 0.0)
    duration = min(duration, sp.max_duration_s)
    if analysis["ev_confirmed"] or sp.inject:
        pass
    arrivals = build_arrivals(detected, sp, duration_v, rate_used, analysis["class_mix"], duration)
    pre = simulate(arrivals, ev_confirm, sp, sig, cp.priority, preemption=True, duration=duration)
    fix = simulate(arrivals, ev_confirm, sp, sig, cp.priority, preemption=False, duration=duration)
    comp = []
    for a, b in zip(pre["ev"], fix["ev"]):
        comp.append({"ev_id": a["ev_id"], "cls": a["cls"], "approach": a["approach"],
                     "delay_preempt_s": a["delay_s"], "delay_fixed_s": b["delay_s"],
                     "travel_preempt_s": a["travel_s"], "travel_fixed_s": b["travel_s"],
                     "stopped_preempt_s": a["stopped_s"], "stopped_fixed_s": b["stopped_s"],
                     "response_s": a["response_s"], "cleared_fixed": b["t_cleared"] is not None})
    src_counts = Counter(x["source"] for x in arrivals)
    return {"duration": duration, "params": {"sim": asdict(sp), "signal": asdict(sig)},
            "observed_rate_vpm": rate, "rate_used_vpm": rate_used,
            "arrival_sources": dict(src_counts),
            "preemption": pre, "fixed": fix, "comparison": comp,
            "notes": notes}


def resimulate(job, settings, confirm=None):
    """Re-run confirmation (optional new thresholds) + both simulations from stored detections."""
    d = Path(job["dir"])
    res = json.loads((d / "result.json").read_text())
    if confirm:
        frames = json.loads((d / "frames.json").read_text())
        cp = C.ConfirmParams(**{**asdict(C.ConfirmParams()), **confirm})
        a_old = res["analysis"]
        a_new = analyse(frames, a_old["duration"], a_old["frame_w"], a_old["frame_h"], cp)
        for k in ("perf", "video_info", "source_info"):
            a_new[k] = a_old.get(k)
        res["analysis"] = a_new
    res["sim"] = run_sims(res["analysis"], settings)
    res["notes"] = res["analysis"]["notes"] + res["sim"]["notes"]
    return res
