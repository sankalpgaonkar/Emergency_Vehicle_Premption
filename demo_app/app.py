# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""EVP Demo server.

Run:   python demo_app/app.py            (then open http://127.0.0.1:5050)
       python demo_app/app.py --port 8000 --host 0.0.0.0
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory, abort, Response

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import config as C            # noqa: E402
from core import pipeline as P          # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = C.MAX_UPLOAD_MB * 1024 * 1024


def err(msg, code):
    return jsonify({"ok": False, "error": msg}), code


@app.errorhandler(413)
def too_big(_e):
    return err(f"File too large (limit {C.MAX_UPLOAD_MB} MB).", 413)


@app.route("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.route("/api/health")
def health():
    from core.detector import find_coco_weights
    from core.video_io import ffmpeg_exe
    k = C.default_model_key()
    return jsonify({"ok": True, "ev_model": str(C.EV_MODELS[k]["path"].relative_to(C.REPO_ROOT)), "ev_model_key": k,
                    "models": {key: {"label": m["label"], "present": m["path"].exists(), "file": m["path"].name,
                                     "hint": m.get("hint", "")}
                               for key, m in C.EV_MODELS.items()},
                    "ev_model_present": C.EV_MODELS[k]["path"].exists(), "coco_model": Path(find_coco_weights()).name,
                    "ffmpeg": bool(ffmpeg_exe()), "jobs": len(P.JOBS)})


@app.route("/api/config")
def config():
    return jsonify({"approaches": C.APPROACHES, "allowed_ext": sorted(C.ALLOWED_EXT),
                    "max_upload_mb": C.MAX_UPLOAD_MB, "max_seconds": C.MAX_PROCESS_SECONDS,
                    **C.to_dict(C.DetectionParams(), C.ConfirmParams(), C.SignalParams(), C.SimParams())})


@app.route("/api/samples")
def samples():
    out = []
    meta = {}
    mf = C.SAMPLES_DIR / "samples.json"
    if mf.exists():
        meta = {m["file"]: m for m in json.loads(mf.read_text())}
    order = list(meta)          # samples.json order first, then any other video files by name
    files = sorted(C.SAMPLES_DIR.glob("*"), key=lambda q: (order.index(q.name) if q.name in order else len(order), q.name))
    for p in files:
        if p.suffix.lower() in C.ALLOWED_EXT:
            m = meta.get(p.name, {})
            out.append({"file": p.name, "title": m.get("title", p.stem), "note": m.get("note", ""),
                        "licence": m.get("licence", ""), "credit": m.get("credit", ""), "url": m.get("url", "")})
    return jsonify(out)


def _settings_from(form_or_json):
    s = {"sim": {}, "signal": {}}
    g = form_or_json.get
    if g("approach") in C.APPROACHES:
        s["sim"]["video_approach"] = g("approach")
    if g("model") in C.EV_MODELS:
        s["model"] = g("model")
    if g("initial_state"):
        s["signal"]["initial_state"] = g("initial_state")
    dens = g("densities")
    if isinstance(dens, str) and dens:
        try:
            dens = json.loads(dens)
        except ValueError:
            dens = None
    if isinstance(dens, dict):
        s["sim"]["densities"] = {k: (None if v in (None, "", "auto") else max(0.0, min(60.0, float(v))))
                                 for k, v in dens.items() if k in C.APPROACHES}
    return s


@app.route("/api/upload", methods=["POST"])
def upload():
    f = request.files.get("video")
    if f is None or not f.filename:
        return err("No file received. Choose a video file to upload.", 400)
    ext = Path(f.filename).suffix.lower()
    if ext not in C.ALLOWED_EXT:
        return err(f"Unsupported format '{ext or 'none'}'. Use one of: " + ", ".join(sorted(C.ALLOWED_EXT)), 415)
    up = C.DATA_DIR / "uploads"
    up.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in Path(f.filename).name)[-80:]
    dst = up / f"{int(time.time() * 1000)}_{safe}"
    f.save(dst)
    if dst.stat().st_size < 1024:
        dst.unlink(missing_ok=True)
        return err("The file is empty or too small to be a video.", 422)
    job = P.new_job(dst, Path(f.filename).name, _settings_from(request.form))
    return jsonify({"ok": True, "job": P.public(job)})


@app.route("/api/samples/<name>/run", methods=["POST"])
def run_sample(name):
    p = (C.SAMPLES_DIR / name).resolve()
    if p.parent != C.SAMPLES_DIR.resolve() or not p.exists():
        return err("Sample not found.", 404)
    job = P.new_job(p, name, _settings_from(request.get_json(silent=True) or {}))
    return jsonify({"ok": True, "job": P.public(job)})


def _job(jid):
    j = P.JOBS.get(jid)
    if not j:
        abort(404)
    return j


@app.route("/api/jobs/<jid>")
def job_status(jid):
    return jsonify(P.public(_job(jid)))


@app.route("/api/jobs/<jid>/preview.jpg")
def job_preview(jid):
    p = Path(_job(jid)["dir"]) / "preview.jpg"
    if not p.exists():
        abort(404)
    r = send_file(p, mimetype="image/jpeg")
    r.headers["Cache-Control"] = "no-store"
    return r


@app.route("/api/jobs/<jid>/video")
def job_video(jid):
    p = Path(_job(jid)["dir"]) / "video.mp4"
    if not p.exists():
        abort(404)
    return send_file(p, mimetype="video/mp4", conditional=True)


@app.route("/api/jobs/<jid>/result")
def job_result(jid):
    j = _job(jid)
    p = Path(j["dir"]) / "result.json"
    if j["status"] != "done" or not p.exists():
        return err("Result not ready.", 409)
    return Response(p.read_text(), mimetype="application/json")


@app.route("/api/jobs/<jid>/simulate", methods=["POST"])
def job_simulate(jid):
    j = _job(jid)
    if j["status"] != "done":
        return err("Result not ready.", 409)
    body = request.get_json(silent=True) or {}
    s = _settings_from(body)
    inj = body.get("inject") or []
    s["sim"]["inject"] = [{"approach": i.get("approach"), "t": float(i.get("t", 0)), "cls": i.get("cls", "ambulance")}
                          for i in inj if i.get("approach") in C.APPROACHES][:6]
    confirm = body.get("confirm")
    if confirm:
        confirm = {k: (int(v) if k == "confirm_frames" else float(v)) for k, v in confirm.items()
                   if k in ("suspect_conf", "confirm_conf", "confirm_frames")}
    try:
        res = P.resimulate(j, s, confirm)
    except Exception as e:      # noqa: BLE001
        return err(f"Simulation failed: {e}", 500)
    return jsonify(res)


@app.route("/api/jobs/<jid>/report.csv")
def job_csv(jid):
    j = _job(jid)
    p = Path(j["dir"]) / "result.json"
    if not p.exists():
        abort(404)
    res = json.loads(p.read_text())
    rows = ["section,key,value"]
    a = res["analysis"]
    for k, v in a["counts"].items():
        rows.append(f"detected_unique,{k},{v}")
    for k, v in (a.get("perf") or {}).items():
        rows.append(f"measured_perf,{k},{json.dumps(v).replace(',', ';')}")
    for e in a["ev_tracks"]:
        rows.append(f"ev_track,{e['tid']},{e['cls']} first={e['first_t']} confirmed={e['confirmed_t']} max_conf={e['max_conf']}")
    for c in res["sim"]["comparison"]:
        for k, v in c.items():
            rows.append(f"SIMULATED_{c['ev_id']},{k},{v}")
    for mode in ("preemption", "fixed"):
        m = res["sim"][mode]["metrics"]
        rows.append(f"SIMULATED_{mode},mean_delay_s,{m['mean_delay_s']}")
        rows.append(f"SIMULATED_{mode},vehicles_completed,{m['vehicles_completed']}")
        for e in res["sim"][mode]["events"]:
            rows.append(f"SIMULATED_{mode}_event,{e['t']},{e['text'].replace(',', ';')}")
    return Response("\n".join(rows) + "\n", mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=evp_{jid}.csv"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050)))
    a = ap.parse_args()
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    P.load_existing()
    print(f"EVP demo running at http://{a.host}:{a.port}  (Ctrl+C to stop)")
    app.run(host=a.host, port=a.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
