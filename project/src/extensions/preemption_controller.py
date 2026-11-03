"""
🚨 Emergency Preemption Controller
====================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
When an emergency vehicle is detected, this module manages the signal
preemption workflow: logging, decision, countdown, and recovery.
Designed as a standalone module — does NOT modify the existing codebase.
"""

import time
import json
import threading
from datetime import datetime
from pathlib import Path
from collections import deque

# Log directory
LOG_DIR = Path(__file__).parent.parent.parent / "results" / "preemption_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class PreemptionState:
    """Possible states for the preemption controller."""
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"


class SignalPhase:
    """
    Standard NEMA-style signal phases for realistic demonstration:
      1. NORMAL: Cross Traffic is GREEN, Emergency Lane is RED
      2. CLEARING_CROSS_YELLOW: Cross Traffic transitions to YELLOW (3.5s)
      3. ALL_RED_CLEARANCE: All signals hold RED to safely empty the intersection (1.5s)
      4. EMERGENCY_GREEN: Emergency Corridor forced to GREEN (12-15s hold)
      5. CLEARING_EMERGENCY_YELLOW: Emergency Lane transitions to YELLOW (3.0s)
      6. RECOVERY_ALL_RED: All signals hold RED briefly before returning to normal (1.5s)
    """
    NORMAL = "NORMAL"
    CLEARING_CROSS_YELLOW = "CLEARING_CROSS_YELLOW"
    ALL_RED_CLEARANCE = "ALL_RED_CLEARANCE"
    EMERGENCY_GREEN = "EMERGENCY_GREEN"
    CLEARING_EMERGENCY_YELLOW = "CLEARING_EMERGENCY_YELLOW"
    RECOVERY_ALL_RED = "RECOVERY_ALL_RED"


