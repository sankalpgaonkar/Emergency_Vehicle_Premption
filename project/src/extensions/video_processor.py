"""
📹 Video Upload & Processing Module
=====================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Handles video file uploads, frame-by-frame processing, and streaming results.
Works with the DetectionEngine without modifying existing code.
"""

import os
import cv2
import time
import uuid
import threading
from pathlib import Path
from datetime import datetime

UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
MAX_FILE_SIZE_MB = 500


class VideoJob:
    """Represents a single video processing job."""

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_ERROR = "error"
    STATUS_CANCELLED = "cancelled"

    def __init__(self, filepath, original_name):
        self.id = str(uuid.uuid4())[:8]
        self.filepath = filepath
        self.original_name = original_name
        self.status = self.STATUS_QUEUED
        self.progress = 0.0
        self.total_frames = 0
        self.processed_frames = 0
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.error = None

        # Results
        self.total_vehicles = 0
        self.total_emergency = 0
        self.emergency_events = []
        self.fps_avg = 0.0

        # Control
        self._cancel = False

    def cancel(self):
        self._cancel = True
        self.status = self.STATUS_CANCELLED

    def to_dict(self):
        return {
            'id': self.id,
            'original_name': self.original_name,
            'status': self.status,
            'progress': round(self.progress, 1),
            'total_frames': self.total_frames,
            'processed_frames': self.processed_frames,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'error': self.error,
            'total_vehicles': self.total_vehicles,
            'total_emergency': self.total_emergency,
            'emergency_events': self.emergency_events[-10:],
            'fps_avg': round(self.fps_avg, 1),
        }


