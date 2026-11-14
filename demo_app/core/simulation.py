# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Microscopic simulation of a four-approach signalised intersection.

Kept deliberately small and deterministic so every number it produces can be
explained in a viva:
  * 4 approaches (N, E, S, W), 2 inbound lanes each, straight-through movement.
  * Car-following: Intelligent Driver Model (IDM, Treiber et al. 2000).
  * A red (or a yellow the vehicle can still stop for) acts as a stopped
    obstacle at the stop line.
  * Emergency vehicles also obey the signals in the simulation (a real EV may
    cross a red with caution, so the fixed-time EV delay shown is an upper bound).

Inputs are "arrivals": every vehicle detected in the video becomes one arrival
on the approach the video is assigned to, at the time it first appeared.
Other approaches are filled from density settings (Poisson arrivals, fixed seed).
The same arrivals are run twice: with preemption and with fixed-time control.
"""
import math
import random

from .signal_controller import SignalController, APPROACHES

VTYPES = {
    #               length  v0 (m/s)  a (m/s2)  b    T(s)
    "car":         (4.5,    13.9,     1.6,      2.0, 1.3),
    "motorcycle":  (2.2,    13.9,     2.0,      2.5, 1.0),
    "bus":         (11.0,   11.1,     1.0,      1.6, 1.6),
    "truck":       (9.0,    11.1,     0.9,      1.6, 1.6),
    "ambulance":   (6.0,    16.7,     2.2,      3.0, 1.0),
    "fire brigade": (9.0,   15.3,     1.6,      2.5, 1.1),
    "police":      (4.8,    16.7,     2.4,      3.0, 1.0),
}
EV_TYPES = {"ambulance", "fire brigade", "police"}
S0 = 2.0             # jam gap (m)
BOX = 22.0           # width of the conflict area crossed by a through movement (m)
STOP_DECEL = 3.0     # a vehicle that cannot stop at this deceleration runs the yellow
LANE_W = 3.5
YIELD_DIST = 40.0    # an ordinary vehicle with an EV less than this far behind it pulls over (rescue lane)


class Vehicle:
    __slots__ = ("vid", "approach", "lane", "vtype", "source", "is_ev", "ev_id", "suspected",
                 "t_arrival", "t_spawn", "s", "v", "trace", "t_stop", "t_exit", "stopped_time",
                 "stops", "_was_moving", "yellow_go", "length", "v0", "a", "b", "T", "t_cleared")

    def __init__(self, vid, approach, vtype, t_arrival, source, is_ev=False, ev_id=None, suspected=False):
        self.vid, self.approach, self.vtype, self.t_arrival = vid, approach, vtype, t_arrival
        self.source, self.is_ev, self.ev_id, self.suspected = source, is_ev, ev_id, suspected
        self.length, self.v0, self.a, self.b, self.T = VTYPES.get(vtype, VTYPES["car"])
        self.lane = 0
        self.t_spawn = None
        self.s = 0.0
        self.v = 0.0
        self.trace = []
        self.t_stop = None      # crossed the stop line
        self.t_cleared = None   # rear left the conflict area
        self.t_exit = None
        self.stopped_time = 0.0
        self.stops = 0
        self._was_moving = True
        self.yellow_go = False


def idm_acc(veh, gap, dv):
    """IDM acceleration. gap: bumper-to-bumper distance to the leader (m); dv = v - v_leader."""
    v = veh.v
    free = 1.0 - (v / veh.v0) ** 4
    if gap is None:
        return veh.a * free
    s_star = S0 + max(0.0, v * veh.T + v * dv / (2.0 * math.sqrt(veh.a * veh.b)))
    gap = max(gap, 0.1)
    return veh.a * (free - (s_star / gap) ** 2)


def free_flow_time(vtype, distance, v_start, dt=0.1):
    """Travel time over `distance` with no leader and no signal (exact for this model)."""
    vv = Vehicle(0, "N", vtype, 0.0, "x")
    vv.v = min(v_start, vv.v0)
    t = 0.0
    while vv.s < distance and t < 600:
        acc = idm_acc(vv, None, 0.0)
        vv.v = max(0.0, vv.v + acc * dt)
        vv.s += vv.v * dt
        t += dt
    return t


def poisson_times(rate_per_min, t0, t1, rng):
    out = []
    if not rate_per_min or rate_per_min <= 0:
        return out
    lam = rate_per_min / 60.0
    t = t0
    while True:
        t += rng.expovariate(lam)
        if t >= t1:
            return out
        out.append(t)


def pick_type(rng, mix):
    r = rng.random() * sum(mix.values())
    acc = 0.0
    for k, w in mix.items():
        acc += w
        if r <= acc:
            return k
    return "car"


def build_arrivals(detected, sp, video_duration, observed_rate, class_mix, duration):
    """detected: list of {"t": first_seen, "cls": car|bus|..., "initial": bool, "ev_id", "suspected"}.
    Returns arrivals list of dicts sorted by time."""
    rng = random.Random(sp.seed)
    arr = []
    va = sp.video_approach
    for d in detected:
        arr.append({"approach": va, "t": d["t"], "vtype": d["cls"], "source": "video",
                    "initial": d.get("initial", False), "is_ev": d.get("is_ev", False), "ev_id": d.get("ev_id"),
                    "suspected": d.get("suspected", False), "conf": d.get("conf")})
    mix = class_mix or {"car": 1.0}
    if sp.continue_after_video and observed_rate:
        for t in poisson_times(observed_rate, video_duration, duration, rng):
            arr.append({"approach": va, "t": t, "vtype": pick_type(rng, mix), "source": "extrapolated"})
    for a in APPROACHES:
        if a == va:
            continue
        rate = sp.densities.get(a)
        if rate is None:
            rate = observed_rate or 0.0
        n_init = 0
        if observed_rate:
            n_init = int(round(sum(1 for d in detected if d.get("initial")) * (rate / observed_rate))) if rate else 0
        for i in range(min(n_init, 12)):
            arr.append({"approach": a, "t": 0.0, "vtype": pick_type(rng, mix), "source": "density", "initial": True})
        for t in poisson_times(rate, 0.0, duration, rng):
            arr.append({"approach": a, "t": t, "vtype": pick_type(rng, mix), "source": "density"})
    for k, inj in enumerate(sp.inject or []):
        arr.append({"approach": inj.get("approach", "E"), "t": float(inj.get("t", 5.0)),
                    "vtype": inj.get("cls", "ambulance"), "source": "manual", "is_ev": True,
                    "ev_id": f"M{k + 1}", "confirm_t": float(inj.get("t", 5.0)), "conf": None})
    arr.sort(key=lambda x: (x["t"], 0 if x.get("initial") else 1))
    return arr


def simulate(arrivals, ev_confirm_times, sp, sig, cp_priority, preemption=True, duration=60.0):
    """Run the simulation. ev_confirm_times: {ev_id: (t_confirm, conf)} from the video.
    Returns a dict with trajectories, signal history, events and metrics."""
    dt = sp.dt
    L = sp.approach_length_m
    total = L + BOX + L
    ctrl = SignalController(sig, preemption=preemption, video_approach=sp.video_approach)
    vehicles, active = [], {a: [[], []] for a in APPROACHES}
    pending = {a: [] for a in APPROACHES}   # arrivals waiting to enter (entry queue)
    queue_series = {a: [] for a in APPROACHES}
    ai = 0
    vid = 0
    t = 0.0
    requested = set()
    steps = int(round(duration / dt))
    # pre-place initial vehicles (seen in the first frame) on their approach
    init = [x for x in arrivals if x.get("initial")]
    rest = [x for x in arrivals if not x.get("initial")]
    for a in APPROACHES:
        lane_pos = [L - 30.0, L - 30.0 - 6.0]
        mine = [x for x in init if x["approach"] == a]
        for k, x in enumerate(mine):
            vid += 1
            v = Vehicle(vid, a, x["vtype"], 0.0, x["source"], x.get("is_ev", False), x.get("ev_id"),
                        x.get("suspected", False))
            lane = k % 2
            pos = lane_pos[lane]
            if pos - v.length < 2:
                pending[a].append(v)
                vehicles.append(v)
                continue
            v.lane, v.s, v.v, v.t_spawn = lane, pos, 6.0, 0.0
            lane_pos[lane] = pos - v.length - 7.0
            active[a][lane].append(v)
            vehicles.append(v)
    for a in APPROACHES:
        for lane in (0, 1):
            active[a][lane].sort(key=lambda q: -q.s)
    for step in range(steps + 1):
        t = step * dt
        # 1. arrivals -> entry queues
        while ai < len(rest) and rest[ai]["t"] <= t + 1e-9:
            x = rest[ai]
            ai += 1
            vid += 1
            v = Vehicle(vid, x["approach"], x["vtype"], x["t"], x["source"], x.get("is_ev", False),
                        x.get("ev_id"), x.get("suspected", False))
            vehicles.append(v)
            if v.is_ev:
                pending[v.approach].insert(0, v)
            else:
                pending[v.approach].append(v)
        # 2. EV requests (confirmation time from the video or manual injection)
        for v in vehicles:
            if v.is_ev and v.ev_id not in requested:
                tc = None
                if v.ev_id in ev_confirm_times:
                    tc = ev_confirm_times[v.ev_id][0]
                elif v.source == "manual":
                    tc = v.t_arrival
                if tc is not None and t + 1e-9 >= tc:
                    requested.add(v.ev_id)
                    ctrl.request(t, v.ev_id, v.approach, v.vtype, cp_priority.get(v.vtype, 3),
                                 conf=ev_confirm_times.get(v.ev_id, (None, None))[1])
        # 3. spawn from entry queues when there is room
        for a in APPROACHES:
            while pending[a]:
                v = pending[a][0]
                lanes = active[a]

                def room(l):
                    return lanes[l][-1].s - lanes[l][-1].length if lanes[l] else 999.0

                if v.is_ev:
                    # EV takes the lane with fewer vehicles ahead
                    lane = min((0, 1), key=lambda l: (len(lanes[l]), -room(l)))
                elif v.vtype in ("bus", "truck"):
                    lane = 0 if room(0) > S0 + 4 else 1
                else:
                    lane = max((0, 1), key=room)
                lead = lanes[lane][-1] if lanes[lane] else None
                v_in = v.v0 * 0.8 if lead is None else min(v.v0 * 0.8, lead.v + 1.0)
                if room(lane) < S0 + v_in * v.T * 0.8 + 1.0:
                    break
                pending[a].pop(0)
                v.lane = lane
                v.s = 0.0
                v.v = v_in
                v.t_spawn = t
                lanes[lane].append(v)
        # 4. signal controller
        ctrl.step(t, dt)
        # 5. vehicle dynamics
        ev_pos = {a: [x.s for lane_q in active[a] for x in lane_q if x.is_ev and x.s < L] for a in APPROACHES}
        for a in APPROACHES:
            st = ctrl.state[a]
            for lane in (0, 1):
                q = active[a][lane]
                q.sort(key=lambda x: -x.s)
                for i, v in enumerate(q):
                    lead = None
                    for j in range(i - 1, -1, -1):
                        c = q[j]
                        if sp.rescue_lane and v.is_ev and not c.is_ev and c.s < L:
                            continue          # traffic ahead pulls aside: the EV passes queued vehicles
                        if sp.rescue_lane and c.is_ev and not v.is_ev and c.s - c.length < v.s + 1.0:
                            continue          # the EV is overtaking this vehicle right now
                        lead = c
                        break
                    gap = dv = None
                    if lead is not None:
                        gap = lead.s - lead.length - v.s
                        dv = v.v - lead.v
                    if v.s < L:       # before the stop line
                        dist = L - v.s
                        must_stop = False
                        # rescue lane: an ordinary vehicle with an EV close behind it (same approach) pulls over and
                        # waits instead of driving into the junction ahead of the EV
                        if sp.rescue_lane and not v.is_ev and ev_pos[a] and any(
                                0.0 < v.s - e_s < YIELD_DIST for e_s in ev_pos[a]):
                            yg = max(1.0, v.v * v.v / (2 * 2.5) + 0.5)
                            if gap is None or yg < gap:
                                gap, dv = yg, v.v
                        if st == "R":
                            must_stop = True
                        elif st == "Y":
                            if not v.yellow_go:
                                if dist > v.v * v.v / (2 * STOP_DECEL) + 0.5:
                                    must_stop = True
                                else:
                                    v.yellow_go = True
                        else:
                            v.yellow_go = False
                        if must_stop and (gap is None or dist < gap):
                            gap, dv = dist, v.v
                    acc = idm_acc(v, gap, dv if dv is not None else 0.0)
                    acc = max(acc, -9.0)
                    v.v = max(0.0, v.v + acc * dt)
                    v.s += v.v * dt
                    if v.v < 0.5:
                        v.stopped_time += dt
                        if v._was_moving:
                            v.stops += 1
                            v._was_moving = False
                    elif v.v > 2.0:
                        v._was_moving = True
                    if v.t_stop is None and v.s >= L:
                        v.t_stop = t
                        if v.is_ev:
                            ctrl.log(t, "ev_stopline", f"{v.vtype} crossing the stop line on {a}", a, ev_id=v.ev_id)
                    if v.t_cleared is None and v.s - v.length >= L + BOX:
                        v.t_cleared = t
                        if v.is_ev:
                            ctrl.clear(t, v.ev_id)
                # remove exited
                keep = []
                for v in q:
                    if v.s >= total:
                        v.t_exit = t
                    else:
                        keep.append(v)
                active[a][lane] = keep
        # 6. record (10 Hz)
        for a in APPROACHES:
            for lane in (0, 1):
                for v in active[a][lane]:
                    v.trace.append(round(v.s, 1))
        if step % 5 == 0:
            for a in APPROACHES:
                on = [v for lane in (0, 1) for v in active[a][lane] if v.s < L]
                qn = [v for v in on if v.v < 0.5 and v.s > L - 80]
                queue_series[a].append([round(t, 1), len(on) + len(pending[a]), len(qn)])
    return _summarise(vehicles, ctrl, queue_series, sp, duration, preemption)


def _summarise(vehicles, ctrl, queue_series, sp, duration, preemption):
    L = sp.approach_length_m
    dist_clear = L + BOX
    traj = []
    for v in vehicles:
        if v.t_spawn is None:
            continue
        traj.append({"id": v.vid, "a": v.approach, "lane": v.lane, "type": v.vtype, "src": v.source,
                     "ev": v.is_ev, "ev_id": v.ev_id, "sus": v.suspected, "t0": round(v.t_spawn, 2),
                     "s": v.trace})
    evs, ords = [], []
    for v in vehicles:
        if v.is_ev:
            req = next((r for r in ctrl.requests if r["ev_id"] == v.ev_id), None)
            ff = free_flow_time(v.vtype, dist_clear + v.length, v.v0 * 0.8)
            tt = (v.t_cleared - v.t_arrival) if v.t_cleared is not None else None
            evs.append({
                "ev_id": v.ev_id, "cls": v.vtype, "approach": v.approach, "source": v.source,
                "t_arrival": round(v.t_arrival, 2),
                "t_request": None if not req else round(req["t_request"], 2),
                "t_green": None if not req or req["t_green"] is None else round(req["t_green"], 2),
                "response_s": None if not req or req["t_green"] is None else round(req["t_green"] - req["t_request"], 2),
                "t_stopline": None if v.t_stop is None else round(v.t_stop, 2),
                "t_cleared": None if v.t_cleared is None else round(v.t_cleared, 2),
                "travel_s": None if tt is None else round(tt, 2),
                "free_flow_s": round(ff, 2),
                "delay_s": None if tt is None else round(max(0.0, tt - ff), 2),
                "stopped_s": round(v.stopped_time, 1), "stops": v.stops,
                "timeout": bool(req and req.get("timeout")),
            })
        else:
            if v.t_cleared is not None:
                ff = free_flow_time(v.vtype, dist_clear + v.length, v.v0 * 0.8)
                ords.append((v.approach, max(0.0, (v.t_cleared - v.t_arrival) - ff), v.stops))
    per_app = {}
    for a in APPROACHES:
        d = [x[1] for x in ords if x[0] == a]
        q = queue_series[a]
        per_app[a] = {"completed": len(d), "mean_delay_s": round(sum(d) / len(d), 2) if d else None,
                      "max_queue": max((x[2] for x in q), default=0)}
    alld = [x[1] for x in ords]
    unfinished = sum(1 for v in vehicles if not v.is_ev and v.t_cleared is None)
    return {
        "mode": "preemption" if preemption else "fixed",
        "duration": duration, "dt": sp.dt, "L": L, "box": BOX, "lane_w": LANE_W,
        "trajectories": traj,
        "signals": ctrl.history,
        "events": ctrl.events,
        "queues": queue_series,
        "ev": evs,
        "metrics": {
            "vehicles_completed": len(alld),
            "vehicles_unfinished": unfinished,
            "mean_delay_s": round(sum(alld) / len(alld), 2) if alld else None,
            "per_approach": per_app,
        },
    }
