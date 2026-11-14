# Feature and evaluation ideas for the demo and the paper

Drawn from comparable_projects.md (cited as "Repo n") and references.md (cited as [n]). Written 2026-11-03. Each idea fits a Flask backend + HTML canvas frontend and a student paper. Anything shown from the in-app simulation must be labelled SIMULATED; detector numbers measured on real video are MEASURED.

## A. Features for the demo

1. **Two-threshold EV confirmation with a latch (avoid false activations).**
   Trigger only when an EV class has confidence ≥ τ_on in k of the last N frames (e.g., τ_on = 0.70, k = N = 3, as in the GreenCorridor design, Repo 3). Below τ_on but above τ_low show a "SUSPECTED" badge without preempting. Once confirmed, keep a decaying hold of h seconds so one missed frame does not cancel the preemption (relay uses h = 2.5 s, Repo 1), and release only after M consecutive negative checks (M = 5 in Repo 4). Show the persistence counter filling up next to the confidence gauge so viewers see *why* it fired.
   Trigger rule for the paper: preempt at the first frame t where Σ_{i=t−N+1..t} 1[c_i ≥ τ_on] ≥ k.

2. **Standards-compliant transition (yellow → all-red → EV green).**
   On confirmation, the conflicting green runs its full yellow and all-red before the EV approach turns green; the same on the way out, and never yellow → green. This is a Standard in MUTCD 11th ed. Sec. 4F.19 [7]. Most student repos skip it (Repos 2, 4, 14), so it is a concrete, citable improvement. Log each interval with its timestamp.

3. **Max-preemption cap and anti-starvation.**
   Limit how long one EV may hold green (60 s in Repo 1) so a stuck or false detection cannot freeze the junction; after the cap the controller returns to normal and logs "preempt cap reached".

