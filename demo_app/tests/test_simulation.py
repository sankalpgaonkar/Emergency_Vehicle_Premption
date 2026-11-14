# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Simulation sanity checks (deterministic, no model needed)."""
from core.config import SimParams, SignalParams, ConfirmParams
from core.simulation import build_arrivals, simulate


def scenario(**kw):
    sp = SimParams(**kw)
    det = [{"t": 0.0, "cls": "car", "initial": True} for _ in range(6)]
    det += [{"t": 0.7 * i, "cls": "car"} for i in range(10)]
    det.append({"t": 1.0, "cls": "ambulance", "is_ev": True, "ev_id": "V1"})
    arr = build_arrivals(det, sp, 8.0, 12.0, {"car": 1.0}, 90)
    return sp, arr


def test_preemption_reduces_ev_delay():
    sp, arr = scenario()
    pre = simulate(arr, {"V1": (1.5, 0.8)}, sp, SignalParams(), ConfirmParams().priority, True, 90)
    fix = simulate(arr, {"V1": (1.5, 0.8)}, sp, SignalParams(), ConfirmParams().priority, False, 90)
    assert pre["ev"][0]["delay_s"] < fix["ev"][0]["delay_s"]
    assert pre["ev"][0]["response_s"] is not None and fix["ev"][0]["response_s"] is None


def test_deterministic():
    sp, arr = scenario()
    a = simulate(arr, {"V1": (1.5, 0.8)}, sp, SignalParams(), ConfirmParams().priority, True, 60)
    b = simulate(arr, {"V1": (1.5, 0.8)}, sp, SignalParams(), ConfirmParams().priority, True, 60)
    assert a["ev"] == b["ev"] and a["metrics"] == b["metrics"]


def test_no_vehicle_overlaps_in_lane():
    sp, arr = scenario()
    r = simulate(arr, {"V1": (1.5, 0.8)}, sp, SignalParams(), ConfirmParams().priority, False, 60)
    lens = {"car": 4.5, "ambulance": 6.0}
    # check every 1 s that ordinary vehicles in the same lane keep a positive gap
    for k in range(0, 600, 10):
        t = k * sp.dt
        pos = {}
        for v in r["trajectories"]:
            i = round((t - v["t0"]) / sp.dt)
            if 0 <= i < len(v["s"]) and not v["ev"]:
                pos.setdefault((v["a"], v["lane"]), []).append((v["s"][i], lens.get(v["type"], 4.5)))
        for lst in pos.values():
            lst.sort(reverse=True)
            for (s1, l1), (s2, l2) in zip(lst, lst[1:]):
                assert s1 - l1 - s2 > -0.3, f"overlap at t={t}"


def test_vehicles_stop_at_red():
    sp, arr = scenario()
    r = simulate(arr, {}, sp, SignalParams(), ConfirmParams().priority, False, 20)  # N red for the first 25 s
    for v in r["trajectories"]:
        if v["a"] == "N" and not v["ev"] and v["t0"] < 1:
            assert max(v["s"]) <= sp.approach_length_m + 0.5
