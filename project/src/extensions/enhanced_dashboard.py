"""
🚦 AI Traffic Management System - Enhanced Dashboard
=====================================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)

Unified web dashboard that adds:
  • Live webcam detection with real-time bounding boxes
  • Video upload & processing with progress tracking
  • Emergency vehicle preemption workflow display
  • All-in-one analytics dashboard

This is a SEPARATE Flask app — it does NOT modify the existing app.py.
Run it independently or alongside the original dashboard.
"""

import os
import sys
import cv2
import time
import json
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, Response, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit

# Add extensions to path
sys.path.insert(0, str(Path(__file__).parent))

from detection_engine import DetectionEngine
from preemption_controller import PreemptionController
from video_processor import VideoProcessor

# ============================================================
# App Setup
# ============================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sankalp_traffic_ai_2024'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Shared state
engine = DetectionEngine(confidence_threshold=0.45)
preemption = PreemptionController()
video_proc = None  # Initialized after engine loads

# Live camera state
live_camera = {
    'active': False,
    'camera_index': 0,
    'thread': None,
}


def init_engine():
    """Load models on startup."""
    global video_proc
    engine.load_models()
    video_proc = VideoProcessor(engine)

    def broadcast_loop():
        while True:
            try:
                st = preemption.get_status()
                socketio.emit('preemption_update', st)
            except Exception:
                pass
            time.sleep(0.2)

    threading.Thread(target=broadcast_loop, daemon=True).start()


# ============================================================
# Live Camera Detection (MJPEG stream)
# ============================================================

def generate_live_frames():
    """Generator that yields MJPEG frames from the webcam with detections."""
    cap = cv2.VideoCapture(live_camera['camera_index'])
    if not cap.isOpened():
        return

    live_camera['active'] = True
    frame_count = 0

    try:
        while live_camera['active']:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            result = engine.detect_frame(frame)
            frame_count += 1

            # Push emergency events to preemption controller
            if result['emergency_detected']:
                status = preemption.process_detections(result['emergency_vehicles'])
                socketio.emit('preemption_update', status)

            # Emit detection stats via WebSocket every 5 frames
            if frame_count % 5 == 0:
                socketio.emit('live_detection_update', {
                    'normal_count': result['normal_vehicle_count'],
                    'emergency_count': len(result['emergency_vehicles']),
                    'emergency_detected': result['emergency_detected'],
                    'processing_ms': result['processing_ms'],
                    'detections': result['detections'][:20],
                    'preemption': preemption.get_status(),
                })

            jpeg = engine.frame_to_jpeg_bytes(result['annotated_frame'], quality=75)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')

    finally:
        cap.release()
        live_camera['active'] = False


@app.route('/live/feed')
def live_feed():
    """MJPEG stream endpoint for live camera detection."""
    return Response(generate_live_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/live/start', methods=['POST'])
def start_live():
    """Start the live camera feed."""
    data = request.get_json(silent=True) or {}
    live_camera['camera_index'] = data.get('camera_index', 0)
    return jsonify({'status': 'ok', 'message': 'Live feed started'})


@app.route('/live/stop', methods=['POST'])
def stop_live():
    """Stop the live camera feed."""
    live_camera['active'] = False
    return jsonify({'status': 'ok', 'message': 'Live feed stopped'})


# ============================================================
# Video Upload & Processing
# ============================================================

@app.route('/video/upload', methods=['POST'])
def upload_video():
    """Upload a video file for processing."""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Validate
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    ok, msg = video_proc.validate_upload(file.filename, size)
    if not ok:
        return jsonify({'error': msg}), 400

    # Save & create job
    filepath = video_proc.save_upload(file, file.filename)
    job = video_proc.create_job(filepath, file.filename)

    return jsonify({'status': 'ok', 'job': job.to_dict()})


@app.route('/video/youtube/info', methods=['POST'])
def youtube_info():
    """Fetch metadata for a YouTube URL."""
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'error': 'No URL provided'}), 400

    if not video_proc.is_valid_video_url(url):
        return jsonify({'status': 'error', 'error': 'Invalid URL. Please enter a valid YouTube link.'}), 400

    info = video_proc.get_youtube_info(url)
    if info.get('status') != 'ok':
        return jsonify(info), 400
    return jsonify(info)


