# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Safety and behaviour checks for the signal controller (no video or model needed)."""
from core.config import SignalParams
from core.signal_controller import SignalController, AXIS, APPROACHES


def run(ctrl, t0, t1, dt=0.1, hist=None):
    t = t0
    while t < t1 - 1e-9:
        ctrl.step(t, dt)
        if hist is not None:
            hist.append((round(t, 2), ctrl.sig(), ctrl.mode))
        t += dt
    return t


def assert_safe(hist):
    """Never two crossing approaches green/yellow at once; every green ends in yellow."""
    prev = None
    for t, s, mode in hist:
        st = dict(zip(APPROACHES, s))
        moving = [a for a in APPROACHES if st[a] in "GY"]
        assert len({AXIS[a] for a in moving}) <= 1, f"conflict at t={t}: {s}"
        if prev:
            for a, (p, c) in zip(APPROACHES, zip(prev, s)):
                assert not (p == "G" and c == "R"), f"{a} went green->red without yellow at t={t}"
        prev = s


def test_fixed_cycle_is_safe_and_periodic():
    sp = SignalParams()
    c = SignalController(sp, preemption=False, video_approach="N")
    h = []
    run(c, 0, 200, hist=h)
    assert_safe(h)
    greens_n = [t for (t, s, m), (t2, s2, m2) in zip(h, h[1:]) if s[0] != "G" and s2[0] == "G"]
    assert len(greens_n) >= 3
    periods = [b - a for a, b in zip(greens_n, greens_n[1:])]
    cycle = sp.green_ns + sp.green_ew + 2 * (sp.yellow + sp.all_red)
    assert all(abs(p - cycle) < 0.25 for p in periods)


def test_preemption_from_red_goes_yellow_allred_green():
    sp = SignalParams()
    c = SignalController(sp, preemption=True, video_approach="N")  # starts with N red (EW green)
    h = []
    run(c, 0, 5, hist=h)
    assert c.state["N"] == "R" and c.state["E"] == "G"
    r = c.request(5.0, "EV1", "N", "ambulance", 1)
    run(c, 5.0, 20, hist=h)
    assert r["t_green"] is not None
    assert abs((r["t_green"] - 5.0) - (sp.yellow + sp.all_red)) < 0.3
    st = dict(zip(APPROACHES, h[-1][1]))
    assert st == {"N": "G", "E": "R", "S": "R", "W": "R"}      # exclusive green for the EV approach
    assert_safe(h)


def test_green_extension_when_already_green():
    sp = SignalParams(initial_state="video_green")
    c = SignalController(sp, preemption=True, video_approach="N")
    run(c, 0, 2)
    r = c.request(2.0, "EV1", "N", "ambulance", 1)
    c.step(2.0, 0.1)
    assert r["t_green"] == 2.0                       # response time 0: green simply held
    run(c, 2.0, 40)
    assert c.state["N"] == "G"                       # held beyond the normal 20 s green


def test_recovery_after_clear_returns_to_normal():
    sp = SignalParams()
    c = SignalController(sp, preemption=True, video_approach="N")
    h = []
    c.request(1.0, "EV1", "N", "ambulance", 1)
    run(c, 1.0, 15, hist=h)
    c.clear(15.0, "EV1")
    run(c, 15.0, 40, hist=h)
    assert c.mode == "NORMAL"
    kinds = [e["kind"] for e in c.events]
    assert kinds.index("preempt_green") < kinds.index("recovery") < kinds.index("normal")
    assert_safe(h)


def test_two_conflicting_evs_served_in_order():
    sp = SignalParams()
    c = SignalController(sp, preemption=True, video_approach="N")
    h = []
    r1 = c.request(1.0, "A", "N", "ambulance", 1)
    r2 = c.request(1.5, "B", "E", "fire brigade", 1)
    run(c, 1.0, 12, hist=h)
    assert r1["t_green"] is not None and r2["t_green"] is None
    c.clear(12.0, "A")
    run(c, 12.0, 30, hist=h)
    assert r2["t_green"] is not None and r2["t_green"] > r1["t_green"]
    assert_safe(h)


def test_priority_beats_arrival_order():
    sp = SignalParams()
    c = SignalController(sp, preemption=True, video_approach="N")
    c.request(1.0, "P", "E", "police", 2)
    c.request(1.1, "A", "N", "ambulance", 1)
    run(c, 1.0, 10)
    assert c.target == "N"


def test_max_green_timeout_releases():
    sp = SignalParams(preempt_max_green=10)
    c = SignalController(sp, preemption=True, video_approach="N")
    c.request(0.0, "A", "N", "ambulance", 1)
    run(c, 0.0, 40)                                   # EV never clears
    assert any(e["kind"] == "preempt_timeout" for e in c.events)


def test_fixed_mode_ignores_requests():
    c = SignalController(SignalParams(), preemption=False, video_approach="N")
    r = c.request(1.0, "A", "N", "ambulance", 1)
    run(c, 1.0, 10)
    assert r["t_green"] is None and c.mode == "NORMAL"


def test_cycle_offset_starts_mid_cycle_and_stays_safe():
    for off in range(0, 50, 5):
        sp = SignalParams(initial_state="NS", cycle_offset_s=off)
        c = SignalController(sp, preemption=True, video_approach="N")
        if off == 21:
            assert c.sig()[0] == "Y"
        h = []
        c.request(3.0, "EV1", "E", "ambulance", 1)
        run(c, 0, 80, hist=h)
        assert_safe(h)
    sp = SignalParams(initial_state="NS", cycle_offset_s=21)
    c = SignalController(sp, preemption=False, video_approach="N")
    assert c.sig() == "YRYR" or c.sig()[0] == "Y"
