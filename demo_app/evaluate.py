# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Batch evaluation for the paper: runs the same pipeline as the web app, without the browser.

Measured (from the video):   unique vehicle counts, EV tracks, confirmation time, inference latency.
Simulated (from the model):  EV delay with preemption vs fixed-time, response time, other traffic delay.

Examples
  python demo_app/evaluate.py                                  # all bundled samples, default model
  python demo_app/evaluate.py --model v1 --model v2            # compare detectors
  python demo_app/evaluate.py --videos my_clip.mp4 --approach E
Outputs go to demo_app/results/ (JSON with everything + CSV/Markdown tables).
"""
import argparse
import csv
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import config as C            # noqa: E402
from core import pipeline as P          # noqa: E402


def run_one(video, model, approach, out_dir):
    d = out_dir / "jobs" / f"{Path(video).stem}_{model}"
    d.mkdir(parents=True, exist_ok=True)
    job = {"id": d.name, "name": Path(video).name, "dir": str(d), "src": str(video), "notes": [],
           "settings": {"model": model, "sim": {"video_approach": approach}}}
    t0 = time.time()
    P.process_video(job)
    res = json.loads((d / "result.json").read_text())
    res["wall_seconds"] = round(time.time() - t0, 2)
    return res, d


def sweep_confirmation(d, analysis, frames_list=(1, 3, 5, 8)):
    frames = json.loads((d / "frames.json").read_text())
    out = []
    for n in frames_list:
        cp = C.ConfirmParams(confirm_frames=n)
        a = P.analyse(frames, analysis["duration"], analysis["frame_w"], analysis["frame_h"], cp)
        out.append({"confirm_frames": n, "confirmed": len(a["ev_confirmed"]), "suspected_only": len(a["ev_suspected"]),
                    "first_confirm_t": min((e["confirmed_t"] for e in a["ev_confirmed"]), default=None),
                    "classes": [e["cls"] for e in a["ev_confirmed"]]})
    return out


PHASES = tuple(range(0, 50, 5))   # cycle offsets in s; the default fixed cycle is 50 s long (20+3+2+20+3+2)


def sweep_sim(analysis, approach, seeds=(1, 2, 3)):
    """Arrival-phase sweep: the same detected traffic is simulated with the fixed cycle started at 10 different
    points (every 5 s of the 50 s cycle), so the EV meets every part of the cycle. Seeds only change the random
    arrivals on the other three approaches."""
    rows = []
    for off in PHASES:
        for seed in seeds:
            s = P.run_sims(analysis, {"sim": {"video_approach": approach, "seed": seed},
                                      "signal": {"initial_state": "NS", "cycle_offset_s": off}})
            for c in s["comparison"]:
                rows.append({"cycle_offset_s": off, "seed": seed, **c,
                             "others_delay_preempt": s["preemption"]["metrics"]["mean_delay_s"],
                             "others_delay_fixed": s["fixed"]["metrics"]["mean_delay_s"]})
    return rows


def summarise_sweep(sw):
    out = []
    for evid in sorted({x["ev_id"] for x in sw}):
        xs = [x for x in sw if x["ev_id"] == evid]
        g = lambda k: [x[k] for x in xs if x.get(k) is not None]
        dp, df, rs, op, of = g("delay_preempt_s"), g("delay_fixed_s"), g("response_s"), g("others_delay_preempt"), g("others_delay_fixed")
        sp = sum(1 for x in xs if (x.get("stopped_preempt_s") or 0) > 0.5)
        sf = sum(1 for x in xs if (x.get("stopped_fixed_s") or 0) > 0.5)
        st = lambda v: {"mean": round(statistics.mean(v), 2), "median": round(statistics.median(v), 2),
                        "min": round(min(v), 2), "max": round(max(v), 2), "n": len(v)} if v else None
        out.append({"ev_id": evid, "cls": xs[0]["cls"], "runs": len(xs), "ev_delay_preempt": st(dp), "ev_delay_fixed": st(df),
                    "response": st(rs), "others_delay_preempt": st(op), "others_delay_fixed": st(of),
                    "ev_stopped_runs_preempt": sp, "ev_stopped_runs_fixed": sf})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", nargs="*")
    ap.add_argument("--model", action="append")
    ap.add_argument("--approach", default="N")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    a = ap.parse_args()
    vids = a.videos or [str(p) for p in sorted(C.SAMPLES_DIR.glob("*.mp4"))]
    models = a.model or [C.default_model_key()]
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "params": C.to_dict(C.DetectionParams(), C.ConfirmParams(),
                                                                                  C.SignalParams(), C.SimParams()),
              "runs": []}
    for m in models:
        for v in vids:
            print(f"[{m}] {Path(v).name} ...", flush=True)
            res, d = run_one(v, m, a.approach, out_dir)
            an = res["analysis"]
            run = {"video": Path(v).name, "model": m, "model_file": an["perf"]["ev_model_file"],
                   "measured": {"duration_s": an["duration"], "counts": an["counts"],
                                "ordinary_vehicles": an["ordinary_count"],
                                "ev_tracks": [{k: e[k] for k in ("cls", "final_cls", "first_t", "suspected_t", "confirmed_t",
                                                                  "confirmed_conf", "max_conf", "hits")}
                                              for e in an["ev_tracks"]],
                                "perf": an["perf"], "confirmation_sweep": sweep_confirmation(d, an)},
                   "simulated": {"default": res["sim"]["comparison"],
                                 "others_delay_preempt": res["sim"]["preemption"]["metrics"]["mean_delay_s"],
                                 "others_delay_fixed": res["sim"]["fixed"]["metrics"]["mean_delay_s"],
                                 "sweep": sweep_sim(an, a.approach)}}
            run["simulated"]["sweep_summary"] = summarise_sweep(run["simulated"]["sweep"])
            report["runs"].append(run)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out_dir / f"eval_{stamp}.json").write_text(json.dumps(report, indent=1))
    # tables
    with open(out_dir / f"eval_{stamp}_measured.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "video", "duration_s", "ordinary_vehicles", "confirmed_EVs", "first_confirm_t", "confirmed_classes",
                    "suspected_only", "analysed_fps", "ev_ms_median", "coco_ms_median"])
        for r in report["runs"]:
            me = r["measured"]
            conf = [e for e in me["ev_tracks"] if e["confirmed_t"] is not None]
            sus = [e for e in me["ev_tracks"] if e["confirmed_t"] is None and e["suspected_t"] is not None]
            w.writerow([r["model"], r["video"], me["duration_s"], me["ordinary_vehicles"], len(conf),
                        min((e["confirmed_t"] for e in conf), default=""), "/".join(e["cls"] for e in conf), len(sus),
                        me["perf"]["analysed_fps"], me["perf"]["ev_ms_median"], me["perf"]["coco_ms_median"]])
    lines = ["| model | video | EV | runs | response s (median, max) | EV delay preempt s: median [min–max] | EV delay fixed s: median [min–max] | EV stopped (preempt / fixed) | other traffic delay s, mean (preempt / fixed) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in report["runs"]:
        summ = r["simulated"]["sweep_summary"]
        if not summ:
            lines.append(f"| {r['model']} | {r['video']} | none confirmed | – | – | – | – | – | – |")
            continue
        for s in summ:
            f3 = lambda d: f"{d['median']:.1f} [{d['min']:.1f}–{d['max']:.1f}]" if d else "–"
            rs = s["response"]
            lines.append(f"| {r['model']} | {r['video']} | {s['cls']} | {s['runs']} | "
                         f"{(str(rs['median']) + ', ' + str(rs['max'])) if rs else '–'} | {f3(s['ev_delay_preempt'])} | {f3(s['ev_delay_fixed'])} | "
                         f"{s['ev_stopped_runs_preempt']}/{s['runs']} vs {s['ev_stopped_runs_fixed']}/{s['runs']} | "
                         f"{s['others_delay_preempt']['mean']:.1f} / {s['others_delay_fixed']['mean']:.1f} |")
    (out_dir / f"eval_{stamp}_simulated.md").write_text(
        "SIMULATED results: arrival-phase sweep, fixed cycle started at 0, 5, ..., 45 s (10 phases) x 3 seeds = 30 runs per EV. "
        "Detected traffic from the video; not field measurements.\n\n" + "\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {out_dir}/eval_{stamp}.json (+ _measured.csv, _simulated.md)")


if __name__ == "__main__":
    main()