@app.route('/video/youtube/download', methods=['POST'])
def youtube_download():
    """Download a YouTube video and create a processing job."""
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'status': 'error', 'error': 'No URL provided'}), 400

    if not video_proc.is_valid_video_url(url):
        return jsonify({'status': 'error', 'error': 'Invalid URL. Please enter a valid YouTube link.'}), 400

    def progress_callback(progress_data):
        socketio.emit('youtube_download_progress', progress_data)

    try:
        job, res = video_proc.create_youtube_job(url, progress_callback=progress_callback)
        return jsonify({
            'status': 'ok',
            'job': job.to_dict(),
            'video_info': {
                'title': res.get('title'),
                'duration': res.get('duration'),
                'thumbnail': res.get('thumbnail')
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/video/process/<job_id>', methods=['POST'])
def process_video(job_id):
    """Start processing an uploaded video."""
    job = video_proc.jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    def on_frame(frame_b64, detections, job_info):
        socketio.emit('video_frame', {
            'frame': frame_b64,
            'detections': detections[:20],
            'job': job_info,
            'preemption': preemption.get_status(),
        })

    video_proc.start_processing(job_id, preemption, on_frame)
    return jsonify({'status': 'ok', 'message': f'Processing started for job {job_id}'})


@app.route('/video/status/<job_id>')
def video_status(job_id):
    """Get the status of a video processing job."""
    job = video_proc.jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job.to_dict())


@app.route('/video/cancel/<job_id>', methods=['POST'])
def cancel_video(job_id):
    """Cancel a running video processing job."""
    job = video_proc.jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    job.cancel()
    return jsonify({'status': 'ok', 'message': 'Job cancelled'})


@app.route('/video/jobs')
def list_jobs():
    """List all video processing jobs."""
    return jsonify([j.to_dict() for j in video_proc.jobs.values()])


# ============================================================
# Preemption API
# ============================================================

@app.route('/preemption/status')
def preemption_status():
    """Get current preemption status."""
    return jsonify(preemption.get_status())


@app.route('/preemption/log')
def preemption_log():
    """Get preemption event log."""
    return jsonify(preemption.get_event_log())


@app.route('/preemption/reset', methods=['POST'])
def preemption_reset():
    """Force reset preemption controller."""
    preemption.force_reset()
    status = preemption.get_status()
    socketio.emit('preemption_update', status)
    return jsonify({'status': 'ok', 'message': 'Preemption reset', 'preemption': status})


@app.route('/preemption/simulate', methods=['POST'])
def preemption_simulate():
    """Trigger realistic ambulance preemption sequence for demonstration."""
    data = request.get_json(silent=True) or {}
    vehicle_type = data.get('vehicle_type', 'ambulance')
    confidence = float(data.get('confidence', 0.96))
    status = preemption.simulate_emergency(vehicle_type, confidence)
    socketio.emit('preemption_update', status)
    return jsonify({'status': 'ok', 'preemption': status})


@app.route('/preemption/signals')
def preemption_signals():
    """Get detailed signal light states for visual simulation."""
    return jsonify(preemption.get_signals())


# ============================================================
# Enhanced Dashboard (single-page HTML)
# ============================================================

ENHANCED_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Traffic Management System — Sankalp Gaonkar</title>
    <meta name="description" content="AI-powered traffic management system with real-time vehicle detection, emergency preemption, and analytics by Sankalp Gaonkar">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: #1a2235;
            --bg-card-hover: #1f2a40;
            --border: #2a3550;
            --text-primary: #e8ecf4;
            --text-secondary: #8896b3;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --accent-purple: #8b5cf6;
            --accent-cyan: #06b6d4;
            --glow-blue: rgba(59, 130, 246, 0.15);
            --glow-red: rgba(239, 68, 68, 0.2);
            --radius: 12px;
            --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* ---- Header ---- */
        .header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
            border-bottom: 1px solid var(--border);
            padding: 20px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(16px);
        }

        .header-left { display: flex; align-items: center; gap: 16px; }

        .logo {
            width: 42px; height: 42px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
            box-shadow: 0 0 20px var(--glow-blue);
        }

        .header h1 {
            font-size: 1.35em;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .header .author {
            font-size: 0.8em;
            color: var(--text-secondary);
            font-weight: 400;
        }

        .header-right { display: flex; align-items: center; gap: 12px; }

        .status-badge {
            display: flex; align-items: center; gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.78em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .status-online {
            background: rgba(16, 185, 129, 0.12);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .status-dot {
            width: 7px; height: 7px;
            border-radius: 50%;
            background: var(--accent-green);
            animation: pulse-dot 2s infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
            50% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        }

        /* ---- Navigation Tabs ---- */
        .nav-tabs {
            display: flex;
            gap: 4px;
            padding: 12px 32px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
        }

        .nav-tab {
            padding: 10px 22px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.88em;
            font-weight: 500;
            color: var(--text-secondary);
            transition: var(--transition);
            border: 1px solid transparent;
            user-select: none;
        }

        .nav-tab:hover {
            color: var(--text-primary);
            background: rgba(59, 130, 246, 0.08);
        }

        .nav-tab.active {
            color: var(--accent-blue);
            background: rgba(59, 130, 246, 0.1);
            border-color: rgba(59, 130, 246, 0.3);
        }

        /* ---- Tab Content ---- */
        .tab-content { display: none; padding: 24px 32px; }
        .tab-content.active { display: block; }

        /* ---- Cards ---- */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            transition: var(--transition);
        }

        .card:hover {
            border-color: rgba(59, 130, 246, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }

        .card-title {
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }

        /* ---- Grid Layout ---- */
        .grid { display: grid; gap: 20px; }
        .grid-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
        .grid-3 { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
        .grid-4 { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }

        /* ---- Metric Cards ---- */
        .metric-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2em;
            font-weight: 700;
            line-height: 1.2;
        }

        .metric-label {
            font-size: 0.82em;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* ---- Live Feed ---- */
        .live-container {
            display: grid;
            grid-template-columns: 1fr 360px;
            gap: 20px;
        }

        @media (max-width: 900px) {
            .live-container { grid-template-columns: 1fr; }
        }

        .video-frame {
            width: 100%;
            border-radius: var(--radius);
            background: #000;
            aspect-ratio: 16/9;
            object-fit: contain;
        }

        .video-placeholder {
            display: flex;
            align-items: center;
            justify-content: center;
            aspect-ratio: 16/9;
            background: var(--bg-card);
            border: 2px dashed var(--border);
            border-radius: var(--radius);
            color: var(--text-secondary);
            font-size: 1.1em;
        }

        /* ---- Detection List ---- */
        .detection-list {
            max-height: 500px;
            overflow-y: auto;
        }

        .detection-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 6px;
            font-size: 0.85em;
            transition: var(--transition);
        }

        .detection-item:hover { background: var(--bg-card-hover); }

        .detection-item .cls-name {
            font-weight: 600;
            text-transform: capitalize;
        }

        .detection-item .conf {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
        }

        .detection-item.emergency {
            background: var(--glow-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        /* ---- Preemption Banner ---- */
        .preemption-banner {
            display: none;
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: var(--radius);
            padding: 20px 24px;
            margin-bottom: 20px;
            animation: preempt-pulse 1.5s ease-in-out infinite alternate;
        }

        .preemption-banner.active { display: block; }

        @keyframes preempt-pulse {
            0% { box-shadow: 0 0 20px rgba(239, 68, 68, 0.1); }
            100% { box-shadow: 0 0 40px rgba(239, 68, 68, 0.25); }
        }

        .preemption-banner h3 {
            color: var(--accent-red);
            font-size: 1.1em;
            margin-bottom: 8px;
        }

        .preemption-banner .countdown {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2.2em;
            font-weight: 700;
            color: var(--accent-red);
        }

        .preemption-banner .detail {
            font-size: 0.88em;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* ---- YouTube Input & Box ---- */
        .yt-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }
        .yt-card:focus-within {
            border-color: rgba(255, 59, 48, 0.45);
            box-shadow: 0 0 20px rgba(255, 59, 48, 0.15);
        }
        .yt-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }
        .yt-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.05em;
            font-weight: 600;
        }
        .yt-badge {
            background: linear-gradient(135deg, #ff0000, #cc0000);
            color: #fff;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.72em;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .yt-input-group {
            display: flex;
            gap: 10px;
        }
        .yt-input {
            flex: 1;
            padding: 12px 16px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            color: var(--text-primary);
            font-size: 0.92em;
            font-family: inherit;
            outline: none;
            transition: var(--transition);
        }
        .yt-input:focus {
            border-color: var(--accent-red);
            background: rgba(255, 255, 255, 0.08);
        }
        .yt-btn {
            background: linear-gradient(135deg, #ff3b30, #d70015);
            color: white;
            border: none;
            padding: 12px 22px;
            border-radius: 8px;
            font-size: 0.9em;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }
        .yt-btn:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(255, 59, 48, 0.4);
        }
        .yt-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .yt-preview-card {
            margin-top: 14px;
            padding: 14px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 14px;
            align-items: center;
        }
        .yt-preview-thumb {
            width: 120px;
            height: 68px;
            border-radius: 6px;
            object-fit: cover;
            background: #111;
            flex-shrink: 0;
            border: 1px solid var(--border);
        }
        .yt-preview-info {
            flex: 1;
            min-width: 0;
        }
        .yt-preview-title {
            font-weight: 600;
            font-size: 0.92em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }
        .yt-preview-meta {
            font-size: 0.78em;
            color: var(--text-secondary);
            display: flex;
            gap: 12px;
        }
        .yt-divider {
            display: flex;
            align-items: center;
            text-align: center;
            margin: 20px 0;
            color: var(--text-secondary);
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .yt-divider::before, .yt-divider::after {
            content: '';
            flex: 1;
            border-bottom: 1px solid var(--border);
        }
        .yt-divider span {
            padding: 0 12px;
        }

        /* ---- Upload Zone ---- */
        .upload-zone {
            border: 2px dashed var(--border);
            border-radius: var(--radius);
            padding: 48px;
            text-align: center;
            cursor: pointer;
            transition: var(--transition);
            position: relative;
        }

        .upload-zone:hover, .upload-zone.dragover {
            border-color: var(--accent-blue);
            background: var(--glow-blue);
        }

        .upload-zone input[type="file"] {
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            opacity: 0;
            cursor: pointer;
        }

        .upload-icon { font-size: 3em; margin-bottom: 12px; }
        .upload-text { font-size: 1.05em; font-weight: 500; }
        .upload-hint { font-size: 0.82em; color: var(--text-secondary); margin-top: 6px; }

        /* ---- Progress Bar ---- */
        .progress-bar-container {
            width: 100%;
            height: 8px;
            background: var(--bg-primary);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 12px;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        /* ---- Job Cards ---- */
        .job-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 18px;
            margin-top: 14px;
        }

        .job-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .job-name {
            font-weight: 600;
            font-size: 0.95em;
        }

        .job-status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.72em;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .job-status.processing { background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); }
        .job-status.completed { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); }
        .job-status.error { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); }
        .job-status.queued { background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); }

        /* ---- Buttons ---- */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.88em;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
        }

        .btn-primary {
            background: var(--accent-blue);
            color: white;
        }

        .btn-primary:hover {
            background: #2563eb;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
        }

        .btn-danger {
            background: var(--accent-red);
            color: white;
        }

        .btn-danger:hover {
            background: #dc2626;
        }

        .btn-outline {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-primary);
        }

        .btn-outline:hover {
            border-color: var(--accent-blue);
            background: var(--glow-blue);
        }

        /* ---- Preemption Log Table ---- */
        .log-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85em;
        }

        .log-table th {
            text-align: left;
            padding: 10px 14px;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
        }

        .log-table td {
            padding: 10px 14px;
            border-bottom: 1px solid rgba(42, 53, 80, 0.4);
        }

        /* ---- Chart Container ---- */
        .chart-wrap {
            background: var(--bg-card);
            border-radius: var(--radius);
            padding: 20px;
            border: 1px solid var(--border);
        }

        /* ---- Scrollbar ---- */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

        /* ============================================================ */
        /* Realistic Traffic Light Structures & Demonstration Stage    */
        /* ============================================================ */
        .signal-demo-container {
            background: linear-gradient(180deg, rgba(20,26,38,0.95) 0%, rgba(10,14,22,0.98) 100%);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            position: relative;
        }

        .signal-demo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .phase-stepper {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            padding: 12px 18px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.06);
            gap: 8px;
            overflow-x: auto;
        }

        .phase-step {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.78em;
            color: var(--text-secondary);
            font-weight: 500;
            padding: 6px 12px;
            border-radius: 6px;
            transition: all 0.3s ease;
            white-space: nowrap;
        }

        .phase-step.active {
            background: rgba(255,255,255,0.08);
            color: #fff;
            font-weight: 700;
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 0 15px rgba(255,255,255,0.1);
        }

        .phase-step.active.step-red {
            border-color: rgba(255, 59, 48, 0.5);
            color: #ff6961;
            box-shadow: 0 0 15px rgba(255, 59, 48, 0.25);
        }

        .phase-step.active.step-yellow {
            border-color: rgba(255, 204, 0, 0.5);
            color: #ffd60a;
            box-shadow: 0 0 15px rgba(255, 204, 0, 0.25);
        }

        .phase-step.active.step-green {
            border-color: rgba(52, 199, 89, 0.5);
            color: #30d158;
            box-shadow: 0 0 15px rgba(52, 199, 89, 0.3);
        }

        .phase-arrow {
            color: rgba(255,255,255,0.2);
            font-size: 0.85em;
        }

        .signals-stage-grid {
            display: grid;
            grid-template-columns: 1fr 1.3fr 1fr;
            gap: 24px;
            align-items: center;
        }

        @media (max-width: 1024px) {
            .signals-stage-grid {
                grid-template-columns: 1fr;
            }
        }

        .signal-column {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 20px 14px;
            border: 1px solid rgba(255,255,255,0.05);
            position: relative;
            transition: var(--transition);
        }

        .signal-column.is-priority {
            border-color: rgba(52, 199, 89, 0.5);
            box-shadow: 0 0 30px rgba(52, 199, 89, 0.18);
            background: radial-gradient(circle at top, rgba(52, 199, 89, 0.08) 0%, rgba(255,255,255,0.01) 100%);
        }

        .signal-lane-title {
            font-size: 0.94em;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-align: center;
            margin-bottom: 4px;
        }

        .signal-lane-sub {
            font-size: 0.74em;
            color: var(--text-secondary);
            margin-bottom: 16px;
            text-align: center;
        }

        .signal-post-assembly {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }

        .signal-strobe {
            width: 24px;
            height: 14px;
            background: #2a313d;
            border-radius: 6px 6px 0 0;
            border: 2px solid #111;
            margin-bottom: -2px;
            z-index: 5;
            transition: all 0.2s ease;
        }
        .signal-strobe.flashing {
            background: #00e5ff;
            box-shadow: 0 0 20px #00e5ff, 0 0 40px #00e5ff;
            animation: strobe-pulse 0.25s infinite alternate;
        }
        @keyframes strobe-pulse {
            from { opacity: 0.4; filter: brightness(1); }
            to { opacity: 1; filter: brightness(2); }
        }

        .signal-box-outer {
            position: relative;
            padding: 8px;
        }

        .signal-backplate {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: #111315;
            border: 3px solid #f5b000;
            border-radius: 24px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8);
            z-index: 1;
        }

        .signal-box {
            position: relative;
            z-index: 2;
            width: 90px;
            background: linear-gradient(180deg, #1e2229 0%, #111418 100%);
            border-radius: 18px;
            padding: 14px 10px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            border: 2px solid #2b313a;
            box-shadow: inset 0 2px 4px rgba(255,255,255,0.1);
        }

        .lamp-unit {
            position: relative;
            width: 66px;
            height: 66px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .lamp-visor {
            position: absolute;
            top: -6px;
            left: 2px;
            right: 2px;
            height: 24px;
            background: linear-gradient(180deg, #333a44 0%, #16191f 100%);
            border-radius: 30px 30px 0 0;
            border-top: 2px solid rgba(255,255,255,0.2);
            z-index: 4;
            box-shadow: 0 3px 5px rgba(0,0,0,0.6);
            pointer-events: none;
        }

        .lamp-lens {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 3px solid #0a0c0e;
            position: relative;
            z-index: 3;
            transition: all 0.3s ease;
        }

        .lens-r {
            background: radial-gradient(circle at 35% 35%, #440c0c 0%, #1a0303 100%);
            box-shadow: inset 0 2px 6px rgba(0,0,0,0.8);
        }
        .lens-r.lit {
            background: radial-gradient(circle at 40% 40%, #ff8585 0%, #ff2020 40%, #cc0000 100%);
            box-shadow: 0 0 30px #ff2b2b, 0 0 60px rgba(255, 43, 43, 0.7), inset 0 0 12px #fff;
            filter: drop-shadow(0 0 10px #ff2b2b);
            animation: glow-red 1.8s infinite ease-in-out;
        }

        .lens-y {
            background: radial-gradient(circle at 35% 35%, #3d2c08 0%, #171102 100%);
            box-shadow: inset 0 2px 6px rgba(0,0,0,0.8);
        }
        .lens-y.lit {
            background: radial-gradient(circle at 40% 40%, #fff48f 0%, #ffb300 40%, #e08500 100%);
            box-shadow: 0 0 30px #ffaa00, 0 0 60px rgba(255, 170, 0, 0.7), inset 0 0 12px #fff;
            filter: drop-shadow(0 0 10px #ffaa00);
            animation: glow-yellow 1s infinite alternate;
        }

        .lens-g {
            background: radial-gradient(circle at 35% 35%, #08331d 0%, #02140a 100%);
            box-shadow: inset 0 2px 6px rgba(0,0,0,0.8);
        }
        .lens-g.lit {
            background: radial-gradient(circle at 40% 40%, #8affd1 0%, #00e676 40%, #009944 100%);
            box-shadow: 0 0 30px #00e676, 0 0 60px rgba(0, 230, 118, 0.7), inset 0 0 12px #fff;
            filter: drop-shadow(0 0 10px #00e676);
            animation: glow-green 1.8s infinite ease-in-out;
        }

        @keyframes glow-red {
            0%, 100% { box-shadow: 0 0 25px #ff2b2b, 0 0 50px rgba(255,43,43,0.5); }
            50% { box-shadow: 0 0 35px #ff2b2b, 0 0 70px rgba(255,43,43,0.8); }
        }
        @keyframes glow-yellow {
            from { box-shadow: 0 0 25px #ffaa00, 0 0 45px rgba(255,170,0,0.5); }
            to { box-shadow: 0 0 38px #ffaa00, 0 0 70px rgba(255,170,0,0.85); }
        }
        @keyframes glow-green {
            0%, 100% { box-shadow: 0 0 25px #00e676, 0 0 50px rgba(0,230,118,0.5); }
            50% { box-shadow: 0 0 35px #00e676, 0 0 75px rgba(0,230,118,0.85); }
        }

        .signal-post-tube {
            width: 14px;
            height: 55px;
            background: linear-gradient(90deg, #2b313a 0%, #4f5866 50%, #1e2229 100%);
            box-shadow: 0 4px 10px rgba(0,0,0,0.6);
        }
        .signal-post-mount {
            width: 50px;
            height: 10px;
            background: #2b313a;
            border-radius: 4px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .signal-state-badge {
            margin-top: 14px;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.82em;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-align: center;
            border: 1px solid transparent;
        }
        .badge-red {
            background: rgba(255, 59, 48, 0.15);
            color: #ff453a;
            border-color: rgba(255, 59, 48, 0.4);
        }
        .badge-yellow {
            background: rgba(255, 204, 0, 0.15);
            color: #ffd60a;
            border-color: rgba(255, 204, 0, 0.4);
        }
        .badge-green {
            background: rgba(52, 199, 89, 0.15);
            color: #30d158;
            border-color: rgba(52, 199, 89, 0.4);
        }

        .intersection-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }

        .intersection-canvas-wrap {
            position: relative;
            width: 100%;
            max-width: 330px;
            height: 330px;
            border-radius: 14px;
            overflow: hidden;
            border: 2px solid rgba(255,255,255,0.1);
            box-shadow: inset 0 0 25px rgba(0,0,0,0.8), 0 10px 30px rgba(0,0,0,0.5);
            background: #11151c;
        }

        #intersection-canvas {
            width: 100%;
            height: 100%;
            display: block;
        }

        .phase-description-card {
            margin-top: 14px;
            width: 100%;
            padding: 12px 16px;
            border-radius: 10px;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            text-align: center;
        }

        .demo-controls-bar {
            display: flex;
            justify-content: center;
            gap: 14px;
            margin-top: 20px;
            flex-wrap: wrap;
        }

        .btn-simulate-em {
            background: linear-gradient(135deg, #ff3b30 0%, #b80000 100%);
            color: #fff;
            font-weight: 700;
            padding: 12px 24px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(255, 59, 48, 0.4);
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.95em;
        }
        .btn-simulate-em:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(255, 59, 48, 0.6);
        }

        /* ================= 4-LANE SIMULATION IN VIDEO TAB ================= */
        .sim4-container {
            margin-top: 24px;
            background: linear-gradient(180deg, rgba(16, 21, 31, 0.96) 0%, rgba(9, 12, 19, 0.99) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: 0 20px 45px rgba(0,0,0,0.6);
            position: relative;
            overflow: hidden;
        }

        .sim4-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }

        .sim4-title {
            font-size: 1.3em;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 0;
            color: #fff;
        }

        .sim4-subtitle {
            font-size: 0.84em;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .sim4-badges-row {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .sim4-stat-badge {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85em;
            display: flex;
            align-items: center;
            gap: 6px;
            color: #cbd5e1;
        }

        .sim4-stat-badge strong {
            color: #fff;
            font-size: 1.1em;
        }

        .sim4-stat-badge.alert {
            background: rgba(255, 59, 48, 0.15);
            border-color: rgba(255, 59, 48, 0.5);
            color: #ff6b6b;
            animation: pulse-border 1.5s infinite;
        }

        .sim4-status-pill {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 700;
            letter-spacing: 0.5px;
            border: 1px solid;
            transition: all 0.3s ease;
        }

        .sim4-pill-normal {
            background: rgba(48, 209, 88, 0.15);
            border-color: rgba(48, 209, 88, 0.4);
            color: #30d158;
        }

        .sim4-pill-preempt {
            background: rgba(255, 59, 48, 0.2);
            border-color: #ff3b30;
            color: #ff453a;
            box-shadow: 0 0 15px rgba(255, 59, 48, 0.4);
            animation: pulse-border 0.8s infinite alternate;
        }

        .sim4-alert-banner {
            margin-top: 16px;
            background: linear-gradient(90deg, rgba(255, 59, 48, 0.25) 0%, rgba(184, 0, 0, 0.25) 100%);
            border: 1.5px solid #ff3b30;
            border-radius: 10px;
            padding: 12px 18px;
            display: flex;
            align-items: center;
            gap: 14px;
            box-shadow: 0 0 25px rgba(255, 59, 48, 0.3);
            animation: fadeIn 0.3s ease;
        }

        .sim4-alert-icon {
            font-size: 1.8em;
            animation: strobe-pulse 0.4s infinite alternate;
        }

        .sim4-alert-heading {
            font-size: 0.9em;
            font-weight: 800;
            color: #ff453a;
            letter-spacing: 0.5px;
        }

        .sim4-alert-text {
            font-size: 0.82em;
            color: #e2e8f0;
            margin-top: 2px;
        }

        .sim4-alert-pulse {
            margin-left: auto;
            background: #ff3b30;
            color: #fff;
            font-weight: 800;
            font-size: 0.72em;
            padding: 4px 10px;
            border-radius: 4px;
            letter-spacing: 0.8px;
            white-space: nowrap;
        }

        .sim4-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 16px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .sim4-toggle-label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.84em;
            color: var(--text-secondary);
            cursor: pointer;
            user-select: none;
        }

        .sim4-toggle-label input {
            cursor: pointer;
            accent-color: var(--accent-blue);
        }

        .sim4-btn-group {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .sim4-btn {
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.8em;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid rgba(255,255,255,0.12);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .sim4-btn-em {
            background: linear-gradient(135deg, #ff3b30 0%, #b80000 100%);
            color: #fff;
            border: none;
            box-shadow: 0 2px 10px rgba(255, 59, 48, 0.4);
        }

        .sim4-btn-em:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(255, 59, 48, 0.6);
        }

        .sim4-btn-sec {
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-secondary);
        }

        .sim4-btn-sec:hover {
            background: rgba(255, 255, 255, 0.12);
            color: #fff;
        }

        /* 4-Lane Stage Grid */
        .sim4-lanes-stage {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-top: 12px;
        }

        @media (max-width: 900px) {
            .sim4-lanes-stage {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        .sim4-lane-col {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            padding: 14px 10px 10px 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }

        .sim4-emergency-col {
            border-color: rgba(255, 59, 48, 0.35);
            background: linear-gradient(180deg, rgba(255, 59, 48, 0.04) 0%, rgba(0,0,0,0) 100%);
        }

        .sim4-emergency-col.preempted {
            border-color: rgba(48, 209, 88, 0.6);
            box-shadow: 0 0 25px rgba(48, 209, 88, 0.25);
        }

        .sim4-lane-head {
            text-align: center;
            width: 100%;
            margin-bottom: 12px;
        }

        .sim4-lane-badge {
            font-size: 0.72em;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.08);
            color: #cbd5e1;
            display: inline-block;
            letter-spacing: 0.5px;
        }

        .sim4-lane-badge.em-badge {
            background: rgba(255, 59, 48, 0.2);
            color: #ff6b6b;
            border: 1px solid rgba(255, 59, 48, 0.4);
        }

        .sim4-lane-name {
            font-size: 0.85em;
            font-weight: 600;
            color: #fff;
            margin-top: 4px;
        }

        .sim4-lane-state {
            font-size: 0.74em;
            font-weight: 700;
            margin-top: 4px;
            padding: 2px 8px;
            border-radius: 10px;
            display: inline-block;
            transition: all 0.25s ease;
        }

        .sim4-state-green {
            background: rgba(48, 209, 88, 0.15);
            color: #30d158;
            border: 1px solid rgba(48, 209, 88, 0.4);
        }

        .sim4-state-yellow {
            background: rgba(255, 204, 0, 0.15);
            color: #ffd60a;
            border: 1px solid rgba(255, 204, 0, 0.4);
        }

        .sim4-state-red {
            background: rgba(255, 59, 48, 0.15);
            color: #ff453a;
            border: 1px solid rgba(255, 59, 48, 0.4);
        }

        /* Signal Post Assembly */
        .sim4-signal-assembly {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 12px;
            position: relative;
        }

        .sim4-strobe {
            width: 16px;
            height: 9px;
            background: #2a313d;
            border-radius: 4px 4px 0 0;
            border: 1.5px solid #111;
            margin-bottom: -2px;
            z-index: 3;
            transition: all 0.2s ease;
        }

        .sim4-strobe.flashing {
            background: #00e5ff;
            box-shadow: 0 0 16px #00e5ff, 0 0 30px #00e5ff;
            animation: strobe-pulse 0.25s infinite alternate;
        }

        .sim4-signal-box {
            width: 44px;
            background: linear-gradient(180deg, #1c212b 0%, #10131a 100%);
            border: 2px solid #2d3442;
            border-radius: 10px;
            padding: 8px 6px;
            display: flex;
            flex-direction: column;
            gap: 7px;
            align-items: center;
            box-shadow: 0 6px 16px rgba(0,0,0,0.7), inset 0 1px 2px rgba(255,255,255,0.1);
            position: relative;
        }

        .sim4-lamp {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #141720;
            border: 1px solid #232834;
            opacity: 0.35;
            transition: all 0.2s ease;
            position: relative;
        }

        .sim4-lamp::after {
            content: '';
            position: absolute;
            top: -4px;
            left: 2px;
            right: 2px;
            height: 5px;
            background: #181d26;
            border-radius: 4px 4px 0 0;
            border: 1px solid #29303d;
            border-bottom: none;
        }

        .sim4-lamp-red.lit {
            background: radial-gradient(circle at 35% 35%, #ff8080, #ff1a1a 60%, #990000 100%);
            border-color: #ff3b30;
            opacity: 1;
            box-shadow: 0 0 14px #ff2b2b, 0 0 28px rgba(255, 43, 43, 0.65);
        }

        .sim4-lamp-yellow.lit {
            background: radial-gradient(circle at 35% 35%, #fff080, #ffcc00 60%, #997a00 100%);
            border-color: #ffd60a;
            opacity: 1;
            box-shadow: 0 0 14px #ffcc00, 0 0 28px rgba(255, 204, 0, 0.65);
        }

        .sim4-lamp-green.lit {
            background: radial-gradient(circle at 35% 35%, #80ff9f, #00e64d 60%, #00802b 100%);
            border-color: #30d158;
            opacity: 1;
            box-shadow: 0 0 16px #00e64d, 0 0 35px rgba(0, 230, 77, 0.7);
        }

        /* Road Track */
        .sim4-road-track {
            width: 100%;
            height: 340px;
            background: #141821;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.7);
        }

        .sim4-road-track.em-track {
            background: linear-gradient(180deg, #161b26 0%, #11151f 100%);
            border-color: rgba(255, 59, 48, 0.25);
        }

        /* Dashed Lane Divider */
        .sim4-road-track::before {
            content: '';
            position: absolute;
            top: 0; bottom: 0;
            left: 50%;
            width: 2px;
            transform: translateX(-50%);
            background-image: repeating-linear-gradient(to bottom, transparent, transparent 12px, #f59e0b 12px, #f59e0b 26px);
            opacity: 0.35;
        }

        /* Zebra Pedestrian Crossing */
        .sim4-zebra {
            position: absolute;
            top: 8px;
            left: 6px;
            right: 6px;
            height: 22px;
            background-image: repeating-linear-gradient(to right, #ffffff, #ffffff 8px, transparent 8px, transparent 16px);
            opacity: 0.35;
        }

        /* Stop Line */
        .sim4-stop-line {
            position: absolute;
            top: 36px;
            left: 0;
            right: 0;
            height: 4px;
            background: #ffffff;
            box-shadow: 0 0 8px rgba(255,255,255,0.7);
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .sim4-stop-line span {
            position: absolute;
            top: 6px;
            font-size: 0.58em;
            font-weight: 800;
            color: rgba(255, 255, 255, 0.4);
            letter-spacing: 1px;
        }

        .sim4-lane-arrow {
            position: absolute;
            top: 55px;
            width: 100%;
            text-align: center;
            color: rgba(255, 255, 255, 0.25);
            font-size: 1.1em;
            pointer-events: none;
        }

        .sim4-lane-marker-text {
            position: absolute;
            bottom: 8px;
            width: 100%;
            text-align: center;
            font-size: 0.62em;
            font-weight: 700;
            letter-spacing: 0.8px;
            color: rgba(255, 255, 255, 0.2);
            text-transform: uppercase;
        }

        /* Vehicle Slot and Positioning */
        .sim4-vehicles-slot {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
        }

        .sim4-veh {
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            transition: all 0.8s cubic-bezier(0.25, 1, 0.5, 1);
        }

        /* Stopped at Red */
        .sim4-veh.stopped-pos-1 { top: 52px; }
        .sim4-veh.stopped-pos-2 { top: 142px; }
        .sim4-veh.stopped-pos-3 { top: 232px; }

        /* Moving through Green */
        .sim4-veh.cruising {
            animation: car-drive 3.5s infinite linear;
        }

        @keyframes car-drive {
            0% { top: 340px; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: -90px; opacity: 0; }
        }

        /* Ambulance Specific Animation */
        .sim4-amb-rushing {
            animation: amb-rush 2.4s infinite linear;
        }

        @keyframes amb-rush {
            0% { top: 340px; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: -90px; opacity: 0; }
        }

        /* Ambulance Strobe and Siren Animations */
        .sim4-strobe-blue {
            animation: flash-blue 0.22s infinite alternate;
        }

        .sim4-strobe-red {
            animation: flash-red 0.22s infinite alternate 0.11s;
        }

        @keyframes flash-blue {
            from { fill: #1d4ed8; filter: drop-shadow(0 0 2px #3b82f6); }
            to { fill: #60a5fa; filter: drop-shadow(0 0 10px #38bdf8); }
        }

        @keyframes flash-red {
            from { fill: #b91c1c; filter: drop-shadow(0 0 2px #ef4444); }
            to { fill: #f87171; filter: drop-shadow(0 0 10px #f43f5e); }
        }

        .sim4-siren-ring {
            position: absolute;
            top: 50%; left: 50%;
            width: 20px; height: 20px;
            border-radius: 50%;
            border: 2px solid rgba(255, 59, 48, 0.8);
            transform: translate(-50%, -50%);
            animation: siren-expand 1.2s infinite ease-out;
            pointer-events: none;
        }

        @keyframes siren-expand {
            0% { width: 10px; height: 10px; opacity: 1; border-color: rgba(255, 59, 48, 0.9); }
            50% { border-color: rgba(0, 229, 255, 0.8); }
            100% { width: 90px; height: 90px; opacity: 0; border-color: rgba(255, 59, 48, 0); }
        }


        /* ---- Footer ---- */
        .footer {
            text-align: center;
            padding: 24px;
            color: var(--text-secondary);
            font-size: 0.82em;
            border-top: 1px solid var(--border);
            margin-top: 40px;
        }

        .footer a { color: var(--accent-blue); text-decoration: none; }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="header-left">
            <div class="logo">🚦</div>
            <div>
                <h1>AI Traffic Management System</h1>
                <span class="author">Developed by Sankalp Gaonkar</span>
            </div>
        </div>
        <div class="header-right">
            <div id="conn-status" class="status-badge status-online">
                <span class="status-dot"></span>
                <span id="conn-text">Connected</span>
            </div>
        </div>
    </div>

    <!-- Navigation -->
    <div class="nav-tabs">
        <div class="nav-tab active" data-tab="overview">📊 Overview</div>
        <div class="nav-tab" data-tab="live">📷 Live Detection</div>
        <div class="nav-tab" data-tab="upload">📹 Video & YouTube</div>
        <div class="nav-tab" data-tab="preemption">🚨 Emergency Preemption</div>
    </div>

    <!-- ================= OVERVIEW TAB ================= -->
    <div id="tab-overview" class="tab-content active">
        <div id="preemption-banner" class="preemption-banner">
            <div style="display:flex;align-items:center;gap:20px;">
                <div>
                    <h3>🚨 EMERGENCY PREEMPTION ACTIVE</h3>
                    <div class="detail" id="preempt-detail">Ambulance detected — signal forced green</div>
                </div>
                <div class="countdown" id="preempt-countdown">15s</div>
            </div>
        </div>

        <div class="grid grid-4" style="margin-bottom:24px;">
            <div class="card">
                <div class="card-title">Total Vehicles Detected</div>
                <div class="metric-value" id="stat-total-vehicles" style="color:var(--accent-blue)">0</div>
                <div class="metric-label">since session start</div>
            </div>
            <div class="card">
                <div class="card-title">Emergency Vehicles</div>
                <div class="metric-value" id="stat-emergency" style="color:var(--accent-red)">0</div>
                <div class="metric-label">total detections</div>
            </div>
            <div class="card">
                <div class="card-title">Preemptions Triggered</div>
                <div class="metric-value" id="stat-preemptions" style="color:var(--accent-amber)">0</div>
                <div class="metric-label">signal overrides</div>
            </div>
            <div class="card">
                <div class="card-title">Processing Speed</div>
                <div class="metric-value" id="stat-fps" style="color:var(--accent-green)">—</div>
                <div class="metric-label">ms per frame</div>
            </div>
        </div>

        <div class="grid grid-2">
            <div class="chart-wrap">
                <div class="card-title">Detection Timeline</div>
                <canvas id="timeline-chart" height="200"></canvas>
            </div>
            <div class="card">
                <div class="card-title">Recent Detections</div>
                <div class="detection-list" id="overview-detections">
                    <div style="color:var(--text-secondary);text-align:center;padding:40px;">
                        Start a live feed or upload a video to see detections
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- ================= LIVE DETECTION TAB ================= -->
    <div id="tab-live" class="tab-content">
        <div style="display:flex;gap:12px;margin-bottom:20px;">
            <button class="btn btn-primary" id="btn-start-live" onclick="startLive()">▶ Start Live Detection</button>
            <button class="btn btn-danger" id="btn-stop-live" onclick="stopLive()" style="display:none">⏹ Stop</button>
            <select id="camera-select" style="background:var(--bg-card);color:var(--text-primary);border:1px solid var(--border);border-radius:8px;padding:8px 14px;font-family:inherit;">
                <option value="0">Camera 0 (Default)</option>
                <option value="1">Camera 1</option>
                <option value="2">Camera 2</option>
            </select>
        </div>

        <div class="live-container">
            <div>
                <div id="live-placeholder" class="video-placeholder">
                    <div>Click "Start Live Detection" to begin</div>
                </div>
                <img id="live-video" class="video-frame" src="" style="display:none" alt="Live detection feed">
            </div>
            <div class="card">
                <div class="card-title">Live Detections</div>
                <div class="detection-list" id="live-detections"></div>
            </div>
        </div>
    </div>

    <!-- ================= VIDEO & YOUTUBE TAB ================= -->
    <div id="tab-upload" class="tab-content">
        <div class="grid grid-2">
            <div>
                <!-- YouTube Link Input Card -->
                <div class="yt-card">
                    <div class="yt-header">
                        <div class="yt-title">
                            <span class="yt-badge">YouTube</span>
                            <span>Paste YouTube Video Link</span>
                        </div>
                        <span style="font-size:0.75em;color:var(--text-secondary);">Traffic feed / Clip</span>
                    </div>
                    <div style="font-size:0.84em;color:var(--text-secondary);margin-bottom:12px;">
                        Paste any YouTube traffic camera, intersection, or emergency vehicle video URL to analyze.
                    </div>
                    <div class="yt-input-group">
                        <input type="text" id="youtube-url-input" class="yt-input"
                               placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
                               onkeydown="if(event.key==='Enter') handleYouTubeFetch()">
                        <button class="yt-btn" id="btn-fetch-youtube" onclick="handleYouTubeFetch()">
                            <span>▶</span> Get Video
                        </button>
                    </div>

                    <!-- YouTube Live Status / Preview -->
                    <div id="yt-status-area" style="display:none;margin-top:14px;">
                        <div class="yt-preview-card" id="yt-preview-card">
                            <img id="yt-thumb-img" class="yt-preview-thumb" src="" alt="Thumbnail">
                            <div class="yt-preview-info">
                                <div class="yt-preview-title" id="yt-video-title">Loading title...</div>
                                <div class="yt-preview-meta" id="yt-video-meta">
                                    <span id="yt-video-channel">Channel</span> &middot;
                                    <span id="yt-video-duration">0:00</span>
                                </div>
                                <div id="yt-status-text" style="font-size:0.82em;color:var(--accent-blue);margin-top:6px;">
                                    ⏳ Downloading video...
                                </div>
                            </div>
                        </div>
                        <div class="progress-bar-container" id="yt-progress-container" style="display:none;margin-top:10px;">
                            <div class="progress-bar-fill" id="yt-progress-fill" style="width:0%;background:linear-gradient(90deg, #ff3b30, #ff9500);"></div>
                        </div>
                    </div>
                </div>

                <div class="yt-divider"><span>OR UPLOAD LOCAL FILE</span></div>

                <div class="upload-zone" id="upload-zone">
                    <input type="file" id="video-input" accept="video/*" onchange="handleUpload(this)">
                    <div class="upload-icon">📁</div>
                    <div class="upload-text">Drop a video here or click to browse</div>
                    <div class="upload-hint">Supports MP4, AVI, MOV, MKV, WebM — up to 500 MB</div>
                </div>

                <div id="jobs-list"></div>
            </div>
            <div>
                <div class="card">
                    <div class="card-title">Processing Preview</div>
                    <img id="upload-preview" class="video-frame" src="" style="display:none" alt="Processing preview">
                    <div id="upload-placeholder" class="video-placeholder" style="aspect-ratio:16/9;">
                        Paste a YouTube link or upload a video to see real-time detection results
                    </div>
                </div>
                <div class="card" style="margin-top:16px;">
                    <div class="card-title">Video Detections</div>
                    <div class="detection-list" id="upload-detections"></div>
                </div>
            </div>
        </div>

        <!-- ================= 4-LANE TRAFFIC SIGNAL & VEHICLE SIMULATION ================= -->
        <div class="sim4-container" id="sim4-container">
            <div class="sim4-header">
                <div>
                    <h2 class="sim4-title">
                        <span>🚦</span> 4-Lane Real-Time Traffic Signal & Vehicle Simulation
                    </h2>
                    <div class="sim4-subtitle">
                        Simulating 4 independent approach lanes with active preemption. Vehicle counts dynamically mirrored from video detections.
                    </div>
                </div>
                <div class="sim4-badges-row">
                    <div class="sim4-stat-badge">
                        <span>🚗 Normal Cars: <strong id="sim4-cars-count">0</strong></span>
                    </div>
                    <div class="sim4-stat-badge" id="sim4-amb-badge">
                        <span>🚑 Ambulance: <strong id="sim4-amb-count">0</strong></span>
                    </div>
                    <div class="sim4-status-pill sim4-pill-normal" id="sim4-master-status">
                        🟢 NORMAL FLOW
                    </div>
                </div>
            </div>

            <!-- Emergency Priority Banner (Appears when Ambulance detected) -->
            <div class="sim4-alert-banner" id="sim4-alert-banner" style="display:none;">
                <div class="sim4-alert-icon">🚨</div>
                <div class="sim4-alert-content">
                    <div class="sim4-alert-heading">EMERGENCY VEHICLE DETECTED IN VIDEO FRAME</div>
                    <div class="sim4-alert-text">
                        <b>Lane 1 Preemption Active:</b> Forced <b>GREEN</b> signal corridor for priority clearance. 
                        <b>Lanes 2, 3, and 4</b> are locked on <b>RED</b> to stop all cross traffic safely.
                    </div>
                </div>
                <div class="sim4-alert-pulse">PRIORITY CLEARANCE</div>
            </div>

            <!-- Controls bar -->
            <div class="sim4-toolbar">
                <div class="sim4-toggle-group">
                    <label class="sim4-toggle-label">
                        <input type="checkbox" id="sim4-auto-sync" checked onchange="fourLaneSim.toggleAutoSync(this.checked)">
                        <span>⚡ Auto-Sync with Video Stream Detections</span>
                    </label>
                </div>
                <div class="sim4-btn-group">
                    <button class="sim4-btn sim4-btn-em" onclick="fourLaneSim.manualTriggerAmbulance()">
                        <span>🚨</span> Test Ambulance Preemption
                    </button>
                    <button class="sim4-btn sim4-btn-sec" onclick="fourLaneSim.addCar()">
                        <span>➕</span> Add Car
                    </button>
                    <button class="sim4-btn sim4-btn-sec" onclick="fourLaneSim.removeCar()">
                        <span>➖</span> Remove Car
                    </button>
                    <button class="sim4-btn sim4-btn-sec" onclick="fourLaneSim.resetNormal()">
                        <span>🔄</span> Reset Normal Cycle
                    </button>
                </div>
            </div>

            <!-- 4-Lane Simulation Stage -->
            <div class="sim4-lanes-stage">

                <!-- LANE 1: EMERGENCY CORRIDOR -->
                <div class="sim4-lane-col sim4-emergency-col" id="sim4-col-1">
                    <div class="sim4-lane-head">
                        <div class="sim4-lane-badge em-badge">🚑 LANE 1</div>
                        <div class="sim4-lane-name">Emergency Corridor</div>
                        <div class="sim4-lane-state sim4-state-green" id="sim4-light-badge-1">GREEN (CLEAR)</div>
                    </div>

                    <!-- Signal Post 1 -->
                    <div class="sim4-signal-assembly">
                        <div class="sim4-strobe" id="sim4-strobe-1" title="Optical Emergency Preemption Sensor"></div>
                        <div class="sim4-signal-box">
                            <div class="sim4-lamp sim4-lamp-red" id="sim4-lamp-1-red"></div>
                            <div class="sim4-lamp sim4-lamp-yellow" id="sim4-lamp-1-yellow"></div>
                            <div class="sim4-lamp sim4-lamp-green lit" id="sim4-lamp-1-green"></div>
                        </div>
                    </div>

                    <!-- Road Lane 1 -->
                    <div class="sim4-road-track em-track">
                        <div class="sim4-zebra"></div>
                        <div class="sim4-stop-line"><span>STOP LINE</span></div>
                        <div class="sim4-lane-arrow">▲</div>
                        <div class="sim4-lane-marker-text">AMBULANCE ROUTE</div>
                        <div class="sim4-vehicles-slot" id="sim4-slot-1"></div>
                    </div>
                </div>

                <!-- LANE 2: SOUTH LANE -->
                <div class="sim4-lane-col" id="sim4-col-2">
                    <div class="sim4-lane-head">
                        <div class="sim4-lane-badge">🚗 LANE 2</div>
                        <div class="sim4-lane-name">Southbound Traffic</div>
                        <div class="sim4-lane-state sim4-state-red" id="sim4-light-badge-2">RED (STOP)</div>
                    </div>

                    <!-- Signal Post 2 -->
                    <div class="sim4-signal-assembly">
                        <div class="sim4-signal-box">
                            <div class="sim4-lamp sim4-lamp-red lit" id="sim4-lamp-2-red"></div>
                            <div class="sim4-lamp sim4-lamp-yellow" id="sim4-lamp-2-yellow"></div>
                            <div class="sim4-lamp sim4-lamp-green" id="sim4-lamp-2-green"></div>
                        </div>
                    </div>

                    <!-- Road Lane 2 -->
                    <div class="sim4-road-track">
                        <div class="sim4-zebra"></div>
                        <div class="sim4-stop-line"><span>STOP LINE</span></div>
                        <div class="sim4-lane-arrow">▲</div>
                        <div class="sim4-lane-marker-text">LANE 2</div>
                        <div class="sim4-vehicles-slot" id="sim4-slot-2"></div>
                    </div>
                </div>

                <!-- LANE 3: EAST LANE -->
                <div class="sim4-lane-col" id="sim4-col-3">
                    <div class="sim4-lane-head">
                        <div class="sim4-lane-badge">🚗 LANE 3</div>
                        <div class="sim4-lane-name">Eastbound Traffic</div>
                        <div class="sim4-lane-state sim4-state-red" id="sim4-light-badge-3">RED (STOP)</div>
                    </div>

                    <!-- Signal Post 3 -->
                    <div class="sim4-signal-assembly">
                        <div class="sim4-signal-box">
                            <div class="sim4-lamp sim4-lamp-red lit" id="sim4-lamp-3-red"></div>
                            <div class="sim4-lamp sim4-lamp-yellow" id="sim4-lamp-3-yellow"></div>
                            <div class="sim4-lamp sim4-lamp-green" id="sim4-lamp-3-green"></div>
                        </div>
                    </div>

                    <!-- Road Lane 3 -->
                    <div class="sim4-road-track">
                        <div class="sim4-zebra"></div>
                        <div class="sim4-stop-line"><span>STOP LINE</span></div>
                        <div class="sim4-lane-arrow">▲</div>
                        <div class="sim4-lane-marker-text">LANE 3</div>
                        <div class="sim4-vehicles-slot" id="sim4-slot-3"></div>
                    </div>
                </div>

                <!-- LANE 4: WEST LANE -->
                <div class="sim4-lane-col" id="sim4-col-4">
                    <div class="sim4-lane-head">
                        <div class="sim4-lane-badge">🚗 LANE 4</div>
                        <div class="sim4-lane-name">Westbound Traffic</div>
                        <div class="sim4-lane-state sim4-state-red" id="sim4-light-badge-4">RED (STOP)</div>
                    </div>

                    <!-- Signal Post 4 -->
                    <div class="sim4-signal-assembly">
                        <div class="sim4-signal-box">
                            <div class="sim4-lamp sim4-lamp-red lit" id="sim4-lamp-4-red"></div>
                            <div class="sim4-lamp sim4-lamp-yellow" id="sim4-lamp-4-yellow"></div>
                            <div class="sim4-lamp sim4-lamp-green" id="sim4-lamp-4-green"></div>
                        </div>
                    </div>

                    <!-- Road Lane 4 -->
                    <div class="sim4-road-track">
                        <div class="sim4-zebra"></div>
                        <div class="sim4-stop-line"><span>STOP LINE</span></div>
                        <div class="sim4-lane-arrow">▲</div>
                        <div class="sim4-lane-marker-text">LANE 4</div>
                        <div class="sim4-vehicles-slot" id="sim4-slot-4"></div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <!-- ================= PREEMPTION TAB ================= -->
    <div id="tab-preemption" class="tab-content">

        <!-- ================= REALISTIC TRAFFIC SIGNAL DEMONSTRATION STAGE ================= -->
        <div class="signal-demo-container">
            <div class="signal-demo-header">
                <div>
                    <h2 style="font-size:1.35em;font-weight:700;display:flex;align-items:center;gap:10px;">
                        <span>🚦</span> Realistic Traffic Signal Preemption Structure
                    </h2>
                    <div style="font-size:0.84em;color:var(--text-secondary);margin-top:4px;">
                        Automated clearance: Cross lanes safely slow to Yellow ➔ All-Red safety interval ➔ Ambulance forced Green ➔ Vice-Versa Recovery
                    </div>
                </div>
                <div style="display:flex;gap:10px;align-items:center;">
                    <button class="btn btn-simulate-em" onclick="triggerSimulatedAmbulance()">
                        <span>🚨</span> Simulate Ambulance Arrival
                    </button>
                    <button class="btn btn-outline" onclick="resetPreemption()">
                        🔄 Reset Normal Flow
                    </button>
                </div>
            </div>

            <!-- 5-Phase Progressive Stepper -->
            <div class="phase-stepper">
                <div class="phase-step active step-green" id="step-1">
                    <span>1️⃣</span> Normal Flow (Cross Green)
                </div>
                <div class="phase-arrow">➔</div>
                <div class="phase-step" id="step-2">
                    <span>2️⃣</span> 🟡 Cross Slowing to Yellow
                </div>
                <div class="phase-arrow">➔</div>
                <div class="phase-step" id="step-3">
                    <span>3️⃣</span> 🔴 All-Red Intersection Clear
                </div>
                <div class="phase-arrow">➔</div>
                <div class="phase-step" id="step-4">
                    <span>4️⃣</span> 🟢 Ambulance Corridor Forced Green
                </div>
                <div class="phase-arrow">➔</div>
                <div class="phase-step" id="step-5">
                    <span>5️⃣</span> 🔄 Vice-Versa Return to Normal
                </div>
            </div>

            <!-- 3-Column Visual Stage -->
            <div class="signals-stage-grid">

                <!-- Left Column: Emergency Ambulance Corridor -->
                <div class="signal-column" id="em-col">
                    <div class="signal-lane-title" style="color:var(--accent-red)">🚑 EMERGENCY CORRIDOR</div>
                    <div class="signal-lane-sub">North-South Preemption Lane</div>

                    <div class="signal-post-assembly">
                        <div class="signal-strobe" id="em-strobe" title="Optical Preemption Sensor Receiver"></div>
                        <div class="signal-box-outer">
                            <div class="signal-backplate"></div>
                            <div class="signal-box">
                                <div class="lamp-unit">
                                    <div class="lamp-visor"></div>
                                    <div class="lamp-lens lens-r lit" id="em-light-red"></div>
                                </div>
                                <div class="lamp-unit">
                                    <div class="lamp-visor"></div>
                                    <div class="lamp-lens lens-y" id="em-light-yellow"></div>
                                </div>
                                <div class="lamp-unit">
                                    <div class="lamp-visor"></div>
                                    <div class="lamp-lens lens-g" id="em-light-green"></div>
                                </div>
                            </div>
                        </div>
                        <div class="signal-post-tube"></div>
                        <div class="signal-post-mount"></div>
                    </div>

                    <div class="signal-state-badge badge-red" id="em-badge">RED — HOLDING</div>
                </div>

                <!-- Middle Column: 2D Animated Intersection & Phase Status -->
                <div class="intersection-box">
                    <div class="intersection-canvas-wrap">
                        <canvas id="intersection-canvas" width="330" height="330"></canvas>
                    </div>

                    <div class="phase-description-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <span id="phase-badge-title" style="font-weight:700;font-size:0.9em;color:var(--accent-blue)">
                                STANDARD SIGNAL CYCLE
                            </span>
                            <span id="phase-timer-display" style="font-family:'JetBrains Mono',monospace;font-weight:700;font-size:1.1em;color:var(--accent-amber)">
                                —
                            </span>
                        </div>
                        <div id="phase-detail-desc" style="font-size:0.8em;color:var(--text-secondary);line-height:1.4;">
                            Cross traffic is flowing smoothly on green. Emergency corridor is waiting at red.
                        </div>
                    </div>
                </div>

                <!-- Right Column: Cross Traffic Conflicting Lanes -->
                <div class="signal-column" id="cr-col">
                    <div class="signal-lane-title" style="color:var(--accent-blue)">🚗 CROSS TRAFFIC LANES</div>
                    <div class="signal-lane-sub">East-West Standard Arterial</div>

                    <div class="signal-post-assembly">
                        <div class="signal-strobe" style="opacity:0.3;"></div>
                        <div class="signal-box-outer">
                            <div class="signal-backplate"></div>
                            <div class="signal-box">
                                <div class="lamp-unit">
                                    <div class="lamp-visor"></div>
                                    <div class="lamp-lens lens-r" id="cr-light-red"></div>
                                </div>
                                <div class="lamp-unit">
                                    <div class="lamp-visor"></div>
                                    <div class="lamp-lens lens-y" id="cr-light-yellow"></div>
                                </div>
                                <div class="lamp-unit">
                                    <div class="lamp-visor"></div>
                                    <div class="lamp-lens lens-g lit" id="cr-light-green"></div>
                                </div>
                            </div>
                        </div>
                        <div class="signal-post-tube"></div>
                        <div class="signal-post-mount"></div>
                    </div>

                    <div class="signal-state-badge badge-green" id="cr-badge">GREEN — FLOWING</div>
                </div>

            </div>
        </div>

        <div class="grid grid-3" style="margin-bottom:24px;">
            <div class="card">
                <div class="card-title">Preemption Controller State</div>
                <div class="metric-value" id="pre-state" style="color:var(--accent-green)">IDLE</div>
                <div class="metric-label">controller state machine</div>
            </div>
            <div class="card">
                <div class="card-title">Signal Directive</div>
                <div class="metric-value" id="pre-signal" style="color:var(--accent-blue);font-size:1.25em;">NORMAL OPERATION</div>
                <div class="metric-label">NEMA TS-2 action</div>
            </div>
            <div class="card">
                <div class="card-title">Phase Remaining</div>
                <div class="metric-value" id="pre-remaining" style="color:var(--accent-amber)">—</div>
                <div class="metric-label">transition timer</div>
            </div>
        </div>

        <div class="card" style="margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <div class="card-title" style="margin-bottom:0;">Preemption Audit Trail Log</div>
                <button class="btn btn-outline" onclick="resetPreemption()">🔄 Reset Log &amp; Controller</button>
            </div>
            <table class="log-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Vehicle Type</th>
                        <th>Confidence</th>
                        <th>Triggered At</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody id="preemption-log-body">
                    <tr><td colspan="5" style="text-align:center;color:var(--text-secondary);">No preemption events yet</td></tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <div class="card-title">Safe Preemption Transition Protocol (Demonstration Guide)</div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;text-align:center;">
                <div style="padding:16px;">
                    <div style="font-size:2em;margin-bottom:8px;">🚑</div>
                    <div style="font-weight:600;margin-bottom:4px;">1. Optical Detection</div>
                    <div style="font-size:0.8em;color:var(--text-secondary);">Ambulance detected via camera / video with high confidence</div>
                </div>
                <div style="padding:16px;">
                    <div style="font-size:2em;margin-bottom:8px;">🟡</div>
                    <div style="font-weight:600;margin-bottom:4px;">2. Clearance Yellow</div>
                    <div style="font-size:0.8em;color:var(--text-secondary);">Cross traffic gently transitions to yellow (3.5s) to avoid collisions</div>
                </div>
                <div style="padding:16px;">
                    <div style="font-size:2em;margin-bottom:8px;">🔴</div>
                    <div style="font-weight:600;margin-bottom:4px;">3. All-Red Clearance</div>
                    <div style="font-size:0.8em;color:var(--text-secondary);">All signals hold red (1.5s) ensuring intersection is 100% empty</div>
                </div>
                <div style="padding:16px;">
                    <div style="font-size:2em;margin-bottom:8px;">🟢</div>
                    <div style="font-weight:600;margin-bottom:4px;">4. Green Corridor &amp; Recovery</div>
                    <div style="font-size:0.8em;color:var(--text-secondary);">Ambulance forced green, then transitions vice-versa back to normal</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <div class="footer">
        AI Traffic Management System v2.0 — Designed &amp; developed by
        <a href="https://github.com/sankalpgaonkar" target="_blank">Sankalp Gaonkar</a>
        &middot; Powered by YOLOv8 &amp; PPO Reinforcement Learning
    </div>

    <script>
        // ============ Socket.IO ============
        const socket = io();
        let stats = { vehicles: 0, emergency: 0, preemptions: 0, fps: 0 };

        socket.on('connect', () => {
            document.getElementById('conn-text').textContent = 'Connected';
            document.getElementById('conn-status').className = 'status-badge status-online';
        });

        socket.on('disconnect', () => {
            document.getElementById('conn-text').textContent = 'Disconnected';
            document.getElementById('conn-status').style.borderColor = 'rgba(239,68,68,0.3)';
            document.getElementById('conn-status').style.color = 'var(--accent-red)';
        });

        // ============ Tab Navigation ============
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
            });
        });

        // ============ Chart ============
        const ctx = document.getElementById('timeline-chart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Vehicles',
                        data: [],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59,130,246,0.08)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        borderWidth: 2,
                    },
                    {
                        label: 'Emergency',
                        data: [],
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239,68,68,0.08)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        borderWidth: 2,
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: {
                        labels: { color: '#8896b3', font: { family: 'Inter' } }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#8896b3', maxTicksLimit: 10 },
                        grid: { color: 'rgba(42,53,80,0.3)' }
                    },
                    y: {
                        ticks: { color: '#8896b3' },
                        grid: { color: 'rgba(42,53,80,0.3)' }
                    }
                }
            }
        });

        function pushChartData(normal, emergency) {
            const now = new Date().toLocaleTimeString();
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(normal);
            chart.data.datasets[1].data.push(emergency);
            if (chart.data.labels.length > 50) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
                chart.data.datasets[1].data.shift();
            }
            chart.update('none');
        }

        // ============ Live Detection Events ============
        socket.on('live_detection_update', (data) => {
            stats.vehicles += data.normal_count;
            stats.emergency += data.emergency_count;
            stats.fps = data.processing_ms;
            updateStats();
            pushChartData(data.normal_count, data.emergency_count);
            updateDetectionList('live-detections', data.detections);
            updateDetectionList('overview-detections', data.detections);
            if (data.preemption) updatePreemption(data.preemption);
        });

        // ============ Video Processing Events ============
        socket.on('video_frame', (data) => {
            const preview = document.getElementById('upload-preview');
            const placeholder = document.getElementById('upload-placeholder');
            preview.src = 'data:image/jpeg;base64,' + data.frame;
            preview.style.display = 'block';
            placeholder.style.display = 'none';

            if (data.detections) {
                stats.vehicles += data.detections.filter(d => !d.is_emergency).length;
                stats.emergency += data.detections.filter(d => d.is_emergency).length;
                updateStats();
                updateDetectionList('upload-detections', data.detections);
                pushChartData(
                    data.detections.filter(d => !d.is_emergency).length,
                    data.detections.filter(d => d.is_emergency).length
                );

                // Synchronize 4-Lane Real-Time Traffic Simulation
                if (window.fourLaneSim) {
                    window.fourLaneSim.handleVideoDetections(data.detections);
                }
            }

            if (data.job) updateJobCard(data.job);
            if (data.preemption) updatePreemption(data.preemption);
        });

        // ============ Preemption Events & Traffic Light Controller ============
        let currentSignalState = {
            phase: 'NORMAL',
            em_state: 'RED',
            cr_state: 'GREEN'
        };

        socket.on('preemption_update', (data) => {
            updatePreemption(data);
        });

        function setLens(id, lit) {
            const el = document.getElementById(id);
            if (!el) return;
            if (lit) el.classList.add('lit');
            else el.classList.remove('lit');
        }

        function setBadge(id, cls, text) {
            const el = document.getElementById(id);
            if (!el) return;
            el.className = 'signal-state-badge ' + cls;
            el.textContent = text;
        }

        function updateStepper(phase) {
            const steps = [
                { id: 'step-1', phases: ['NORMAL'] },
                { id: 'step-2', phases: ['CLEARING_CROSS_YELLOW'] },
                { id: 'step-3', phases: ['ALL_RED_CLEARANCE'] },
                { id: 'step-4', phases: ['EMERGENCY_GREEN'] },
                { id: 'step-5', phases: ['CLEARING_EMERGENCY_YELLOW', 'RECOVERY_ALL_RED'] }
            ];

            steps.forEach(s => {
                const el = document.getElementById(s.id);
                if (!el) return;
                el.classList.remove('active', 'step-red', 'step-yellow', 'step-green');
                if (s.phases.includes(phase)) {
                    el.classList.add('active');
                    if (phase === 'NORMAL' || phase === 'EMERGENCY_GREEN') el.classList.add('step-green');
                    else if (phase === 'CLEARING_CROSS_YELLOW' || phase === 'CLEARING_EMERGENCY_YELLOW') el.classList.add('step-yellow');
                    else el.classList.add('step-red');
                }
            });
        }

        function updatePreemption(p) {
            if (!p) return;
            stats.preemptions = p.total_preemptions || 0;
            const preStatEl = document.getElementById('stat-preemptions');
            if (preStatEl) preStatEl.textContent = p.total_preemptions || 0;

            const banner = document.getElementById('preemption-banner');
            if (banner) {
                if (p.is_preempting) {
                    banner.classList.add('active');
                    const remSec = (p.remaining_seconds || 0).toFixed(0);
                    document.getElementById('preempt-countdown').textContent = remSec + 's';
                    if (p.active_event) {
                        document.getElementById('preempt-detail').textContent =
                            p.active_event.vehicle_type.toUpperCase() + ' detected — ' + (p.signal_action || '').replace(/_/g, ' ');
                    }
                } else {
                    banner.classList.remove('active');
                }
            }

            // Metrics
            const preStateEl = document.getElementById('pre-state');
            if (preStateEl) {
                preStateEl.textContent = p.state || 'IDLE';
                preStateEl.style.color =
                    p.state === 'ACTIVE' ? 'var(--accent-red)' :
                    p.state === 'TRIGGERED' ? 'var(--accent-amber)' :
                    p.state === 'COOLDOWN' ? 'var(--accent-purple)' : 'var(--accent-green)';
            }

            const preSigEl = document.getElementById('pre-signal');
            if (preSigEl) preSigEl.textContent = (p.signal_action || 'NORMAL').replace(/_/g, ' ');

            const preRemEl = document.getElementById('pre-remaining');
            if (preRemEl) {
                preRemEl.textContent = p.remaining_seconds > 0 ? p.remaining_seconds.toFixed(1) + 's' : '—';
            }

            // ---- Traffic Signal Light Structures ----
            const sig = p.signals || {};
            const em = sig.emergency_lane || {};
            const cr = sig.cross_lane || {};

            currentSignalState.phase = sig.phase || 'NORMAL';
            currentSignalState.em_state = em.state || 'RED';
            currentSignalState.cr_state = cr.state || 'GREEN';

            // Emergency Corridor Lenses
            setLens('em-light-red', em.red !== undefined ? em.red : true);
            setLens('em-light-yellow', em.yellow !== undefined ? em.yellow : false);
            setLens('em-light-green', em.green !== undefined ? em.green : false);

            // Cross Traffic Lenses
            setLens('cr-light-red', cr.red !== undefined ? cr.red : false);
            setLens('cr-light-yellow', cr.yellow !== undefined ? cr.yellow : false);
            setLens('cr-light-green', cr.green !== undefined ? cr.green : true);

            // Optical Sensor Strobe
            const strobe = document.getElementById('em-strobe');
            if (strobe) {
                if (sig.optical_strobe) strobe.classList.add('flashing');
                else strobe.classList.remove('flashing');
            }

            // Badges
            setBadge('em-badge',
                em.green ? 'badge-green' : (em.yellow ? 'badge-yellow' : 'badge-red'),
                em.green ? '🟢 GREEN — PRIORITY FORCED' : (em.yellow ? '🟡 YELLOW — CLEARING' : '🔴 RED — HOLDING'));

            setBadge('cr-badge',
                cr.green ? 'badge-green' : (cr.yellow ? 'badge-yellow' : 'badge-red'),
                cr.green ? '🟢 GREEN — FLOWING' : (cr.yellow ? '🟡 YELLOW — CAUTION SLOWING' : '🔴 RED — LOCKED STOP'));

            // Column highlights
            const emCol = document.getElementById('em-col');
            if (emCol) {
                if (em.green) emCol.classList.add('is-priority');
                else emCol.classList.remove('is-priority');
            }

            // Stepper
            updateStepper(sig.phase || 'NORMAL');

            // Phase description & countdown
            const pTitle = document.getElementById('phase-badge-title');
            if (pTitle) pTitle.textContent = (sig.phase || 'NORMAL').replace(/_/g, ' ');

            const pTimer = document.getElementById('phase-timer-display');
            if (pTimer) pTimer.textContent = sig.phase_remaining > 0 ? sig.phase_remaining.toFixed(1) + 's' : '—';

            const pDesc = document.getElementById('phase-detail-desc');
            if (pDesc) pDesc.textContent = sig.phase_description || 'Standard signal cycle in operation.';
        }

        function triggerSimulatedAmbulance() {
            fetch('/preemption/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vehicle_type: 'ambulance', confidence: 0.98 })
            })
            .then(r => r.json())
            .then(data => {
                if (data.preemption) updatePreemption(data.preemption);
            });
        }

        // ============ 2D Intersection Simulation Canvas ============
        let cvs = null, cctx = null;
        let simCars = [
            { x: 30, y: 148, speed: 1.8, color: '#3b82f6', dir: 1 },
            { x: 95, y: 148, speed: 1.6, color: '#eab308', dir: 1 },
            { x: 295, y: 174, speed: 1.9, color: '#a855f7', dir: -1 },
            { x: 230, y: 174, speed: 1.7, color: '#ec4899', dir: -1 }
        ];
        let simAmbulance = { x: 150, y: 310, speed: 1.2, sirenAngle: 0 };

        function initIntersectionCanvas() {
            cvs = document.getElementById('intersection-canvas');
            if (!cvs) return;
            cctx = cvs.getContext('2d');
            requestAnimationFrame(drawIntersectionLoop);
        }

        function drawIntersectionLoop(time) {
            if (!cctx || !cvs) {
                requestAnimationFrame(drawIntersectionLoop);
                return;
            }

            const w = cvs.width, h = cvs.height;
            cctx.clearRect(0, 0, w, h);

            // Ground terrain
            cctx.fillStyle = '#0f141d';
            cctx.fillRect(0, 0, w, h);

            // Road asphalt
            const rw = 80;
            const rx = (w - rw) / 2;
            const ry = (h - rw) / 2;

            // Highlight emergency corridor if green
            if (currentSignalState.em_state === 'GREEN') {
                cctx.fillStyle = 'rgba(52, 199, 89, 0.08)';
                cctx.fillRect(rx - 8, 0, rw + 16, h);
            }

            cctx.fillStyle = '#1c222b';
            cctx.fillRect(rx, 0, rw, h); // North-South
            cctx.fillRect(0, ry, w, rw); // East-West

            // Intersection center box
            cctx.fillStyle = '#191e26';
            cctx.fillRect(rx, ry, rw, rw);

            // Road Markings (yellow dashed center line)
            cctx.strokeStyle = '#eab308';
            cctx.lineWidth = 2;
            cctx.setLineDash([8, 6]);

            // NS center line
            cctx.beginPath();
            cctx.moveTo(w / 2, 0); cctx.lineTo(w / 2, ry);
            cctx.moveTo(w / 2, ry + rw); cctx.lineTo(w / 2, h);
            cctx.stroke();

            // EW center line
            cctx.beginPath();
            cctx.moveTo(0, h / 2); cctx.lineTo(rx, h / 2);
            cctx.moveTo(rx + rw, h / 2); cctx.lineTo(w, h / 2);
            cctx.stroke();

            cctx.setLineDash([]); // Reset dash

            // Stop Lines (white)
            cctx.strokeStyle = '#ffffff';
            cctx.lineWidth = 3;

            // South stop line
            cctx.beginPath();
            cctx.moveTo(rx, ry + rw); cctx.lineTo(rx + rw / 2, ry + rw);
            cctx.stroke();

            // North stop line
            cctx.beginPath();
            cctx.moveTo(rx + rw / 2, ry); cctx.lineTo(rx + rw, ry);
            cctx.stroke();

            // West stop line
            cctx.beginPath();
            cctx.moveTo(rx, ry); cctx.lineTo(rx, ry + rw / 2);
            cctx.stroke();

            // East stop line
            cctx.beginPath();
            cctx.moveTo(rx + rw, ry + rw / 2); cctx.lineTo(rx + rw, ry + rw);
            cctx.stroke();

            // Zebra crosswalks
            cctx.fillStyle = 'rgba(255,255,255,0.2)';
            for (let i = 0; i < 4; i++) {
                // North crosswalk
                cctx.fillRect(rx + 6 + i * 18, ry - 14, 10, 10);
                // South crosswalk
                cctx.fillRect(rx + 6 + i * 18, ry + rw + 4, 10, 10);
                // West crosswalk
                cctx.fillRect(rx - 14, ry + 6 + i * 18, 10, 10);
                // East crosswalk
                cctx.fillRect(rx + rw + 4, ry + 6 + i * 18, 10, 10);
            }

            // Signal indicators on corners
            // North-South signal dot
            cctx.fillStyle = currentSignalState.em_state === 'GREEN' ? '#00e676' : (currentSignalState.em_state === 'YELLOW' ? '#ffaa00' : '#ff3b30');
            cctx.shadowColor = cctx.fillStyle;
            cctx.shadowBlur = 8;
            cctx.beginPath();
            cctx.arc(rx - 10, ry + rw + 8, 5, 0, Math.PI * 2);
            cctx.fill();

            // East-West signal dot
            cctx.fillStyle = currentSignalState.cr_state === 'GREEN' ? '#00e676' : (currentSignalState.cr_state === 'YELLOW' ? '#ffaa00' : '#ff3b30');
            cctx.shadowColor = cctx.fillStyle;
            cctx.beginPath();
            cctx.arc(rx - 8, ry - 10, 5, 0, Math.PI * 2);
            cctx.fill();
            cctx.shadowBlur = 0; // Reset shadow

            // Update & Draw Cross Traffic Cars
            simCars.forEach((car) => {
                const stopX = car.dir === 1 ? rx - 18 : rx + rw + 18;
                let canGo = (currentSignalState.cr_state === 'GREEN');

                if (currentSignalState.cr_state === 'YELLOW') {
                    // If close to intersection, go, else slow down
                    const dist = Math.abs(car.x - stopX);
                    canGo = (car.dir === 1 && car.x > stopX - 25) || (car.dir === -1 && car.x < stopX + 25);
                }

                if (!canGo) {
                    if (car.dir === 1 && car.x < stopX && car.x + car.speed >= stopX) {
                        car.x = stopX;
                    } else if (car.dir === -1 && car.x > stopX && car.x - car.speed <= stopX) {
                        car.x = stopX;
                    } else if ((car.dir === 1 && car.x < stopX) || (car.dir === -1 && car.x > stopX)) {
                        car.x += car.speed * car.dir;
                    } else {
                        // Already past intersection, keep moving
                        car.x += car.speed * car.dir;
                    }
                } else {
                    car.x += car.speed * car.dir;
                }

                // Loop around canvas
                if (car.dir === 1 && car.x > w + 20) car.x = -20;
                if (car.dir === -1 && car.x < -20) car.x = w + 20;

                // Draw Car body
                cctx.fillStyle = car.color;
                cctx.beginPath();
                cctx.roundRect(car.x - 12, car.y - 7, 24, 14, 4);
                cctx.fill();

                // Windshield
                cctx.fillStyle = '#0a0d14';
                cctx.fillRect(car.dir === 1 ? car.x + 2 : car.x - 7, car.y - 5, 5, 10);
            });

            // Update & Draw Ambulance
            const emStopY = ry + rw + 22;
            const isEmGreen = (currentSignalState.em_state === 'GREEN');

            if (isEmGreen) {
                // High speed through intersection
                simAmbulance.speed = 3.2;
                simAmbulance.y -= simAmbulance.speed;
                if (simAmbulance.y < -35) {
                    simAmbulance.y = h + 20;
                }
            } else {
                // Stop at line if red/yellow
                simAmbulance.speed = 1.4;
                if (simAmbulance.y > emStopY) {
                    simAmbulance.y -= simAmbulance.speed;
                    if (simAmbulance.y < emStopY) simAmbulance.y = emStopY;
                } else if (simAmbulance.y < emStopY - 40) {
                    // If already past, keep exiting
                    simAmbulance.y -= 2.0;
                    if (simAmbulance.y < -35) simAmbulance.y = h + 20;
                }
            }

            // Draw Ambulance
            const ax = simAmbulance.x + 8;
            const ay = simAmbulance.y;

            // Ambulance shadow
            cctx.fillStyle = 'rgba(0,0,0,0.5)';
            cctx.fillRect(ax - 10, ay - 16, 20, 36);

            // Ambulance body (White)
            cctx.fillStyle = '#f8fafc';
            cctx.beginPath();
            cctx.roundRect(ax - 9, ay - 17, 18, 34, 4);
            cctx.fill();

            // Red Emergency Stripe
            cctx.fillStyle = '#ef4444';
            cctx.fillRect(ax - 9, ay - 3, 18, 5);

            // Front windshield
            cctx.fillStyle = '#0f172a';
            cctx.fillRect(ax - 7, ay - 14, 14, 6);

            // Red Cross on roof
            cctx.fillStyle = '#ef4444';
            cctx.fillRect(ax - 1, ay + 6, 2, 8);
            cctx.fillRect(ax - 4, ay + 9, 8, 2);

            // Flashing Emergency Strobe Beacon on roof
            const flash = Math.sin(time / 80) > 0;
            cctx.fillStyle = flash ? '#ff2b2b' : '#3b82f6';
            cctx.shadowColor = cctx.fillStyle;
            cctx.shadowBlur = isEmGreen || currentSignalState.phase !== 'NORMAL' ? 16 : 4;
            cctx.beginPath();
            cctx.arc(ax, ay - 2, 4, 0, Math.PI * 2);
            cctx.fill();
            cctx.shadowBlur = 0;

            requestAnimationFrame(drawIntersectionLoop);
        }

        window.addEventListener('DOMContentLoaded', () => {
            initIntersectionCanvas();
        });
        setTimeout(initIntersectionCanvas, 500);

        // ============ Update Functions ============
        function updateStats() {
            document.getElementById('stat-total-vehicles').textContent = stats.vehicles.toLocaleString();
            document.getElementById('stat-emergency').textContent = stats.emergency;
            document.getElementById('stat-preemptions').textContent = stats.preemptions;
            document.getElementById('stat-fps').textContent = stats.fps + 'ms';
        }

        function updateDetectionList(elementId, detections) {
            const el = document.getElementById(elementId);
            if (!detections || detections.length === 0) return;

            el.innerHTML = detections.slice(0, 15).map(d => {
                const cls = d.is_emergency ? 'detection-item emergency' : 'detection-item';
                const icon = d.is_emergency ? '🚨' : '🚗';
                const confColor = d.confidence > 0.7 ? 'var(--accent-green)' :
                                  d.confidence > 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)';
                return `<div class="${cls}">
                    <span>${icon} <span class="cls-name">${d.class}</span></span>
                    <span class="conf" style="color:${confColor}">${(d.confidence * 100).toFixed(0)}%</span>
                </div>`;
            }).join('');
        }

        // ============ Live Camera Controls ============
        function startLive() {
            const cam = document.getElementById('camera-select').value;
            fetch('/live/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({camera_index: parseInt(cam)})
            }).then(() => {
                document.getElementById('live-video').src = '/live/feed';
                document.getElementById('live-video').style.display = 'block';
                document.getElementById('live-placeholder').style.display = 'none';
                document.getElementById('btn-start-live').style.display = 'none';
                document.getElementById('btn-stop-live').style.display = 'inline-flex';
            });
        }

        function stopLive() {
            fetch('/live/stop', {method: 'POST'}).then(() => {
                document.getElementById('live-video').style.display = 'none';
                document.getElementById('live-placeholder').style.display = 'flex';
                document.getElementById('btn-start-live').style.display = 'inline-flex';
                document.getElementById('btn-stop-live').style.display = 'none';
            });
        }

        // ============ YouTube Integration ============
        function formatDuration(seconds) {
            if (!seconds || seconds <= 0) return 'Live / Unknown';
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return `${m}:${s < 10 ? '0' : ''}${s}`;
        }

        async function handleYouTubeFetch() {
            const input = document.getElementById('youtube-url-input');
            const url = (input.value || '').trim();
            if (!url) {
                alert('Please enter a YouTube link first.');
                input.focus();
                return;
            }

            const btn = document.getElementById('btn-fetch-youtube');
            const statusArea = document.getElementById('yt-status-area');
            const thumbImg = document.getElementById('yt-thumb-img');
            const titleEl = document.getElementById('yt-video-title');
            const channelEl = document.getElementById('yt-video-channel');
            const durationEl = document.getElementById('yt-video-duration');
            const statusText = document.getElementById('yt-status-text');
            const progressContainer = document.getElementById('yt-progress-container');
            const progressFill = document.getElementById('yt-progress-fill');

            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> Fetching...';
            statusArea.style.display = 'block';
            progressContainer.style.display = 'block';
            progressFill.style.width = '15%';
            statusText.textContent = '🔍 Fetching video details from YouTube...';
            statusText.style.color = 'var(--accent-blue)';
            titleEl.textContent = 'Connecting to YouTube...';
            thumbImg.src = '';

            try {
                // Step 1: Get metadata fast
                const infoRes = await fetch('/video/youtube/info', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const infoData = await infoRes.json();

                if (infoData.status !== 'ok' || infoData.error) {
                    throw new Error(infoData.error || 'Failed to retrieve YouTube video details');
                }

                // Show metadata preview
                titleEl.textContent = infoData.title || 'YouTube Video';
                channelEl.textContent = infoData.channel || 'YouTube';
                durationEl.textContent = formatDuration(infoData.duration);
                if (infoData.thumbnail) {
                    thumbImg.src = infoData.thumbnail;
                }

                statusText.textContent = '📥 Downloading video stream (720p/MP4)...';
                progressFill.style.width = '40%';

                // Step 2: Download and create job
                const dlRes = await fetch('/video/youtube/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const dlData = await dlRes.json();

                if (dlData.status !== 'ok' || dlData.error) {
                    throw new Error(dlData.error || 'Failed to download YouTube video');
                }

                progressFill.style.width = '100%';
                statusText.textContent = '✅ Video ready! Starting detection and preemption analysis...';
                statusText.style.color = 'var(--accent-green)';

                // Add to job list and auto-start processing
                addJobCard(dlData.job);
                fetch('/video/process/' + dlData.job.id, { method: 'POST' });

                // Scroll to preview smoothly
                document.getElementById('upload-preview').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

            } catch (err) {
                statusText.textContent = '❌ Error: ' + err.message;
                statusText.style.color = 'var(--accent-red)';
                progressFill.style.width = '0%';
                alert('YouTube error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>▶</span> Get Video';
            }
        }

        // Listen for download progress updates from server
        socket.on('youtube_download_progress', function(data) {
            const progressFill = document.getElementById('yt-progress-fill');
            const statusText = document.getElementById('yt-status-text');
            if (progressFill && data && data.percent) {
                progressFill.style.width = Math.max(20, data.percent) + '%';
                if (statusText) {
                    const speedMb = data.speed ? (data.speed / 1024 / 1024).toFixed(1) : 0;
                    statusText.textContent = `📥 Downloading YouTube stream: ${data.percent}% (${speedMb} MB/s)`;
                }
            }
        });

        // ============ Video Upload ============
        const uploadZone = document.getElementById('upload-zone');
        uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', e => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) doUpload(e.dataTransfer.files[0]);
        });

        function handleUpload(input) {
            if (input.files.length) doUpload(input.files[0]);
        }

        function doUpload(file) {
            const formData = new FormData();
            formData.append('video', file);

            fetch('/video/upload', { method: 'POST', body: formData })
                .then(r => r.json())
                .then(data => {
                    if (data.error) { alert(data.error); return; }
                    addJobCard(data.job);
                    // Auto-start processing
                    fetch('/video/process/' + data.job.id, { method: 'POST' });
                })
                .catch(err => alert('Upload failed: ' + err));
        }

        function addJobCard(job) {
            const container = document.getElementById('jobs-list');
            const card = document.createElement('div');
            card.className = 'job-card';
            card.id = 'job-' + job.id;
            card.innerHTML = buildJobHTML(job);
            container.prepend(card);
        }

        function updateJobCard(job) {
            let card = document.getElementById('job-' + job.id);
            if (!card) { addJobCard(job); return; }
            card.innerHTML = buildJobHTML(job);
        }

        function buildJobHTML(job) {
            return `
                <div class="job-header">
                    <span class="job-name">📹 ${job.original_name}</span>
                    <span class="job-status ${job.status}">${job.status}</span>
                </div>
                <div style="font-size:0.82em;color:var(--text-secondary);margin-bottom:8px;">
                    Frames: ${job.processed_frames}/${job.total_frames} &middot;
                    Vehicles: ${job.total_vehicles} &middot;
                    Emergency: ${job.total_emergency} &middot;
                    FPS: ${job.fps_avg.toFixed(1)}
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar-fill" style="width:${job.progress}%"></div>
                </div>
                ${job.status === 'processing' ?
                    `<button class="btn btn-danger" style="margin-top:10px;padding:6px 14px;font-size:0.8em;"
                        onclick="cancelJob('${job.id}')">Cancel</button>` : ''}
            `;
        }

        function cancelJob(jobId) {
            fetch('/video/cancel/' + jobId, { method: 'POST' });
        }

        // ============ Preemption Controls ============
        function resetPreemption() {
            fetch('/preemption/reset', { method: 'POST' });
        }

        // Poll preemption log periodically
        setInterval(() => {
            fetch('/preemption/log')
                .then(r => r.json())
                .then(events => {
                    if (events.length === 0) return;
                    const tbody = document.getElementById('preemption-log-body');
                    tbody.innerHTML = events.reverse().map(e => `
                        <tr>
                            <td>#${e.id || '?'}</td>
                            <td style="text-transform:capitalize">${e.vehicle_type || '—'}</td>
                            <td>${e.confidence ? (e.confidence * 100).toFixed(0) + '%' : '—'}</td>
                            <td>${e.triggered_at ? new Date(e.triggered_at).toLocaleTimeString() : '—'}</td>
                            <td>${e.duration ? e.duration + 's' : '—'}</td>
                        </tr>
                    `).join('');
                })
                .catch(() => {});
        }, 3000);

        // ============================================================
        // 4-LANE TRAFFIC SIGNAL & VEHICLE SIMULATION CONTROLLER
        // ============================================================
        class FourLaneSimulation {
            constructor() {
                this.autoSync = true;
                this.carCount = 2;
                this.ambulanceCount = 0;
                this.isPreempted = false;
                this.carColors = ['#2563eb', '#0284c7', '#7c3aed', '#059669', '#d97706', '#dc2626'];
                this.preemptionTimeout = null;
                this.cycleInterval = null;
                this.normalCycleIndex = 0;

                this.init();
            }

            init() {
                this.updateSignals('NORMAL');
                this.renderVehicles();
                this.startNormalCycle();
            }

            toggleAutoSync(checked) {
                this.autoSync = checked;
                const statusEl = document.getElementById('sim4-master-status');
                if (!checked) {
                    statusEl.textContent = '⏸ MANUAL CONTROL';
                    statusEl.className = 'sim4-status-pill sim4-pill-normal';
                } else {
                    this.updateMasterStatus();
                }
            }

            handleVideoDetections(detections) {
                if (!this.autoSync) return;

                const normalDets = detections.filter(d => !d.is_emergency);
                const emDets = detections.filter(d => d.is_emergency);

                this.carCount = normalDets.length;
                this.ambulanceCount = emDets.length;

                document.getElementById('sim4-cars-count').textContent = this.carCount;
                document.getElementById('sim4-amb-count').textContent = this.ambulanceCount;

                const ambBadge = document.getElementById('sim4-amb-badge');
                if (this.ambulanceCount > 0) {
                    ambBadge.classList.add('alert');
                    this.triggerPreemption();
                } else {
                    ambBadge.classList.remove('alert');
                    if (this.isPreempted) {
                        this.releasePreemption();
                    }
                }

                this.renderVehicles();
            }

            triggerPreemption() {
                this.isPreempted = true;
                clearInterval(this.cycleInterval);
                this.updateSignals('PREEMPTION');
                this.updateMasterStatus();

                const banner = document.getElementById('sim4-alert-banner');
                if (banner) banner.style.display = 'flex';

                const col1 = document.getElementById('sim4-col-1');
                if (col1) col1.classList.add('preempted');

                const strobe = document.getElementById('sim4-strobe-1');
                if (strobe) strobe.classList.add('flashing');
            }

            releasePreemption() {
                this.isPreempted = false;
                const banner = document.getElementById('sim4-alert-banner');
                if (banner) banner.style.display = 'none';

                const col1 = document.getElementById('sim4-col-1');
                if (col1) col1.classList.remove('preempted');

                const strobe = document.getElementById('sim4-strobe-1');
                if (strobe) strobe.classList.remove('flashing');

                this.updateSignals('NORMAL');
                this.updateMasterStatus();
                this.startNormalCycle();
            }

            manualTriggerAmbulance() {
                this.ambulanceCount = 1;
                document.getElementById('sim4-amb-count').textContent = this.ambulanceCount;
                document.getElementById('sim4-amb-badge').classList.add('alert');
                this.triggerPreemption();
                this.renderVehicles();

                // Auto-revert after 8 seconds if manual
                clearTimeout(this.preemptionTimeout);
                this.preemptionTimeout = setTimeout(() => {
                    this.resetNormal();
                }, 8000);
            }

            addCar() {
                this.carCount = Math.min(12, this.carCount + 1);
                document.getElementById('sim4-cars-count').textContent = this.carCount;
                this.renderVehicles();
            }

            removeCar() {
                this.carCount = Math.max(0, this.carCount - 1);
                document.getElementById('sim4-cars-count').textContent = this.carCount;
                this.renderVehicles();
            }

            resetNormal() {
                this.ambulanceCount = 0;
                document.getElementById('sim4-amb-count').textContent = '0';
                document.getElementById('sim4-amb-badge').classList.remove('alert');
                this.releasePreemption();
                this.renderVehicles();
            }

            updateMasterStatus() {
                const el = document.getElementById('sim4-master-status');
                if (!el) return;
                if (this.isPreempted) {
                    el.textContent = '🚨 LANE 1 PREEMPTED (GREEN)';
                    el.className = 'sim4-status-pill sim4-pill-preempt';
                } else {
                    el.textContent = '🟢 NORMAL TRAFFIC FLOW';
                    el.className = 'sim4-status-pill sim4-pill-normal';
                }
            }

            updateSignals(mode) {
                if (mode === 'PREEMPTION') {
                    // LANE 1 (EMERGENCY): FORCED GREEN
                    this.setLamp(1, false, false, true);
                    this.setLaneBadge(1, 'sim4-state-green', '🟢 FORCED GREEN');

                    // LANES 2, 3, 4: LOCKED RED
                    [2, 3, 4].forEach(lane => {
                        this.setLamp(lane, true, false, false);
                        this.setLaneBadge(lane, 'sim4-state-red', '🔴 LOCKED RED');
                    });
                } else {
                    // Normal Cycle State
                    // In normal state: Cross traffic (Lanes 2, 3, 4) or Lane 1 have regular green
                    if (this.normalCycleIndex === 0) {
                        // Lanes 2, 3, 4 have GREEN, Lane 1 has RED
                        this.setLamp(1, true, false, false);
                        this.setLaneBadge(1, 'sim4-state-red', '🔴 RED (HOLD)');

                        [2, 3, 4].forEach(lane => {
                            this.setLamp(lane, false, false, true);
                            this.setLaneBadge(lane, 'sim4-state-green', '🟢 GREEN (PASS)');
                        });
                    } else {
                        // Lane 1 has GREEN, others RED
                        this.setLamp(1, false, false, true);
                        this.setLaneBadge(1, 'sim4-state-green', '🟢 GREEN (PASS)');

                        [2, 3, 4].forEach(lane => {
                            this.setLamp(lane, true, false, false);
                            this.setLaneBadge(lane, 'sim4-state-red', '🔴 RED (HOLD)');
                        });
                    }
                }
            }

            startNormalCycle() {
                clearInterval(this.cycleInterval);
                if (this.isPreempted) return;

                this.cycleInterval = setInterval(() => {
                    if (this.isPreempted) return;
                    this.normalCycleIndex = (this.normalCycleIndex === 0) ? 1 : 0;
                    this.updateSignals('NORMAL');
                    this.renderVehicles();
                }, 5000);
            }

            setLamp(lane, red, yellow, green) {
                const r = document.getElementById(`sim4-lamp-${lane}-red`);
                const y = document.getElementById(`sim4-lamp-${lane}-yellow`);
                const g = document.getElementById(`sim4-lamp-${lane}-green`);

                if (r) r.className = `sim4-lamp sim4-lamp-red ${red ? 'lit' : ''}`;
                if (y) y.className = `sim4-lamp sim4-lamp-yellow ${yellow ? 'lit' : ''}`;
                if (g) g.className = `sim4-lamp sim4-lamp-green ${green ? 'lit' : ''}`;
            }

            setLaneBadge(lane, cls, text) {
                const el = document.getElementById(`sim4-light-badge-${lane}`);
                if (!el) return;
                el.className = `sim4-lane-state ${cls}`;
                el.textContent = text;
            }

            getCarSVG(color) {
                return `
                <svg viewBox="0 0 38 68" width="34" height="60">
                    <rect x="2" y="4" width="34" height="62" rx="8" fill="rgba(0,0,0,0.5)" filter="blur(2px)"/>
                    <rect x="4" y="6" width="30" height="56" rx="6" fill="${color}"/>
                    <!-- Cabin / Windshield -->
                    <rect x="7" y="20" width="24" height="26" rx="4" fill="#0f172a"/>
                    <path d="M 8 20 L 11 12 L 27 12 L 30 20 Z" fill="rgba(186, 230, 253, 0.7)"/>
                    <path d="M 8 46 L 11 52 L 27 52 L 30 46 Z" fill="rgba(186, 230, 253, 0.5)"/>
                    <!-- Headlights -->
                    <ellipse cx="8" cy="8" rx="2.5" ry="1.5" fill="#fef08a"/>
                    <ellipse cx="30" cy="8" rx="2.5" ry="1.5" fill="#fef08a"/>
                    <!-- Taillights -->
                    <rect x="7" y="58" width="5" height="2.5" rx="1" fill="#ef4444" style="box-shadow:0 0 4px #ef4444"/>
                    <rect x="26" y="58" width="5" height="2.5" rx="1" fill="#ef4444" style="box-shadow:0 0 4px #ef4444"/>
                </svg>`;
            }

            getAmbulanceSVG() {
                return `
                <div style="position:relative;display:inline-block;">
                    <div class="sim4-siren-ring"></div>
                    <svg viewBox="0 0 44 80" width="38" height="72">
                        <rect x="2" y="4" width="40" height="74" rx="8" fill="rgba(0,0,0,0.6)" filter="blur(3px)"/>
                        <!-- Ambulance Body -->
                        <rect x="4" y="6" width="36" height="68" rx="6" fill="#f8fafc" stroke="#dc2626" stroke-width="1.5"/>
                        <!-- Red Hazard Stripes -->
                        <rect x="4" y="32" width="4" height="34" fill="#ef4444"/>
                        <rect x="36" y="32" width="4" height="34" fill="#ef4444"/>
                        <!-- Cab / Windshield -->
                        <rect x="7" y="18" width="30" height="12" rx="3" fill="#0f172a"/>
                        <path d="M 8 18 L 12 10 L 32 10 L 36 18 Z" fill="rgba(56, 189, 248, 0.8)"/>
                        <!-- Medical Red Cross on Roof -->
                        <rect x="19" y="40" width="6" height="18" rx="1" fill="#dc2626"/>
                        <rect x="13" y="46" width="18" height="6" rx="1" fill="#dc2626"/>
                        <!-- Rooftop Emergency Strobes (Blue & Red) -->
                        <rect x="10" y="28" width="9" height="4" rx="1" class="sim4-strobe-blue" fill="#3b82f6"/>
                        <rect x="25" y="28" width="9" height="4" rx="1" class="sim4-strobe-red" fill="#ef4444"/>
                        <!-- Headlights beams -->
                        <ellipse cx="9" cy="8" rx="3" ry="1.5" fill="#fff"/>
                        <ellipse cx="35" cy="8" rx="3" ry="1.5" fill="#fff"/>
                    </svg>
                </div>`;
            }

            renderVehicles() {
                // Clear all 4 lane vehicle slots
                for (let i = 1; i <= 4; i++) {
                    const slot = document.getElementById(`sim4-slot-${i}`);
                    if (slot) slot.innerHTML = '';
                }

                // Check lights
                const lane1IsGreen = document.getElementById('sim4-lamp-1-green')?.classList.contains('lit');

                // Render Ambulance in Lane 1
                if (this.ambulanceCount > 0) {
                    const slot1 = document.getElementById('sim4-slot-1');
                    if (slot1) {
                        const ambEl = document.createElement('div');
                        ambEl.className = 'sim4-veh ' + (lane1IsGreen ? 'sim4-amb-rushing' : 'stopped-pos-1');
                        ambEl.innerHTML = this.getAmbulanceSVG();
                        slot1.appendChild(ambEl);
                    }
                }

                // Distribute normal cars across lanes
                // If Lane 1 has ambulance, distribute normal cars across Lanes 2, 3, 4
                // Otherwise distribute across Lanes 1, 2, 3, 4
                const targetLanes = (this.ambulanceCount > 0) ? [2, 3, 4] : [1, 2, 3, 4];
                let laneIndex = 0;
                const laneCarCounts = { 1: 0, 2: 0, 3: 0, 4: 0 };

                for (let c = 0; c < this.carCount; c++) {
                    const assignedLane = targetLanes[laneIndex % targetLanes.length];
                    laneCarCounts[assignedLane]++;
                    laneIndex++;

                    const slot = document.getElementById(`sim4-slot-${assignedLane}`);
                    if (!slot) continue;

                    const isLaneGreen = document.getElementById(`sim4-lamp-${assignedLane}-green`)?.classList.contains('lit');
                    const carEl = document.createElement('div');
                    const color = this.carColors[c % this.carColors.length];

                    if (isLaneGreen) {
                        carEl.className = 'sim4-veh cruising';
                        carEl.style.animationDelay = (laneCarCounts[assignedLane] * 1.1) + 's';
                    } else {
                        // Stopped behind stop line
                        const posClass = 'stopped-pos-' + Math.min(3, laneCarCounts[assignedLane]);
                        carEl.className = `sim4-veh ${posClass}`;
                    }

                    carEl.innerHTML = this.getCarSVG(color);
                    slot.appendChild(carEl);
                }
            }
        }

        // Initialize simulation on window load
        window.addEventListener('DOMContentLoaded', () => {
            window.fourLaneSim = new FourLaneSimulation();
        });
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            window.fourLaneSim = new FourLaneSimulation();
        }
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    """Serve the enhanced dashboard."""
    return render_template_string(ENHANCED_DASHBOARD)


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'models_loaded': engine._loaded,
        'live_active': live_camera['active'],
        'preemption_state': preemption.state,
    })


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚦 AI TRAFFIC MANAGEMENT SYSTEM — Enhanced Dashboard")
    print("   Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)")
    print("=" * 70)

    init_engine()

    print("\n🌐 Dashboard: http://localhost:5002")
    print("📷 Live Feed: http://localhost:5002/live/feed")
    print("📹 Upload:    http://localhost:5002 → Video Upload tab")
    print("🚨 Preemption: http://localhost:5002 → Emergency Preemption tab")
    print("=" * 70 + "\n")

    socketio.run(app, host='0.0.0.0', port=5002, debug=False, allow_unsafe_werkzeug=True)
