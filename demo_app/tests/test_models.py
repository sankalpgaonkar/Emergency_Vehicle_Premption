# Copyright (c) 2026 Sankalp Gaonkar
# Part of the demo (demo_app/). Tests for the selectable detector models (v3 added 3 Nov 2026).
"""v3 is registered, selectable and NOT the default; it loads and runs one real inference."""
import cv2
import pytest

import app as server
from core import config as C


@pytest.fixture()
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_v3_registered_but_v2_stays_default():
    assert "v3" in C.EV_MODELS and C.EV_MODELS["v3"]["path"].exists()
    assert C.EV_MODELS["v3"]["path"].name == "ev_detector_v3_sankalp.pt"
    assert C.EV_MODELS["v3"]["label"].startswith("v3")
    assert C.default_model_key() == "v2"
    for k in ("v2", "v2alt", "v1"):            # the earlier options are still selectable
        assert C.EV_MODELS[k]["path"].exists(), k


def test_health_lists_v3_with_hint(client):
    h = client.get("/api/health").get_json()
    assert h["ev_model_key"] == "v2"
    m = h["models"]["v3"]
    assert m["present"] and m["file"] == "ev_detector_v3_sankalp.pt" and m["hint"]


def test_v3_loads_and_detects_fire_truck_frame():
    from core.config import DetectionParams
    from core.detector import Detector
    det = Detector(DetectionParams(), model_key="v3")
    assert det.model_key == "v3"
    assert sorted(det.ev_names.values()) == sorted(C.EV_CLASSES)
    cap = cv2.VideoCapture(str(C.SAMPLES_DIR / "toronto_fire_truck.mp4"))
    cap.set(cv2.CAP_PROP_POS_MSEC, 3000)        # the fire truck is in view at 3 s
    ok, frame = cap.read()
    cap.release()
    assert ok
    _vehicles, ev = det.run(frame)
    assert any(e[5] == "fire brigade" and e[4] >= 0.5 for e in ev), ev
