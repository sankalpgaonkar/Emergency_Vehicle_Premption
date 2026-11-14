# Copyright (c) 2026 Sankalp Gaonkar
# Part of the v2 demo (demo_app/). See NEW_COMPONENTS.md for what is new in v2.
"""Video helpers: validation, browser-friendly transcoding (H.264) via ffmpeg.

ffmpeg comes from the system PATH, or from the `imageio-ffmpeg` pip package
(which ships a static ffmpeg for Windows/macOS/Linux), so no manual install is needed."""
import shutil
import subprocess
from pathlib import Path

import cv2


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


class VideoError(Exception):
    """A problem with the uploaded file that the user can act on."""


def probe(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoError("The file could not be opened as a video. It may be corrupted or in an unsupported codec.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise VideoError("No frames could be decoded from this file. It may be corrupted or truncated.")
    if fps <= 1 or fps > 240:
        fps = 25.0
    dur = n / fps if n > 0 else None
    return {"fps": round(fps, 3), "frames": n, "width": w or frame.shape[1], "height": h or frame.shape[0],
            "duration": round(dur, 2) if dur else None}


def transcode_for_browser(src, dst, max_seconds, max_width=960, log_path=None):
    """Re-encode to H.264/yuv420p MP4 (plays in every browser), keeping timestamps.
    Detection then runs on THIS file so the overlay matches playback exactly."""
    exe = ffmpeg_exe()
    if not exe:
        raise VideoError("ffmpeg is not available. Install it or `pip install imageio-ffmpeg`.")
    cmd = [exe, "-y", "-v", "error", "-i", str(src), "-t", str(max_seconds),
           "-vf", f"scale='min({max_width},iw)':-2", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(dst)]
    log = open(log_path, "w") if log_path else subprocess.DEVNULL
    try:
        r = subprocess.run(cmd, stdout=log, stderr=log, timeout=900)
    finally:
        if log_path:
            log.close()
    if r.returncode != 0 or not Path(dst).exists() or Path(dst).stat().st_size < 1000:
        msg = ""
        if log_path and Path(log_path).exists():
            msg = Path(log_path).read_text()[-300:]
        raise VideoError("The video could not be decoded (ffmpeg failed). " + msg.strip())
    return dst
