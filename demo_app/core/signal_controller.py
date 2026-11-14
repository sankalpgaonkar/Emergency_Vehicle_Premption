# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Signal controller for a four-approach intersection with emergency-vehicle preemption.

Normal operation is a fixed-time two-phase cycle:
    NS green -> NS yellow -> all red -> EW green -> EW yellow -> all red -> ...

Preemption state machine (only when preemption is enabled):

    NORMAL --(confirmed EV request on approach A)--> PREEMPT_CLEAR
        every approach except A that is green turns yellow, then red;
        if the cross street was moving, an all-red interval follows.
        If A is already green it simply stays green (green extension).
    PREEMPT_CLEAR --(conflicts cleared)--> PREEMPT_GREEN
        A green, all other approaches red. Held until every EV requesting A
        has crossed the intersection, at least preempt_min_green and at most
        preempt_max_green seconds.
    PREEMPT_GREEN --(EV cleared, another EV waiting on B)--> PREEMPT_CLEAR (towards B)
    PREEMPT_GREEN --(EV cleared, no request)--> RECOVERY
        A yellow -> all red -> normal cycle resumes with the green of the axis
        that was held red (it waited longest).

Safety rules that are never skipped: every green ends with a full yellow, and
the cross street gets an all-red interval before a conflicting green.
"""

AXIS = {"N": "NS", "S": "NS", "E": "EW", "W": "EW"}
APPROACHES = ["N", "E", "S", "W"]


class SignalController:
    def __init__(self, sp, preemption=True, video_approach="N"):
        self.p = sp
        self.preemption = preemption
        self.stages = [("NS", "G", sp.green_ns), ("NS", "Y", sp.yellow), ("ALL", "R", sp.all_red),
                       ("EW", "G", sp.green_ew), ("EW", "Y", sp.yellow), ("ALL", "R", sp.all_red)]
        va_axis = AXIS[video_approach]
        init = sp.initial_state
        if init == "video_red":
            start_axis = "EW" if va_axis == "NS" else "NS"
        elif init == "video_green":
            start_axis = va_axis
        else:
            start_axis = init if init in ("NS", "EW") else "NS"
        self.stage_idx = 0 if start_axis == "NS" else 3
        self.stage_t = 0.0
        # cycle_offset_s: start the fixed cycle this many seconds later in its sequence (used to sweep the
        # EV's arrival phase over the whole cycle in evaluate.py)
        off = float(getattr(sp, "cycle_offset_s", 0.0) or 0.0) % sum(d for _, _, d in self.stages)
        while off > 0:
            dur = self.stages[self.stage_idx][2]
            if off < dur:
                self.stage_t = off
                break
            off -= dur
            self.stage_idx = (self.stage_idx + 1) % len(self.stages)
        self.mode = "NORMAL"
        self.state = {a: "R" for a in APPROACHES}
        self._apply_stage()
        self.requests = []        # pending EV requests (dicts)
        self.target = None        # approach being served
        self.timers = {}          # per-approach yellow countdowns during preemption/recovery
        self.allred_left = 0.0
        self.need_allred = False
        self.hold_t = 0.0
        self.events = []
        self.history = []         # [(t, state_string, mode)]
        self._last_sig = None

    # ---------- helpers ----------
    def _apply_stage(self):
        axis, col, _ = self.stages[self.stage_idx]
        for a in APPROACHES:
            self.state[a] = col if (axis != "ALL" and AXIS[a] == axis) else "R"

    def sig(self):
        return "".join(self.state[a] for a in APPROACHES)

    def log(self, t, kind, text, approach=None, **extra):
        e = {"t": round(t, 2), "kind": kind, "text": text}
        if approach:
            e["approach"] = approach
        e.update(extra)
        self.events.append(e)

    def _record(self, t):
        s = self.sig()
        key = (s, self.mode)
        if key != self._last_sig:
            self.history.append([round(t, 2), s, self.mode])
            self._last_sig = key

    # ---------- requests ----------
    def request(self, t, ev_id, approach, cls, priority, conf=None):
        r = {"ev_id": ev_id, "approach": approach, "cls": cls, "priority": priority, "t_request": t,
             "t_green": None, "cleared": False}
        if not self.preemption:
            self.log(t, "ev_no_preempt", f"{cls} confirmed on {approach} — fixed-time mode, no preemption", approach,
                     ev_id=ev_id)
            r["t_green"] = None
            self.requests.append(r)
            return r
        self.requests.append(r)
        waiting = [q for q in self.requests if not q["cleared"] and q is not r]
        if waiting and self.target and self.target != approach:
            self.log(t, "ev_queued", f"{cls} on {approach} queued behind EV on {self.target}", approach, ev_id=ev_id)
        else:
            self.log(t, "ev_request", f"Preemption requested by {cls} on {approach}", approach, ev_id=ev_id)
        if self.mode == "PREEMPT_GREEN" and self.target == approach and self.state[approach] == "G":
            r["t_green"] = t          # joins a preemption already serving this approach
        return r

    def clear(self, t, ev_id):
        for r in self.requests:
            if r["ev_id"] == ev_id and not r["cleared"]:
                r["cleared"] = True
                r["t_clear"] = t
                self.log(t, "ev_cleared", f"{r['cls']} cleared the intersection ({r['approach']})", r["approach"],
                         ev_id=ev_id)

    def _pending(self):
        q = [r for r in self.requests if not r["cleared"]]
        q.sort(key=lambda r: (r["priority"], r["t_request"]))
        return q

    # ---------- main step ----------
    def step(self, t, dt):
        pend = self._pending() if self.preemption else []
        if self.mode in ("NORMAL", "RECOVERY") and pend:
            self._start_preempt(t, pend[0]["approach"])
        if self.mode == "NORMAL":
            self._step_normal(t, dt)
        elif self.mode == "PREEMPT_CLEAR":
            self._step_clear(t, dt)
        elif self.mode == "PREEMPT_GREEN":
            self._step_hold(t, dt, pend)
        elif self.mode == "RECOVERY":
            self._step_recovery(t, dt)
        self._record(t)

    def _step_normal(self, t, dt):
        self.stage_t += dt
        dur = self.stages[self.stage_idx][2]
        if self.stage_t >= dur - 1e-9:
            self.stage_idx = (self.stage_idx + 1) % len(self.stages)
            self.stage_t = 0.0
            self._apply_stage()

    def _start_preempt(self, t, A):
        prev = self.mode
        self.mode = "PREEMPT_CLEAR"
        self.target = A
        self.timers = {}
        self.need_allred = False
        cross = [a for a in APPROACHES if AXIS[a] != AXIS[A]]
        for a in APPROACHES:
            if a == A and self.state[a] == "G":
                continue
            if self.state[a] == "G":
                self.state[a] = "Y"
                self.timers[a] = self.p.yellow
            elif self.state[a] == "Y":
                # continue the running yellow; remaining time estimated from the normal stage
                rem = self.p.yellow - (self.stage_t if self.mode != "RECOVERY" else 0.0)
                self.timers[a] = max(0.5, rem if prev == "NORMAL" else self.timers.get(a, self.p.yellow))
            if a in cross and self.state[a] in ("G", "Y"):
                self.need_allred = True
        if self.state[A] == "Y":
            self.need_allred = True
        if prev == "NORMAL":
            axis, col, _ = self.stages[self.stage_idx]
            if axis == "ALL":
                # already in an all-red interval: honour the remainder
                self.need_allred = True
        self.allred_left = self.p.all_red if self.need_allred else 0.0
        if self.state[A] == "G":      # green extension: the EV approach never stops being green
            for r in self._pending():
                if r["approach"] == A and r["t_green"] is None:
                    r["t_green"] = t
        self.log(t, "preempt_start", f"Clearing conflicting approaches for EV on {A}"
                 + (" (green extended)" if self.state[A] == "G" else ""), A)

    def _step_clear(self, t, dt):
        A = self.target
        done = True
        for a, left in list(self.timers.items()):
            left -= dt
            if left <= 1e-9:
                self.state[a] = "R"
                del self.timers[a]
            else:
                self.timers[a] = left
                done = False
        if not done:
            return
        if self.state[A] != "G":
            if self.allred_left > 1e-9:
                self.allred_left -= dt
                return
            self.state[A] = "G"
        self.mode = "PREEMPT_GREEN"
        self.hold_t = 0.0
        for r in self._pending():
            if r["approach"] == A and r["t_green"] is None:
                r["t_green"] = t
        self.log(t, "preempt_green", f"{A} GREEN for emergency vehicle — all other approaches RED", A)

    def _step_hold(self, t, dt, pend):
        A = self.target
        self.hold_t += dt
        for r in pend:
            if r["approach"] == A and r["t_green"] is None:
                r["t_green"] = t
        mine = [r for r in pend if r["approach"] == A]
        if mine and self.hold_t < self.p.preempt_max_green:
            return
        if self.hold_t < self.p.preempt_min_green:
            return
        if mine:
            self.log(t, "preempt_timeout", f"Max preemption green ({self.p.preempt_max_green:.0f}s) reached on {A}", A)
            for r in mine:
                r["timeout"] = True
                r["cleared"] = True
        others = [r for r in self._pending() if r["approach"] != A]
        if others:
            self._start_preempt(t, others[0]["approach"])
            return
        # recovery
        self.mode = "RECOVERY"
        self.timers = {A: self.p.yellow}
        self.state[A] = "Y"
        self.allred_left = self.p.all_red
        self.log(t, "recovery", f"EV passed — {A} yellow, returning to normal cycle", A)

    def _step_recovery(self, t, dt):
        A = self.target
        if self.timers:
            left = self.timers[A] - dt
            if left <= 1e-9:
                self.state[A] = "R"
                self.timers = {}
            else:
                self.timers[A] = left
            return
        if self.allred_left > 1e-9:
            self.allred_left -= dt
            return
        # resume normal cycle with the axis that was held red
        resume_axis = "EW" if AXIS[A] == "NS" else "NS"
        self.stage_idx = 0 if resume_axis == "NS" else 3
        self.stage_t = 0.0
        self.mode = "NORMAL"
        self.target = None
        self._apply_stage()
        self.log(t, "normal", f"Normal cycle resumed ({resume_axis} green)")
