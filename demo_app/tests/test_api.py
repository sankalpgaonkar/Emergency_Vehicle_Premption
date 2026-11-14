# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""API tests through Flask's test client. The sample-video test runs the real models."""
import io
import time

import pytest

import app as server
from core import pipeline as P


@pytest.fixture()
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def wait(client, jid, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{jid}").get_json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.5)
    raise AssertionError("job timed out")


def test_health(client):
    h = client.get("/api/health").get_json()
    assert h["ok"] and h["ev_model_present"]


def test_unsupported_format(client):
    r = client.post("/api/upload", data={"video": (io.BytesIO(b"x" * 5000), "notes.txt")},
                    content_type="multipart/form-data")
    assert r.status_code == 415 and "Unsupported" in r.get_json()["error"]


def test_empty_file(client):
    r = client.post("/api/upload", data={"video": (io.BytesIO(b"abc"), "clip.mp4")}, content_type="multipart/form-data")
    assert r.status_code == 422


def test_corrupted_video_reports_error(client):
    junk = bytes((i * 37) % 256 for i in range(200000))
    r = client.post("/api/upload", data={"video": (io.BytesIO(junk), "broken.mp4")}, content_type="multipart/form-data")
    assert r.status_code == 200
    j = wait(client, r.get_json()["job"]["id"])
    assert j["status"] == "error" and ("corrupt" in j["error"].lower() or "decod" in j["error"].lower())


def test_placeholder_video_no_detections(client):
    r = client.post("/api/samples/zz_original_placeholder_emergency2.mp4/run", json={"approach": "N"})
    j = wait(client, r.get_json()["job"]["id"])
    assert j["status"] == "done"
    res = client.get(f"/api/jobs/{j['id']}/result").get_json()
    assert res["analysis"]["ordinary_count"] == 0 and not res["analysis"]["ev_confirmed"]
    assert res["sim"]["comparison"] == []
    # the synthetic clip draws a box labelled "AMBULANCE"; a detector may SUSPECT it, but must not confirm it
    assert any("no preemption" in n for n in res["notes"])


def test_real_clip_end_to_end(client):
    r = client.post("/api/samples/tokyo_ambulance_intersection.mp4/run", json={"approach": "E"})
    j = wait(client, r.get_json()["job"]["id"])
    assert j["status"] == "done", j.get("error")
    res = client.get(f"/api/jobs/{j['id']}/result").get_json()
    a = res["analysis"]
    assert a["ordinary_count"] > 0
    assert a["ev_confirmed"], "the ambulance in this clip should be confirmed"
    assert len(a["ev_confirmed"]) == 1, [e["tid"] for e in a["ev_confirmed"]]
    c = res["sim"]["comparison"][0]
    assert c["approach"] == "E" and c["response_s"] is not None
    pre = res["sim"]["preemption"]
    t_conf = a["ev_confirmed"][0]["confirmed_t"]
    req = [e for e in pre["events"] if e["kind"] == "ev_request"][0]
    assert abs(req["t"] - t_conf) <= 0.11          # preemption request at the confirmation time
    # re-simulate with an injected conflicting EV
    r2 = client.post(f"/api/jobs/{j['id']}/simulate", json={"approach": "E", "inject": [{"approach": "N", "t": 2.0}]})
    res2 = r2.get_json()
    n_video = len(res["sim"]["comparison"])
    assert len(res2["sim"]["comparison"]) == n_video + 1
    assert any(c["approach"] == "N" for c in res2["sim"]["comparison"])