class PreemptionController:
    """
    Manages traffic-signal preemption when an emergency vehicle is detected.
    Provides realistic step-by-step traffic light transition:
    RED → [Ambulance Detected] → Other lanes YELLOW → All RED → EMERGENCY GREEN →
    [Ambulance Clears] → Emergency YELLOW → All RED → Normal GREEN.
    """

    def __init__(self,
                 preemption_duration=12.0,
                 cooldown_duration=6.0,
                 min_confidence=0.50,
                 confirm_frames=3):
        self.preemption_duration = preemption_duration
        self.cooldown_duration = cooldown_duration
        self.min_confidence = min_confidence
        self.confirm_frames = confirm_frames

        # Phase transition durations (seconds)
        self.yellow_clearance_duration = 3.5
        self.all_red_duration = 1.5
        self.recovery_yellow_duration = 3.0
        self.recovery_all_red_duration = 1.5

        # State machine
        self._state = PreemptionState.IDLE
        self._state_start = 0.0
        self._signal_phase = SignalPhase.NORMAL
        self._phase_start = time.time()
        self._lock = threading.Lock()

        # Detection confirmation buffer
        self._detection_buffer = deque(maxlen=confirm_frames)

        # Event log
        self._event_log = []
        self._active_event = None

        # Callbacks
        self._on_preemption_start = None
        self._on_preemption_end = None
        self._on_state_change = None

        # Stats
        self.total_preemptions = 0
        self.total_emergency_detections = 0

        # Background ticker for real-time smooth phase progression
        self._running = True
        self._ticker_thread = threading.Thread(target=self._run_ticker, daemon=True)
        self._ticker_thread.start()

    def _run_ticker(self):
        """Continuously tick state machine for smooth light transitions."""
        while self._running:
            time.sleep(0.1)
            with self._lock:
                self._tick(time.time())

    # ---- Public API ----

    @property
    def state(self):
        return self._state

    @property
    def is_preempting(self):
        return self._state in (PreemptionState.TRIGGERED, PreemptionState.ACTIVE)

    def register_callbacks(self, on_start=None, on_end=None, on_state=None):
        self._on_preemption_start = on_start
        self._on_preemption_end = on_end
        self._on_state_change = on_state

    def process_detections(self, emergency_vehicles):
        """Call this every frame with detected emergency vehicles."""
        now = time.time()
        with self._lock:
            self._tick(now)

            if emergency_vehicles:
                self.total_emergency_detections += 1
                best = max(emergency_vehicles, key=lambda d: d.get('confidence', 0.5))
                if best.get('confidence', 0) >= self.min_confidence:
                    self._detection_buffer.append(now)

            recent = [t for t in self._detection_buffer if now - t < 2.5]
            confirmed = len(recent) >= self.confirm_frames

            if confirmed and self._state == PreemptionState.IDLE:
                self._trigger_preemption(now, emergency_vehicles)

            return self.get_status()

    def simulate_emergency(self, vehicle_type='ambulance', confidence=0.96):
        """Manually trigger preemption workflow for project demonstration."""
        with self._lock:
            if self.is_preempting:
                return self.get_status()
            now = time.time()
            self._trigger_preemption(now, [{'class': vehicle_type, 'confidence': confidence}])
            return self.get_status()

    def get_status(self):
        """Return current preemption and signal lights status."""
        signals = self.get_signals()
        return {
            'state': self._state,
            'is_preempting': self.is_preempting,
            'remaining_seconds': signals['phase_remaining'],
            'total_preemptions': self.total_preemptions,
            'total_detections': self.total_emergency_detections,
            'active_event': self._active_event,
            'signal_action': self._get_signal_action(),
            'signals': signals,
        }

    def get_signals(self):
        """Detailed signal light breakdown for UI demonstration."""
        now = time.time()
        elapsed = now - self._phase_start

        if self._signal_phase == SignalPhase.CLEARING_CROSS_YELLOW:
            dur = self.yellow_clearance_duration
            desc = "🟡 Cross Traffic Yellow: Warning cross lanes to slow and clear junction"
        elif self._signal_phase == SignalPhase.ALL_RED_CLEARANCE:
            dur = self.all_red_duration
            desc = "🔴 All-Red Safety Hold: Intersection clearance in progress"
        elif self._signal_phase == SignalPhase.EMERGENCY_GREEN:
            dur = self.preemption_duration
            desc = "🟢 EMERGENCY CORRIDOR FORCED GREEN: Priority clear path for Ambulance"
        elif self._signal_phase == SignalPhase.CLEARING_EMERGENCY_YELLOW:
            dur = self.recovery_yellow_duration
            desc = "🟡 Emergency Yellow: Ambulance passed, clearing emergency lane"
        elif self._signal_phase == SignalPhase.RECOVERY_ALL_RED:
            dur = self.recovery_all_red_duration
            desc = "🔴 Recovery All-Red: Re-aligning intersection for normal flow"
        else:
            dur = 0
            desc = "🟢 Standard Signal Flow: Cross Traffic Green, Emergency Corridor Red"

        remaining = max(0.0, dur - elapsed) if dur > 0 else 0.0

        em_green = (self._signal_phase == SignalPhase.EMERGENCY_GREEN)
        em_yellow = (self._signal_phase == SignalPhase.CLEARING_EMERGENCY_YELLOW)
        em_red = not (em_green or em_yellow)

        cr_green = (self._signal_phase == SignalPhase.NORMAL)
        cr_yellow = (self._signal_phase == SignalPhase.CLEARING_CROSS_YELLOW)
        cr_red = not (cr_green or cr_yellow)

        return {
            'phase': self._signal_phase,
            'phase_description': desc,
            'phase_duration': dur,
            'phase_remaining': round(remaining, 1),
            'emergency_lane': {
                'name': 'North-South Ambulance Corridor',
                'red': em_red,
                'yellow': em_yellow,
                'green': em_green,
                'state': 'GREEN' if em_green else ('YELLOW' if em_yellow else 'RED'),
                'is_priority': em_green,
            },
            'cross_lane': {
                'name': 'East-West Cross Traffic Lanes',
                'red': cr_red,
                'yellow': cr_yellow,
                'green': cr_green,
                'state': 'GREEN' if cr_green else ('YELLOW' if cr_yellow else 'RED'),
                'is_priority': False,
            },
            'optical_strobe': self.is_preempting,
            'state': self._state,
            'is_preempting': self.is_preempting,
            'active_event': self._active_event
        }

    def get_event_log(self, limit=20):
        return self._event_log[-limit:]

    def force_reset(self):
        """Force back to IDLE and restore normal green."""
        with self._lock:
            self._set_state(PreemptionState.IDLE)
            self._signal_phase = SignalPhase.NORMAL
            self._phase_start = time.time()
            self._active_event = None
            self._detection_buffer.clear()

    # ---- State Machine Internals ----

    def _tick(self, now):
        elapsed = now - self._phase_start

        if self._state == PreemptionState.TRIGGERED:
            if self._signal_phase == SignalPhase.CLEARING_CROSS_YELLOW:
                if elapsed >= self.yellow_clearance_duration:
                    self._signal_phase = SignalPhase.ALL_RED_CLEARANCE
                    self._phase_start = now
            elif self._signal_phase == SignalPhase.ALL_RED_CLEARANCE:
                if elapsed >= self.all_red_duration:
                    self._signal_phase = SignalPhase.EMERGENCY_GREEN
                    self._phase_start = now
                    self._set_state(PreemptionState.ACTIVE, now)

        elif self._state == PreemptionState.ACTIVE:
            if elapsed >= self.preemption_duration:
                self._signal_phase = SignalPhase.CLEARING_EMERGENCY_YELLOW
                self._phase_start = now
                self._set_state(PreemptionState.COOLDOWN, now)

        elif self._state == PreemptionState.COOLDOWN:
            if self._signal_phase == SignalPhase.CLEARING_EMERGENCY_YELLOW:
                if elapsed >= self.recovery_yellow_duration:
                    self._signal_phase = SignalPhase.RECOVERY_ALL_RED
                    self._phase_start = now
            elif self._signal_phase == SignalPhase.RECOVERY_ALL_RED:
                if elapsed >= self.recovery_all_red_duration:
                    self._end_preemption(now)

    def _trigger_preemption(self, now, vehicles):
        best = max(vehicles, key=lambda d: d.get('confidence', 0.9)) if vehicles else {'class': 'ambulance', 'confidence': 0.95}
        self._active_event = {
            'id': self.total_preemptions + 1,
            'vehicle_type': best.get('class', 'ambulance'),
            'confidence': best.get('confidence', 0.95),
            'triggered_at': datetime.now().isoformat(),
            'timestamp': now,
        }

        self.total_preemptions += 1
        self._set_state(PreemptionState.TRIGGERED, now)
        self._signal_phase = SignalPhase.CLEARING_CROSS_YELLOW
        self._phase_start = now
        self._log_event('PREEMPTION_TRIGGERED', self._active_event)

        if self._on_preemption_start:
            try:
                self._on_preemption_start(self._active_event)
            except Exception:
                pass

        print(f"🚨 PREEMPTION #{self.total_preemptions}: "
              f"{best.get('class', 'ambulance').upper()} detected ({best.get('confidence', 0.95):.0%}) → Initiating cross-lane yellow clearance")

    def _end_preemption(self, now):
        if self._active_event:
            self._active_event['ended_at'] = datetime.now().isoformat()
            self._active_event['duration'] = round(now - self._active_event['timestamp'], 1)
            self._event_log.append(self._active_event.copy())
            self._log_event('PREEMPTION_ENDED', self._active_event)

        if self._on_preemption_end:
            try:
                self._on_preemption_end(self._active_event)
            except Exception:
                pass

        self._active_event = None
        self._detection_buffer.clear()
        self._set_state(PreemptionState.IDLE, now)
        self._signal_phase = SignalPhase.NORMAL
        self._phase_start = now
        print("✅ Preemption ended → Cross lanes restored to Green")

    def _set_state(self, new_state, now=None):
        old = self._state
        self._state = new_state
        self._state_start = now or time.time()

        if self._on_state_change and old != new_state:
            try:
                self._on_state_change(old, new_state)
            except Exception:
                pass

    def _get_signal_action(self):
        if self._signal_phase == SignalPhase.EMERGENCY_GREEN:
            return "FORCE_GREEN_EMERGENCY_LANE"
        elif self._signal_phase in (SignalPhase.CLEARING_CROSS_YELLOW, SignalPhase.ALL_RED_CLEARANCE):
            return "CLEARING_CROSS_TRAFFIC"
        elif self._signal_phase in (SignalPhase.CLEARING_EMERGENCY_YELLOW, SignalPhase.RECOVERY_ALL_RED):
            return "RESTORING_NORMAL_CYCLE"
        return "NORMAL_OPERATION"

    def _log_event(self, event_type, data):
        try:
            log_file = LOG_DIR / f"preemption_{datetime.now():%Y%m%d}.jsonl"
            entry = {
                'event': event_type,
                'timestamp': datetime.now().isoformat(),
                'data': data,
            }
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass
