"""
🔍 Detection Engine - Reuses Existing Trained Models
=====================================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Wraps the existing YOLO models for live detection & video processing.
Does NOT retrain — uses the already-trained weights from project/models/.
"""

import cv2
import numpy as np
import time
import base64
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
REPO_ROOT = PROJECT_ROOT.parent


class DetectionEngine:
    """
    Unified detection engine that loads the existing trained models once
    and exposes methods for frame-by-frame detection with annotated output.
    """

    # Emergency vehicle class names from the custom-trained model
    EMERGENCY_CLASSES = {'ambulance', 'fire brigade', 'police'}

    # COCO vehicle class IDs for the general model
    VEHICLE_CLASS_IDS = {2, 3, 5, 7}  # car, motorcycle, bus, truck

    def __init__(self, confidence_threshold=0.45):
        self.confidence_threshold = confidence_threshold
        self._general_model = None
        self._emergency_model = None
        self._loaded = False

    def load_models(self):
        """Load both models (idempotent — safe to call multiple times)."""
        if self._loaded:
            return True

        # --- General vehicle detector (YOLOv8m from repo root) ---
        general_path = REPO_ROOT / "yolov8m.pt"
        if not general_path.exists():
            general_path = REPO_ROOT / "yolov8s.pt"
        if not general_path.exists():
            general_path = REPO_ROOT / "yolov8n.pt"

        try:
            self._general_model = YOLO(str(general_path))
            print(f"✅ General vehicle model loaded: {general_path.name}")
        except Exception as e:
            print(f"❌ Failed to load general model: {e}")
            return False

        # --- Emergency vehicle detector (custom trained) ---
        emergency_path = MODELS_DIR / "yolo_emergency_detector.pt"
        if emergency_path.exists():
            try:
                self._emergency_model = YOLO(str(emergency_path))
                print(f"✅ Emergency model loaded: {emergency_path.name}")
            except Exception as e:
                print(f"⚠️ Emergency model failed to load: {e}")
                self._emergency_model = None
        else:
            print(f"⚠️ Emergency model not found at {emergency_path}")
            self._emergency_model = None

        self._loaded = True
        return True

    def detect_frame(self, frame):
        """
        Run detection on a single frame. Returns a structured dict with:
        - annotated_frame: the frame with bounding boxes drawn
        - detections: list of detection dicts
        - emergency_detected: bool
        - emergency_vehicles: list of emergency detection dicts
        - normal_vehicle_count: int
        - fps_hint: processing time in ms
        """
        if not self._loaded:
            self.load_models()

        start_ms = time.time() * 1000
        detections = []
        emergency_vehicles = []
        emergency_detected = False
        annotated = frame.copy()

        # --- General vehicle detections ---
        if self._general_model:
            results = self._general_model(frame, verbose=False)[0]
            for box in results.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                if conf >= self.confidence_threshold and cls_id in self.VEHICLE_CLASS_IDS:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    class_name = results.names[cls_id]
                    det = {
                        'class': class_name,
                        'confidence': round(conf, 3),
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'is_emergency': False,
                    }
                    detections.append(det)
                    self._draw_box(annotated, x1, y1, x2, y2, class_name, conf, False)

        # --- Emergency vehicle detections ---
        if self._emergency_model:
            emer_results = self._emergency_model(frame, verbose=False)[0]
            for box in emer_results.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                class_name = emer_results.names[cls_id]
                if conf >= self.confidence_threshold and class_name in self.EMERGENCY_CLASSES:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    det = {
                        'class': class_name,
                        'confidence': round(conf, 3),
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'is_emergency': True,
                    }
                    detections.append(det)
                    emergency_vehicles.append(det)
                    emergency_detected = True
                    self._draw_box(annotated, x1, y1, x2, y2, class_name, conf, True)

        # Overlay HUD
        self._draw_hud(annotated, len(detections) - len(emergency_vehicles),
                       len(emergency_vehicles), emergency_detected)

        elapsed_ms = time.time() * 1000 - start_ms

        return {
            'annotated_frame': annotated,
            'detections': detections,
            'emergency_detected': emergency_detected,
            'emergency_vehicles': emergency_vehicles,
            'normal_vehicle_count': len(detections) - len(emergency_vehicles),
            'processing_ms': round(elapsed_ms, 1),
        }

    # ---- Drawing helpers (no external deps, uses OpenCV only) ----

    @staticmethod
    def _draw_box(frame, x1, y1, x2, y2, label, conf, is_emergency):
        if is_emergency:
            color = (0, 0, 255)
            thickness = 3
            prefix = "🚨 "
        else:
            color = (0, 220, 100)
            thickness = 2
            prefix = ""

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        text = f"{prefix}{label} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        label_y = max(y1 - 6, th + 6)
        cv2.rectangle(frame, (x1, label_y - th - 6), (x1 + tw + 8, label_y + 4), color, -1)
        cv2.putText(frame, text, (x1 + 4, label_y - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Corner accents for emergency
        if is_emergency:
            c = 18
            for cx, cy, dx, dy in [
                (x1, y1, 1, 1), (x2, y1, -1, 1),
                (x1, y2, 1, -1), (x2, y2, -1, -1),
            ]:
                cv2.line(frame, (cx, cy), (cx + c * dx, cy), color, thickness + 1)
                cv2.line(frame, (cx, cy), (cx, cy + c * dy), color, thickness + 1)

    @staticmethod
    def _draw_hud(frame, normal_count, emergency_count, emergency_active):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        ts = datetime.now().strftime("%H:%M:%S")
        cv2.putText(frame, f"AI TRAFFIC SYSTEM | {ts}", (12, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        cv2.putText(frame, f"Vehicles: {normal_count}", (w - 360, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 100), 2)
        if emergency_count > 0:
            cv2.putText(frame, f"EMERGENCY: {emergency_count}", (w - 190, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

        if emergency_active:
            pulse = int(abs(np.sin(time.time() * 4)) * 200) + 55
            cv2.rectangle(frame, (0, 50), (w, 80), (0, 0, pulse), -1)
            cv2.putText(frame, "EMERGENCY VEHICLE DETECTED - PREEMPTION ACTIVE",
                        (w // 2 - 300, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    @staticmethod
    def frame_to_jpeg_base64(frame, quality=70):
        """Encode an OpenCV frame to base64 JPEG for web streaming."""
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buf).decode('utf-8')

    @staticmethod
    def frame_to_jpeg_bytes(frame, quality=70):
        """Encode an OpenCV frame to JPEG bytes for MJPEG streaming."""
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes()
