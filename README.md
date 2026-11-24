# Emergency Vehicle Preemption

Vision-based emergency vehicle detection, traffic-signal preemption, and
intersection simulation.

The project uses CCTV-style video and computer vision to detect ambulances,
fire vehicles, and police vehicles. A temporal confirmation rule reduces
false alarms before the signal controller starts a safe preemption sequence.
The web dashboard also compares preemption with a fixed-time signal plan.

> **Important:** This is a research/demo system. It must not be connected to
> live traffic signals without independent safety certification, hardware
> integration, and approval from the relevant road authority.

## Features

- Dual YOLO inference:
  - COCO vehicle detection with ByteTrack tracking
  - Custom emergency-vehicle detection for ambulance, fire brigade, and police
- Five-frame temporal confirmation before an emergency vehicle is confirmed
- Conflict-free signal controller with:
  - Yellow and all-red clearance phases
  - Emergency green hold
  - Green extension and recovery cycle
- Four-approach microscopic traffic simulation using IDM-style car following
- Side-by-side preemption and fixed-time performance metrics
- Browser dashboard built with Flask and vanilla HTML, CSS, and JavaScript
- Docker and Render deployment configuration

## How it works

```text
Video
  -> FFmpeg browser conversion
  -> COCO vehicle tracking + emergency vehicle detection
  -> Temporal confirmation
  -> Safe signal preemption controller
  -> Preemption vs fixed-time simulation
  -> Interactive dashboard
```

The default analysis configuration processes up to 15 frames per second at
640px inference size. Processing speed depends heavily on the available CPU,
RAM, and whether the service is waking from sleep.

## Screenshots

![Dashboard](docs/screenshots/03_preemption_green.png)

The dashboard shows the source video, detection overlays, signal state,
simulation results, event log, and comparative metrics.

## Requirements

- Python 3.10, 3.11, or 3.12
- macOS, Linux, or Windows
- At least 4 GB RAM recommended for local YOLO inference
- FFmpeg is installed automatically by the provided application setup

## Run locally

### macOS/Linux

```bash
git clone https://github.com/sankalpgaonkar/Emergency_Vehicle_Preemption.git
cd Emergency_Vehicle_Preemption
./run_mac.sh
```

### Windows

```bat
git clone https://github.com/sankalpgaonkar/Emergency_Vehicle_Preemption.git
cd Emergency_Vehicle_Preemption
run_windows.bat
```

Then open <http://127.0.0.1:5050>.

The launcher creates a virtual environment, installs the demo dependencies,
and starts the Flask application. To run it manually:

```bash
python -m pip install -r demo_app/requirements.txt
python demo_app/app.py --host 127.0.0.1 --port 5050
```

## Using the dashboard

1. Choose a bundled sample clip or upload a video. Sample clips start playing
   while server-side detection and simulation run.
2. Select the camera approach and initial signal state.
3. Wait for detection and simulation to finish.
4. Play the processed video and inspect the signal timeline.
5. Compare preemption with the fixed-time baseline.

Supported video formats include MP4, AVI, MOV, MKV, WEBM, M4V, MPG, MPEG,
WMV, and OGV. Uploads are limited to 300 MB and analysis is limited to the
first 180 seconds of a video by default.

## Deployment

### Render (recommended)

This repository includes `Dockerfile` and `render.yaml`.

1. Create a new **Web Service** in Render.
2. Connect this GitHub repository.
3. Select the Docker runtime, or let Render use the included `render.yaml`.
4. Deploy and open the generated service URL.

The container listens on the `PORT` environment variable and exposes
`/api/health` as its health-check endpoint.

### Other Docker platforms

The same container can run on Railway, Fly.io, Google Cloud Run, AWS ECS, or
an ordinary VM:

```bash
docker build -t emergency-vehicle-preemption .
docker run --rm -p 5050:5050 -e PORT=5050 emergency-vehicle-preemption
```

Open <http://localhost:5050>.

### Vercel

Vercel is not suitable for deploying this entire application as one service.
The backend performs CPU-heavy YOLO inference, FFmpeg conversion, and
background video jobs. Those workloads are a better fit for a long-running
Docker service.

Vercel can host a separate frontend, while the Flask API runs on Render,
Railway, Cloud Run, or another container platform.

### Production deployment notes

- Free or low-resource instances can be slow because the service may
  cold-start and CPU inference runs two models per analysed frame.
- Use a paid instance with more RAM/CPU for faster demos.
- The application writes uploads and job output to local disk. Use object
  storage such as S3, Cloudinary, or Supabase Storage if files must survive
  restarts or be shared across multiple instances.
- For a fast public demo, precompute results for the bundled sample videos
  and serve the videos through object storage or a CDN.
- Restrict upload size and duration before increasing instance resources.

## Models

| Key | File | Purpose |
| --- | --- | --- |
| `v2` | `project/models/ev_detector_v2_sankalp.pt` | Default detector |
| `v3` | `project/models/ev_detector_v3_sankalp.pt` | Detector with additional Indian-road examples |
| `v1` | `project/models/yolo_emergency_detector.pt` | Original baseline detector |
| `v2alt` | `project/models/ev_detector_v2_alt.pt` | YOLO11 comparison model |

The COCO vehicle model is stored at `demo_app/weights/yolov8n.pt`.

## Configuration

Core defaults are defined in `demo_app/core/config.py`:

- `process_fps`: 15 analysed frames per second
- `imgsz`: 640px inference size
- `MAX_UPLOAD_MB`: 300 MB
- `MAX_PROCESS_SECONDS`: 180 seconds
- Confirmation threshold: five consecutive frames at confidence `>= 0.50`
- Clearance: 3 seconds yellow followed by 2 seconds all-red

For a faster demo on CPU-only infrastructure, lower `process_fps` and
`imgsz`, understanding that this can affect detection accuracy and measured
timings.

## Project structure

```text
demo_app/
  app.py                 Flask routes and API
  core/
    config.py            Runtime parameters and model registry
    detector.py          YOLO and ByteTrack inference
    ev_confirm.py        Temporal confirmation logic
    pipeline.py          Video processing jobs
    signal_controller.py Safe preemption state machine
    simulation.py        Traffic simulation
    video_io.py          FFmpeg and video helpers
  samples/               Bundled sample videos
  static/                Dashboard frontend
  tests/                 Automated tests
project/models/          Trained emergency-vehicle weights
training/                Dataset and training utilities
docs/                    Methodology and project documentation
Dockerfile               Container image definition
render.yaml              Render service configuration
```

## Testing

Run the demo test suite with:

```bash
python -m pytest -v demo_app/tests
```

The tests cover API behavior, model loading, confirmation rules, signal
safety invariants, and simulation behavior.

## Research documentation

- [Methodology](docs/METHODOLOGY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Project review](docs/PROJECT_REVIEW.md)
- [Quick start](QUICK_START.md)
- [Sample-video credits](demo_app/samples/CREDITS.md)

## License and attribution

The project source code is licensed under the [MIT License](LICENSE).

The application depends on Ultralytics YOLO, PyTorch, OpenCV, Flask, and
other open-source packages with their own licenses. Sample videos and
training data retain the licenses and attribution described in
`demo_app/samples/CREDITS.md` and `docs/data_credits/`.

Maintained by [Sankalp Gaonkar](https://github.com/sankalpgaonkar).
