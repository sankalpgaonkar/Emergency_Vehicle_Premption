# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Confidence-persistence rule: no preemption from a single confident frame."""
from core.config import ConfirmParams
from core.ev_confirm import confirm_tracks

BOX = [100, 100, 200, 180]


def frames(confs, dt=1 / 15):
    out = []
    for i, c in enumerate(confs):
        ev = [] if c is None else [BOX[:2] + [BOX[2] + i, BOX[3]] + [c, "ambulance"]]
        out.append({"t": round(i * dt, 3), "ev": ev})
    return out


def test_single_frame_never_confirms():
    tr, _ = confirm_tracks(frames([0.95] + [None] * 10), ConfirmParams())
    assert tr[0].confirmed_t is None and tr[0].suspected_t is not None


def test_five_consecutive_confirm_on_fifth():
    p = ConfirmParams(confirm_frames=5, confirm_conf=0.5)
    fr = frames([0.6, 0.6, 0.7, 0.8, 0.9, 0.9])
    tr, per = confirm_tracks(fr, p)
    assert tr[0].confirmed_t == fr[4]["t"]
    assert per[3][0]["state"] == "SUSPECTED" and per[4][0]["state"] == "CONFIRMED"


def test_dip_resets_streak():
    p = ConfirmParams(confirm_frames=5, confirm_conf=0.5)
    tr, _ = confirm_tracks(frames([0.6, 0.6, 0.6, 0.6, 0.4, 0.6, 0.6, 0.6, 0.6]), p)
    assert tr[0].confirmed_t is None


def test_low_confidence_stays_candidate():
    tr, _ = confirm_tracks(frames([0.25] * 20), ConfirmParams())
    assert tr[0].state == "CANDIDATE"


def test_class_vote_uses_confidence_weights():
    fr = frames([0.6] * 6)
    fr[0]["ev"][0][5] = "police"
    tr, _ = confirm_tracks(fr, ConfirmParams())
    assert tr[0].cls == "ambulance"


def test_two_separate_vehicles_two_tracks():
    fr = []
    for i in range(8):
        fr.append({"t": i / 15, "ev": [[10, 10, 60, 50, 0.8, "ambulance"], [500, 300, 600, 380, 0.8, "fire brigade"]]})
    tr, _ = confirm_tracks(fr, ConfirmParams())
    assert len(tr) == 2 and all(t.confirmed_t is not None for t in tr)


def test_nested_box_is_one_vehicle():
    fr = [{"t": i / 15, "ev": [[100, 100, 300, 260, 0.8, "ambulance"], [150, 120, 290, 250, 0.7, "ambulance"]]}
          for i in range(8)]
    tr, _ = confirm_tracks(fr, ConfirmParams())
    assert len(tr) == 1