class VideoProcessor:
    """
    Manages video uploads and background processing.
    Uses DetectionEngine for frame-by-frame analysis.
    """

    def __init__(self, detection_engine):
        self.engine = detection_engine
        self.jobs = {}  # id -> VideoJob
        self._current_frame_b64 = None  # Latest processed frame for streaming
        self._lock = threading.Lock()

    def validate_upload(self, filename, file_size_bytes):
        """Validate an uploaded file before saving."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        if file_size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
            return False, f"File too large ({file_size_bytes / 1024 / 1024:.0f} MB). Max: {MAX_FILE_SIZE_MB} MB"
        return True, "OK"

    def save_upload(self, file_storage, original_name):
        """Save an uploaded file and return the filepath."""
        ext = Path(original_name).suffix.lower()
        safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
        filepath = UPLOAD_DIR / safe_name
        file_storage.save(str(filepath))
        return str(filepath)

    def create_job(self, filepath, original_name):
        """Create a new processing job."""
        job = VideoJob(filepath, original_name)
        self.jobs[job.id] = job
        return job

    @staticmethod
    def is_valid_video_url(url: str) -> bool:
        """Check if URL looks like a valid YouTube or video link."""
        if not url or not isinstance(url, str):
            return False
        url_lower = url.strip().lower()
        return any(domain in url_lower for domain in ['youtube.com', 'youtu.be', 'youtube-nocookie.com']) or url_lower.startswith(('http://', 'https://'))

    def get_youtube_info(self, url: str) -> dict:
        """Extract metadata from YouTube video without downloading."""
        import yt_dlp
        
        ydl_opts = {
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'mweb'],
                }
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url.strip(), download=False)
                return {
                    'status': 'ok',
                    'title': info.get('title', 'YouTube Video'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'channel': info.get('uploader', info.get('channel', 'Unknown')),
                    'view_count': info.get('view_count', 0),
                    'id': info.get('id', '')
                }
        except Exception as e:
            # Fallback: attempt with browser cookies
            try:
                ydl_opts_fallback = dict(ydl_opts)
                ydl_opts_fallback['cookiesfrombrowser'] = ('chrome', None, None, None)
                with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                    info = ydl.extract_info(url.strip(), download=False)
                    return {
                        'status': 'ok',
                        'title': info.get('title', 'YouTube Video'),
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'channel': info.get('uploader', info.get('channel', 'Unknown')),
                        'view_count': info.get('view_count', 0),
                        'id': info.get('id', '')
                    }
            except Exception:
                return {'status': 'error', 'error': str(e)}

    def download_youtube(self, url: str, progress_callback=None) -> dict:
        """
        Download YouTube video to UPLOAD_DIR for processing.
        Returns dict with filepath, title, duration, thumbnail.
        """
        import yt_dlp

        out_id = uuid.uuid4().hex[:8]
        outtmpl = str(UPLOAD_DIR / f"yt_{out_id}_%(id)s.%(ext)s")

        def _hook(d):
            if progress_callback and d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                pct = round((downloaded / total * 100), 1) if total > 0 else 0
                speed = d.get('speed') or 0
                progress_callback({
                    'percent': pct,
                    'downloaded_bytes': downloaded,
                    'total_bytes': total,
                    'speed': speed,
                    'status': 'downloading'
                })

        ydl_opts = {
            'format': 'bestvideo[height<=720][ext=mp4]/bestvideo[height<=720]/best[ext=mp4]/best[height<=720]/bestvideo/best',
            'outtmpl': outtmpl,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [_hook] if progress_callback else [],
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'mweb'],
                }
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url.strip(), download=True)
                downloaded_file = ydl.prepare_filename(info)
                
                p = Path(downloaded_file)
                if not p.exists():
                    matches = list(UPLOAD_DIR.glob(f"yt_{out_id}_*"))
                    if matches:
                        downloaded_file = str(matches[0])
                    else:
                        raise FileNotFoundError("Downloaded video file could not be located")

                title = info.get('title', 'YouTube Video')
                duration = info.get('duration', 0)
                thumbnail = info.get('thumbnail', '')
                
                return {
                    'status': 'ok',
                    'filepath': downloaded_file,
                    'title': title,
                    'duration': duration,
                    'thumbnail': thumbnail
                }
        except Exception as e:
            # Fallback: attempt with browser cookies
            try:
                ydl_opts_fallback = dict(ydl_opts)
                ydl_opts_fallback['cookiesfrombrowser'] = ('chrome', None, None, None)
                with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                    info = ydl.extract_info(url.strip(), download=True)
                    downloaded_file = ydl.prepare_filename(info)
                    p = Path(downloaded_file)
                    if not p.exists():
                        matches = list(UPLOAD_DIR.glob(f"yt_{out_id}_*"))
                        if matches:
                            downloaded_file = str(matches[0])
                        else:
                            raise FileNotFoundError("Downloaded video file could not be located")

                    return {
                        'status': 'ok',
                        'filepath': downloaded_file,
                        'title': info.get('title', 'YouTube Video'),
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', '')
                    }
            except Exception:
                return {'status': 'error', 'error': str(e)}

    def create_youtube_job(self, url: str, progress_callback=None):
        """Download YouTube video and create a VideoJob."""
        res = self.download_youtube(url, progress_callback=progress_callback)
        if res.get('status') != 'ok':
            raise ValueError(res.get('error', 'Failed to download YouTube video'))
        
        job = self.create_job(res['filepath'], f"[YouTube] {res['title']}")
        return job, res

    def start_processing(self, job_id, preemption_controller=None, frame_callback=None):
        """
        Start processing a video job in a background thread.
        
        Args:
            job_id: The job ID to process
            preemption_controller: Optional PreemptionController for emergency handling
            frame_callback: Optional callback(frame_b64, detections) for each frame
        """
        job = self.jobs.get(job_id)
        if not job:
            return

        thread = threading.Thread(
            target=self._process_video,
            args=(job, preemption_controller, frame_callback),
            daemon=True,
        )
        thread.start()

    def get_latest_frame(self):
        """Get the latest processed frame as base64 JPEG."""
        return self._current_frame_b64

    def _process_video(self, job, preemption_ctrl, frame_callback):
        """Background video processing loop."""
        job.status = VideoJob.STATUS_PROCESSING
        job.started_at = datetime.now().isoformat()

        cap = cv2.VideoCapture(job.filepath)
        if not cap.isOpened():
            job.status = VideoJob.STATUS_ERROR
            job.error = "Failed to open video file"
            return

        job.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_times = []

        try:
            while not job._cancel:
                ret, frame = cap.read()
                if not ret:
                    break

                t0 = time.time()

                # Detect
                result = self.engine.detect_frame(frame)
                job.processed_frames += 1
                job.total_vehicles += result['normal_vehicle_count']

                # Emergency handling
                if result['emergency_detected']:
                    job.total_emergency += len(result['emergency_vehicles'])
                    for ev in result['emergency_vehicles']:
                        event = {
                            'frame': job.processed_frames,
                            'type': ev['class'],
                            'confidence': ev['confidence'],
                            'timestamp': datetime.now().isoformat(),
                        }
                        job.emergency_events.append(event)

                    if preemption_ctrl:
                        preemption_ctrl.process_detections(result['emergency_vehicles'])

                # Progress
                if job.total_frames > 0:
                    job.progress = (job.processed_frames / job.total_frames) * 100

                # FPS
                elapsed = time.time() - t0
                frame_times.append(elapsed)
                if len(frame_times) > 30:
                    frame_times.pop(0)
                job.fps_avg = 1.0 / (sum(frame_times) / len(frame_times)) if frame_times else 0

                # Stream frame to dashboard
                frame_b64 = self.engine.frame_to_jpeg_base64(result['annotated_frame'])
                with self._lock:
                    self._current_frame_b64 = frame_b64

                if frame_callback:
                    try:
                        frame_callback(frame_b64, result['detections'], job.to_dict())
                    except Exception:
                        pass

                # Skip frames for performance (process every 2nd frame for large videos)
                if job.total_frames > 3000 and job.processed_frames % 2 == 0:
                    cap.read()  # Skip a frame
                    job.processed_frames += 1

        except Exception as e:
            job.status = VideoJob.STATUS_ERROR
            job.error = str(e)
        finally:
            cap.release()

        if job._cancel:
            job.status = VideoJob.STATUS_CANCELLED
        elif job.status != VideoJob.STATUS_ERROR:
            job.status = VideoJob.STATUS_COMPLETED
            job.completed_at = datetime.now().isoformat()
            job.progress = 100.0

        print(f"📹 Video job {job.id} {job.status}: "
              f"{job.processed_frames} frames, {job.total_emergency} emergencies")
