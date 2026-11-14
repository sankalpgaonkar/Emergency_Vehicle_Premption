# Comparable open-source projects

Read on 2026-11-03. Stars, licence and last push come from the GitHub REST API on that date (licence = the SPDX id GitHub detects from the repo's own LICENSE file; "no licence" means no licence file, which legally means all rights reserved — do not copy code from those). "Read" says what was actually inspected: the code (specific files named) or only the README. Ideas are for re-implementing in your own words/code, not copying.

Quick ranking for this project: 1 (relay), 2 (CARLA preemption), 3 (GreenCorridor design), 4 (siren+vision AND-fusion), 5 (Pygame adaptive timer) and 7 (SUMO V2X metrics) carry the most directly usable ideas.

---

## 1. kafle1/relay — YOLO counts → max-pressure controller with ambulance preemption
- URL: https://github.com/kafle1/relay
- Licence: AGPL-3.0 · Stars: 1 · last push 2026-11-02
- Read: code — `src/controller.py` (758 lines, including its built-in invariant tests), README; browser sim in `sim/` (Three.js).
- What it does: one fixed camera → YOLO per-approach counts (PCU-weighted) → queue-weighted max-pressure phase selection with min/max green, gap-out, yellow and all-red (1.5 s default) clearance, anti-starvation, pedestrians, and emergency preemption. `compare.html` runs a fixed timer and the adaptive controller side by side on the same seeded arrivals.
- Honest notes: the preemption logic is the most carefully engineered of all repos read; it ships assertion tests for "single dropped detection frame must not abandon the preempt", "crossing sirens are sequenced, never raced", and "max_preempt bounds a continuous hold". However, in an earlier benchmark on this box (Oct 2026, 44 ambulance / 10 fire / 98 negative photos) its shipped fine-tuned detector found 0/44 ambulances at conf 0.25, so its ambulance trigger in practice depends on the synthetic sim. README says the paper is "under review at IEEE T-ITS" — not verifiable.
- Borrow: (a) an emergency **latch/hold** (`emergency_hold = 2.5 s`): a detection keeps the approach "EV present" for a short window, decaying each tick, so one missed frame does not drop the preemption; (b) a **max preemption cap** (`max_preempt = 60 s`) so a stuck detection cannot freeze the junction; (c) when two EVs are on conflicting approaches, serve the longest-waiting one, then the other; (d) the **same-seed side-by-side** fixed vs preemption view. Write these as your own code: AGPL-3.0 code copied into your project would make your project AGPL too.

## 2. Gianvi-lan/carla-emergency-preemption — CARLA, 4 infrastructure cameras, YOLO26n, preemption benchmark
- URL: https://github.com/Gianvi-lan/carla-emergency-preemption
- Licence: MIT · Stars: 1 · last push 2026-04-03
- Read: code — `src/traffic_control/smart_wrapper.py`, `scripts/run_demo.py`, benchmark CSVs in `experiments/benchmark_results/`; README, BENCHMARK.md.
- What it does: one camera per junction arm in CARLA; a 6-class YOLO (3 emergency + 3 civilian) at conf 0.5; when an EV is seen on an arm, that light is frozen green and all others red; an 8 s (simulated-time) cooldown between emergencies and a 3 s minimum green for passage.
- Honest notes: results are backed by raw CSVs. From `test_a_single_vehicle_…csv` (30 runs each) I computed mean EV crossing time 33.50 s with CARLA's native lights vs 12.93 s with preemption (simulated, CARLA). `test_b_multi_vehicle_…csv` (30 runs) has ambulance + fire truck + police arriving together; `priority_respected` is True in 30/30. Safety gap: `_trigger_emergency_green` switches the conflicting lights straight to red with **no yellow or all-red clearance**, which MUTCD Sec. 4F.19 forbids for real signals.
- Borrow: (a) the **two-test benchmark design** — Test A single EV, native vs preemption, many runs with random approach; Test B three EV classes at once with a "priority respected" pass/fail; (b) a 2×2 camera grid view; (c) use it as a counter-example for why the demo inserts yellow + all-red.

## 3. FWZ8804/greencorridor — four streams, YOLOv8n + beacon light + YAMNet siren, ESP32 lights
- URL: https://github.com/FWZ8804/greencorridor
- Licence: no licence · Stars: 0 · last push 2026-10-01
- Read: README only — the repository contains just README.md (0 code files), so none of it can be verified.
- What it describes: one video per approach (N/S/E/W); per stream YOLOv8n vehicles + red/blue beacon analysis + IoU tracking + YAMNet siren score on that stream's audio, fused into one emergency confidence; confirmation = **confidence ≥ 0.70 for 3 consecutive frames**; direction = the stream it came from; the current green goes **yellow (12 s) then red**; EV approach stays green **until clearance** (not a fixed time); FIFO queue of EVs; normal timers suspended and **resumed from the saved state** after clearance.
- Borrow: the clean state description (detect → confirm k frames → clear conflicting via yellow → hold until clearance → resume saved cycle) is close to what the demo needs and is a good template for the paper's state-machine figure; "direction = which video it came from" is an honest answer to the single-camera mapping problem.

## 4. vinay3254/ambulance — siren (FFT) AND vision (OCR "ECNALUBMA" + colour) → lights
- URL: https://github.com/vinay3254/ambulance
- Licence: no licence · Stars: 8 · last push 2026-08-22
- Read: code — `main.py`, `traffic_controller.py`, `audio_detector.py`, `camera_detector.py`.
- What it does: audio band-pass 500–2000 Hz + FFT dominant frequency in the 700–1800 Hz sweep band → siren confidence (threshold 0.65); camera confidence = 0.5·OCR match of the mirrored word + 0.3·colour + 0.2·shape (threshold 0.6). Preemption fires only when **both** agree; it is released after **5 consecutive all-clear checks** (`CLEAR_THRESHOLD = 5`).
- Honest notes: hackathon prototype ("Hackathon Prototype v1.0" in README); the simulated audio is a synthetic sweep; `trigger_emergency` sets other lanes red and the EV lane green immediately (no yellow); no evaluation numbers.
- Borrow: (a) **AND-fusion of two independent evidence channels** to cut false activations (optional siren check on the uploaded video's audio track); (b) **release hysteresis** — end preemption only after M consecutive negative checks, not on the first miss.

## 5. mihir-m-gandhi/Adaptive-Traffic-Signal-Timer — YOLO counts → green time, Pygame 4-way sim
- URL: https://github.com/mihir-m-gandhi/Adaptive-Traffic-Signal-Timer
- Licence: Apache-2.0 · Stars: 202 · last push 2022-10-27
- Read: code — `Code/YOLO/darkflow/simulation.py`, `vehicle_detection.py`; README.
- What it does: a Pygame four-way intersection with signal timers and per-direction vehicle counts on screen; green time for the next phase computed from counts of each class: `greenTime = ceil((nCar·2 + nRickshaw·2.25 + nBus·2.5 + nTruck·2.5 + nBike·1) / (lanes+1))`, clamped to [10, 60] s, yellow 5 s.
- Honest notes: in the shipped `simulation.py` the call to the YOLO detector is commented out (`# from vehicle_detection import detection`) — the timer uses the simulation's own spawned vehicles, not camera detections. Darkflow/YOLOv2-era code.
- Borrow: (a) the **count → green-time rule with per-class discharge times and min/max clamp** — simple, explainable, and easy to show on screen as an "adaptive (non-EV) mode"; (b) the on-canvas layout: timer next to each signal head and a vehicle count per approach.

## 6. Heram21/Intelligent-Adaptive-Traffic-Signal-Control-…-Emergency-Vehicle-Priority — Pygame sim + ambulance override
- URL: https://github.com/Heram21/Intelligent-Adaptive-Traffic-Signal-Control-Using-Computer-Vision-with-Emergency-Vehicle-Priority
- Licence: Apache-2.0 · Stars: 2 · last push 2026-05-03
- Read: code — `Simulation/simulation.py`, `vehicle_detection.py`; README.
- What it does: same structure as project 5 (identical `TrafficSignal(red, yellow, green, minimum, maximum)` class, the same comment "Coordinates of signal image, timer, and vehicle count", the same per-class pass times) plus an `ambulance` vehicle class, an emergency queue (`deque`) and a saved "next normal" phase to resume after the emergency.
- Honest notes: appears derived from project 5 and its README does not mention it (Apache-2.0 requires keeping attribution notices). README claims real-time YOLO detection, but the YOLO import is commented out and the "emergency detection" checks the class of simulated vehicles.
- Borrow: **save the interrupted phase and resume it** after the EV clears, plus an EV queue; also a cautionary example — a demo where the sim is not driven by detections is exactly what your faculty brief says to avoid.

## 7. ajaypokkali-source/ambulance-v2x — SUMO/TraCI V2V + V2I + I2I corridor
- URL: https://github.com/ajaypokkali-source/ambulance-v2x
- Licence: no licence · Stars: 0 · last push 2026-10-21
- Read: code — `v2x_multi/v2x_multi_test.py` and module list; README. An earlier task on this box ran its comparison with SUMO 1.28 (pip) in Oct 2026.
- What it does: V2I preemption when the ambulance is within 100 m of a signal (`PREEMPTION_DISTANCE`), I2I pre-arming the next junction at 220 m, V2V lane clearing of blocking cars, restore normal operation after the ambulance passes (`PASS_DISTANCE = −10 m`).
- Honest notes: when re-run here, total EV travel time went from 1283.5 s (baseline, 381.5 s stopped, 18 stops) to 824.0 s (full V2X, 3.5 s stopped, 2 stops), simulated in SUMO; V2I+I2I alone gave 827.5 s. These are its scenario's numbers, not general results.
- Borrow: the **EV metric triplet — travel time, stopped time, number of stops** — and distance-based activation/release (activate at d ≤ D_on, release when the EV is past the stop line by a margin).

## 8. izdeen03/EV-GreenWave-Simulation-Berlin — bachelor thesis, SUMO preemption vs green wave
- URL: https://github.com/izdeen03/EV-GreenWave-Simulation-Berlin
- Licence: MIT · Stars: 0 · last push 2025-11-02
- Read: code — `Projeckt files/Original/plot.py`, `outputt/plot_queues.py`; README.
- What it does: SUMO model of Sonnenallee (Berlin) comparing baseline, rule-based preemption and green-wave coordination; plots EV travel time and **mean queue length on the main road and on cross streets during the EV's travel window**, baseline vs green wave.
- Honest notes: README says TraCI scripts are included, but only plotting and network-building scripts are in the repo; the control logic itself is not published.
- Borrow: measure the **side-street queue length during the EV window** (and the Δ vs baseline) as the "cost to general traffic" metric.

## 9. msnotfound/rl-emergency-traffic-control — PPO (sumo-rl) with ambulance-weighted reward
- URL: https://github.com/msnotfound/rl-emergency-traffic-control
- Licence: MIT · Stars: 1 · last push 2026-05-31
- Read: code — `train_scenario_s.py`, `train_robust.py`, README. An earlier task on this box ran its shipped model headless (Oct 2026).
- What it does: PPO over two junctions; reward = −(0.7·Σ lane waiting time + 5000 per waiting ambulance); an observation wrapper appends 20 "ambulance in lane" slots.
- Honest notes: the description claims "~70% faster ambulance travel vs fixed-time"; on the earlier run here the shipped model's own metric printout was broken ("Total ambulance time: −10.0 s"), so the claim could not be reproduced. Also, `train_robust.py` maps lanes to slots with `abs(hash(lane_id)) % 20`; Python randomises string hashes per process unless PYTHONHASHSEED is fixed, so the slot for a lane differs between training and testing runs.
- Borrow: the **EV-weighted reward** idea (penalise EV waiting far more than car waiting) as a one-line extension of your PPO agent — and the bug as a lesson: use a fixed lane index, not `hash()`.

## 10. LucasAlegre/sumo-rl — the RL environment your PPO agent uses
- URL: https://github.com/LucasAlegre/sumo-rl
- Licence: MIT · Stars: 1,099 · last push 2026-03-08
- Read: code — `sumo_rl/environment/env.py`, `traffic_signal.py`; README.
- What it does: Gymnasium/PettingZoo wrapper over SUMO signals; defaults delta_time 5 s, yellow_time 2 s, min_green 5 s, max_green 50 s; built-in rewards `diff-waiting-time`, `average-speed`, `queue`, `pressure`, plus custom `reward_fn`.
- Borrow: cite it properly (README asks for the @misc citation, Alegre 2019); state the defaults you used in the experimental-setup table; a custom `reward_fn` is the clean place to add EV priority.

## 11. ganeshmohane/Multiple-Emergency-Vehicles-Detection-and-Traffic-Management-Using-Deep-Learning — YOLOv8 3-class EV detector (SIH 2024)
- URL: https://github.com/ganeshmohane/Multiple-Emergency-Vehicles-Detection-and-Traffic-Management-Using-Deep-Learning
- Licence: no licence · Stars: 1 · last push 2025-04-08
- Read: code — `Prioterization Algorithm/traffic_simulation.py`, `traffic_light.py`, UI scripts; README.
- What it does: YOLOv8 detector for ambulance / fire truck / police (same three classes as yours) with Tkinter UIs for image/video.
- Honest notes: the "prioritization algorithm" files are print-statement stubs (`set_signal` prints "Setting signal for lane …"). In the earlier benchmark on this box its weights found 30/44 ambulances at conf 0.25 but also fired on 13/98 non-emergency photos (25/44 and 6/98 at 0.5).
- Borrow: a **same-classes baseline** for your paper — report your detector next to an independent model on the same held-out photos, including the **false-positive rate on look-alike negatives** (vans, white trucks, buses).

## 12. sheelabhadra/Emergency-Vehicle-Detection — audio siren detection (three paper re-implementations)
- URL: https://github.com/sheelabhadra/Emergency-Vehicle-Detection
- Licence: no licence · Stars: 48 · last push 2019-06-27
- Read: code — `Paper-2/em_detection.py` (MFCC features), file list; README.
- What it does: re-implements three published siren detectors: pitch periodicity, MFCC + classifier, and pyAudioAnalysis features; plots probability of siren vs time for an audio file.
- Borrow: a **"siren probability over time" strip** under the video timeline if you add audio; MFCC + small classifier is the simplest audio baseline to describe in a student paper.

## 13. Gaochengzhi/Emergency_Traffic_Simulation — SUMO EV behaviour with the bluelight device
- URL: https://github.com/Gaochengzhi/Emergency_Traffic_Simulation
- Licence: GPL-3.0 · Stars: 7 · last push 2023-03-22
- Read: code — `src/main.py`, `cfg/` files; README.
- What it does: SUMO city scenario where the EV uses SUMO's `bluelight` device (`--device.bluelight.explicit`, reaction distance 90 m), `speedMode 32` (may pass red lights), and other vehicles change lane to let it through; README notes "the traffic lights are not intelligent".
- Borrow: for SUMO experiments, a **realistic no-preemption baseline** — EVs that run reds cautiously with a rescue lane — rather than an EV that waits like a car, which would exaggerate the benefit of preemption.

## 14. CODERUDRA-X/CODERUDRAX-FlowSync-AI — "YOLOv8 + multi-agent PPO + SUMO + dashboard"
- URL: https://github.com/CODERUDRA-X/CODERUDRAX-FlowSync-AI
- Licence: MIT · Stars: 4 · last push 2026-03-21
- Read: code — the only two Python files, `yolo_detector.py`, `vehicle_counter.py`; README.
- What it does: area-based lane density from YOLO; `set_emergency_phase(lane)` gives the emergency lane green immediately.
- Honest notes: the README describes multi-agent PPO, SUMO and a Flask dashboard, but the repository holds 5 files and none of that code — claims unbacked. No clearance interval before the emergency green.
- Borrow: little; the **area-based density** (occupied fraction of a lane polygon instead of a raw count) is a reasonable density metric for the density bars.


---

## Patterns across all of them (useful for the paper's related-work paragraph)
- Almost every hobby/student repo switches the EV approach to green **immediately**, without yellow/all-red clearance (projects 2, 4, 14); only relay (1) and the GreenCorridor design (3) model clearance. MUTCD 11th ed. Sec. 4F.19 says the yellow change and red clearance shall not be shortened or omitted on entry to, during, or exit from preemption.
- Few confirm a detection over time: explicit rules found were k-consecutive-frames (3 × ≥0.70 in 3), a decaying latch (1), cooldown (2), and AND-fusion with audio plus release hysteresis (4).
- Several READMEs claim results or components that are not in the code (6, 8, 9, 14). Evaluation that **is** backed by raw output files was found in 1, 2 and 7.
- Common reported metrics: EV crossing/travel time (2, 7, 8, 9), stopped time and stops (7), queue length on side streets (8), civilian waiting time (9), priority-respected rate for multiple EVs (2).
