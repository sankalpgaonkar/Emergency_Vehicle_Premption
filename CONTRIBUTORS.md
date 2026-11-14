# Contributors

| Who | Contribution |
|---|---|
| **Sankalp Gaonkar** | v1 (2025): original codebase and YOLOv8 emergency-vehicle detector (`runs/detect/train/`, the v1 model), SUMO Jaipur junction, PPO training script, vision scripts and dashboards. 2026: `src/extensions/` (detection engine, preemption controller, video processor, enhanced dashboard). v2 (Nov 2026): demo application, preemption state machine and simulation, retrained v2 detector, evaluation scripts and documentation (`NEW_COMPONENTS.md`). |

## Third-party work used (credit required)

* Ultralytics YOLOv8: software and COCO-pretrained weights, AGPL-3.0, https://github.com/ultralytics/ultralytics
* Roboflow Universe dataset "Emergency vehicle" (emergency-vehicle-crigt, v1) by user jd-s39ap, CC BY 4.0,
  https://universe.roboflow.com/jd-s39ap/emergency-vehicle-crigt
* Eclipse SUMO (EPL-2.0), sumo-rl (MIT), Stable-Baselines3 (MIT): v1 simulation and RL parts
* Wikimedia Commons video authors Kevin.B, Nesnad, Free Video Library, Hillelfrei and Legoktm (see `demo_app/samples/CREDITS.md`)
* Wikimedia Commons photo authors of the external test set (see `training/external_test_manifest.json`)

Note: AI-assisted tools were used to help write parts of v2. Check NMAMIT's and the publication venue's rules on
disclosing AI assistance.