4. **Multi-EV queue with a stated priority order.**
   Queue confirmed EVs by class, then arrival time: fire brigade and ambulance (heavy, harder to stop) before police (light), the order MUTCD Sec. 4F.18 gives as guidance [7]; FIFO within a class (Repo 3). If two EVs are on conflicting approaches, serve one fully, clear, then the other — never alternate (Repo 1's "sequence, never race" test). Report a "priority respected" pass/fail per scenario (Repo 2).

5. **Selectable exit (recovery) strategy.**
   After the EV clears: (a) return to the interrupted phase, (b) go to the next phase in the cycle, or (c) give the starved approaches extended greens until queues fall back. Transition/exit strategies are the subject of [1]–[4]; Obenberger & Collura compare "best-way, long, short and hold" strategies [3], and Nelson & Bullock compare "smooth, add and dwell" on a corridor [1]. In the demo this is a dropdown; in the paper it is an experiment (idea 11).

6. **Same-seed side-by-side: fixed-time vs preemption.**
   Run two copies of the intersection on identical arrivals (the counts from the video), one fixed-time and one with preemption, and show EV delay and queue lengths for both (Repo 1's compare view). Label it SIMULATED.

7. **Count → green time for normal operation, from the video's counts.**
   Fixed-time baseline from Webster's optimum cycle C₀ = (1.5L + 5)/(1 − Y) [10], where L = total lost time per cycle and Y = Σ critical flow ratios (q/s). Optional adaptive mode: green_i = clamp(⌈Σ_c n_c·t_c / (lanes+1)⌉, 10, 60) with per-class discharge times t_c (car 2 s, bus/truck 2.5 s, two-wheeler 1 s, as in Repo 5). Both are one-screen explanations faculty can follow.

8. **Realistic queue formation in the canvas: IDM car-following.**
   Move each simulated vehicle with the Intelligent Driver Model [13]:
   a = a_max·[1 − (v/v₀)^δ − (s*/s)²], with s* = s₀ + vT + vΔv / (2√(a_max·b)).
   Queues then build at red and discharge at green on their own, and the EV visibly waits behind cars under fixed-time but not under preemption. Typical parameters to state in the paper: v₀ desired speed, T ≈ 1–1.5 s headway, s₀ ≈ 2 m, δ = 4.

9. **Count each vehicle once (tracking), and confirm the *same* EV over frames.**
   Use Ultralytics' built-in tracker (`model.track(..., tracker="bytetrack.yaml")`) [15], [16] so counts are unique IDs crossing a line rather than per-frame boxes (which double-count a slow vehicle), and require the k-of-N persistence on one track ID. Repo 7 and Repo 3 both rely on tracking/distance rather than single frames.

10. **Optional siren evidence from the video's audio track.**
    If the uploaded clip has audio, compute a siren score over time (band-pass + spectrum, Repo 4; or a pretrained audio tagger, Repo 12 / YAMNet in Repo 3) and show it as a strip under the timeline. Use it only as supporting evidence (AND-fusion lowers false activations, Repo 4) — CNN siren detection [19], audio-vision fusion [20] and siren localisation [21] are the references. Keep it off by default; most traffic clips have music or no audio.

## B. Evaluation ideas for the paper

11. **Experiments that need no new data.**
    (i) Detector: precision, recall, mAP@0.5, mAP@0.5:0.95 on the held-out split, plus a **false-activation test** on non-EV traffic video (number of preemptions per hour that should not have happened) and a **missed-EV test** on EV clips — reported as a function of τ_on and k (idea 1). An independent same-class model (Repo 11) can be a reference line.
    (ii) Controller, SIMULATED: fixed-time vs preemption vs preemption with each exit strategy, over several random seeds and demand levels, reporting the metrics below with mean ± SD.
    (iii) Sensitivity: EV delay vs detection latency (confirm after k = 1…5 frames) — shows the trade-off between false activations and lost time.
    (iv) SUMO (optional): compare with a realistic no-preemption baseline where the EV uses SUMO's bluelight behaviour instead of queueing like a car (Repo 13), otherwise the benefit is overstated.

12. **A two-test benchmark like Repo 2.** Test A: one EV, random approach, N runs, normal vs preemption (EV crossing time). Test B: ambulance + fire + police arriving together, check priority order and per-class crossing time.

## C. Metric definitions used in EV-preemption studies

Define every metric once, with units, and say whether each number is MEASURED (from real video/detector) or SIMULATED.

- **EV travel time** T_EV = t_exit − t_entry over a fixed segment (e.g., from first detection line to 30 m past the stop line). Used as an EV outcome in corridor evaluation [1] and in Repos 2, 7, 8. SUMO reports it per vehicle as `duration` in its tripinfo output (SUMO TripInfo docs, https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html (read 2026-11-03)).
- **EV delay** D_EV = T_EV − T_free, where T_free = L_seg / v_free is the travel time with no signal or queue. SUMO's `timeLoss` is the same idea: "the time lost due to driving below the ideal speed" (same docs page).
- **Number of stops and stopped time** — count of times the EV speed falls below a halting threshold (SUMO counts speed ≤ 0.1 m/s: `waitingCount` = number of such episodes, `waitingTime` = time spent at ≤ 0.1 m/s, same docs page) and the total time below it; used in Repo 7.
- **System response time (detection → green)** R = t_green(EV approach) − t_confirm, split into confirmation latency t_confirm − t_first_seen (from the k-of-N rule) and transition time (yellow + all-red, fixed by [7]). Define it explicitly; it is this project's own decomposition, not a standard figure.
- **Impact on general traffic** — average delay (or time loss) per non-EV vehicle and maximum/mean queue length on the conflicting approaches during and after the EV event, versus the same seed without preemption. Corridor-level delay and travel time of other traffic are the outcomes studied in [1]–[4]; side-street queue during the EV window is used in Repo 8. Webster's formula gives the expected fixed-time delay as a sanity check [10].
- **Recovery time** T_rec = time from the end of the EV green until the controller is back on its normal cycle (or until the conflicting queues return to their pre-event length — state which). Exit/transition strategies are compared on this period in [1]–[4].
- **Detection metrics** — precision P = TP/(TP+FP), recall R = TP/(TP+FN), F1 = 2PR/(P+R), mAP@0.5 and mAP@0.5:0.95 as reported by Ultralytics validation [15]; plus **false activations per hour** and **missed EVs** at the controller level (after the persistence rule), which are what matter for the signal.
- **Priority respected** (multi-EV) — fraction of multi-EV runs where EVs were served in the stated priority order (Repo 2's `priority_respected` column).

Do not quote numeric gains from these papers in the paper unless the full text has been read; only titles/abstracts were checked here.
