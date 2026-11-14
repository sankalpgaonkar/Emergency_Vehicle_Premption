# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Emergency-vehicle confirmation ("confidence persistence").

The detector gives a box and a confidence per frame. A single frame is not
enough to change a traffic signal, so each EV box is tracked over frames and
moves through three states:

    (raw box) -> SUSPECTED  conf >= suspect_conf in a frame   (shown, never preempts)
              -> CONFIRMED  conf >= confirm_conf in confirm_frames consecutive analysed frames
              -> LOST       no box for lost_after_s seconds

Only CONFIRMED tracks create a preemption request. The class of a track is the
confidence-weighted vote over all its frames, so a vehicle that flickers between
"ambulance" and "police" is reported as the class it was most often seen as.
"""
from dataclasses import dataclass, field


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def containment(a, b):
    """Intersection over the smaller box: 1.0 when one box lies inside the other."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / small if small > 0 else 0.0


def suppress_nested(boxes, thr=0.7):
    """The detector sometimes puts a second box on part of the same vehicle (a box inside a box).
    Standard NMS keeps both because their IoU is small; drop the lower-confidence one."""
    keep = []
    for b in sorted(boxes, key=lambda x: -x[4]):
        if all(containment(b, k) < thr for k in keep):
            keep.append(b)
    return keep


def _near(a, b):
    """Centre distance relative to box size; tolerates fast motion between frames."""
    ca = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    cb = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    size = max(a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1], 1.0)
    return ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5 / size


@dataclass
class EVTrack:
    tid: int
    first_t: float
    last_t: float
    last_box: list
    streak: int = 0
    hits: int = 0
    max_conf: float = 0.0
    votes: dict = field(default_factory=dict)
    suspected_t: float = None
    confirmed_t: float = None
    confirmed_conf: float = None
    confirmed_cls: str = None       # class as known at the moment of confirmation (causal)
    lost_t: float = None

    @property
    def cls(self):
        return max(self.votes, key=self.votes.get) if self.votes else "unknown"

    @property
    def state(self):
        if self.confirmed_t is not None:
            return "CONFIRMED"
        if self.suspected_t is not None:
            return "SUSPECTED"
        return "CANDIDATE"


def confirm_tracks(frames, p):
    """frames: list of {"t": float, "ev": [[x1,y1,x2,y2,conf,cls_name], ...]} in time order.
    p: ConfirmParams. Returns (tracks, per_frame) where per_frame[i] is a list of
    {"tid", "state", "conf", "cls", "box"} for frame i (state as known AT that frame)."""
    tracks, active, per_frame = [], [], []
    next_id = 1
    for fr in frames:
        t = fr["t"]
        # retire tracks not seen recently
        still = []
        for tr in active:
            if t - tr.last_t > p.lost_after_s:
                tr.lost_t = tr.last_t
            else:
                still.append(tr)
        active = still
        boxes = suppress_nested(fr.get("ev", []))
        used = set()
        out = []
        for b in boxes:
            best, best_score = None, 0.0
            for tr in active:
                if id(tr) in used:
                    continue
                s = max(iou(b, tr.last_box), 0.8 * containment(b, tr.last_box))
                if s < 0.15 and _near(b, tr.last_box) < 0.6:
                    s = 0.15
                if s > best_score:
                    best, best_score = tr, s
            if best is None or best_score < 0.15:
                # camera pans / zooms make the box of a close vehicle jump. A new box that overlaps a still-alive
                # suspected/confirmed track is taken as the same vehicle rather than a second EV (single camera).
                alive = [tr for tr in active if id(tr) not in used and tr.state != "CANDIDATE"
                         and (iou(b, tr.last_box) > 0 or containment(b, tr.last_box) > 0)]
                if alive:
                    best, best_score = max(alive, key=lambda q: q.last_t), 0.15
            if best is None or best_score < 0.15:
                best = EVTrack(next_id, t, t, list(b[:4]))
                next_id += 1
                tracks.append(best)
                active.append(best)
            used.add(id(best))
            tr = best
            conf, name = float(b[4]), b[5]
            tr.last_t, tr.last_box = t, list(b[:4])
            tr.hits += 1
            tr.max_conf = max(tr.max_conf, conf)
            tr.votes[name] = tr.votes.get(name, 0.0) + conf
            if conf >= p.suspect_conf and tr.suspected_t is None:
                tr.suspected_t = t
            if conf >= p.confirm_conf:
                tr.streak += 1
            else:
                tr.streak = 0
            if tr.confirmed_t is None and tr.streak >= p.confirm_frames:
                tr.confirmed_t = t
                tr.confirmed_conf = conf
                tr.confirmed_cls = tr.cls
            # after confirmation the label stays the class the decision was made with
            out.append({"tid": tr.tid, "state": tr.state, "conf": round(conf, 3), "cls": tr.confirmed_cls or tr.cls,
                        "streak": tr.streak, "box": [round(v, 1) for v in b[:4]]})
        # tracks that were active but got no box this frame lose their streak
        for tr in active:
            if id(tr) not in used:
                tr.streak = 0
        per_frame.append(out)
    for tr in active:
        tr.lost_t = tr.last_t
    return tracks, per_frame


def track_summary(tr):
    # The class used for decisions is the one known when the track was confirmed: a real
    # controller cannot use frames that come later. The final vote is kept for analysis.
    return {"tid": tr.tid, "cls": tr.confirmed_cls or tr.cls, "final_cls": tr.cls, "first_t": round(tr.first_t, 2), "last_t": round(tr.last_t, 2),
            "suspected_t": None if tr.suspected_t is None else round(tr.suspected_t, 2),
            "confirmed_t": None if tr.confirmed_t is None else round(tr.confirmed_t, 2),
            "confirmed_conf": tr.confirmed_conf, "max_conf": round(tr.max_conf, 3), "hits": tr.hits,
            "state": tr.state, "votes": {k: round(v, 2) for k, v in tr.votes.items()}}
