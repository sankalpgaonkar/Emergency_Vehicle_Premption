"""
🚨 Emergency Vehicle Detection System
===================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Advanced AI-powered emergency vehicle detection with real-time alerts
"""

import cv2
from ultralytics import YOLO
import numpy as np
from datetime import datetime
import time

# --- CONFIGURATION ---
import os
from pathlib import Path

# Get the project root directory (3 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent
MODEL_PATH_EMERGENCY = str(PROJECT_ROOT / "models" / "yolo_emergency_detector.pt")
MODEL_PATH_GENERAL = 'yolov8m.pt'  # This will be downloaded automatically
VIDEO_PATH = str(PROJECT_ROOT / "videos" / "emergency2.mp4")

# --- CLASS DEFINITIONS ---
EMERGENCY_CLASSES = ['ambulance', 'fire brigade', 'police']
NORMAL_CAR_CLASS = 'car'
CONFIDENCE_THRESHOLD = 0.5

# Visual styling
COLORS = {
    'emergency': (0, 0, 255),      # Red for emergency vehicles
    'normal': (0, 255, 0),         # Green for normal vehicles
    'text_bg': (0, 0, 0),          # Black background for text
    'alert': (0, 255, 255),        # Yellow for alerts
    'header': (255, 100, 0)        # Blue for headers
}

class EmergencyAlert:
    def __init__(self):
        self.active_alerts = []
        self.alert_history = []
        self.last_alert_time = 0
        
    def add_alert(self, vehicle_type, confidence, bbox):
        current_time = time.time()
        alert = {
            'type': vehicle_type,
            'confidence': confidence,
            'bbox': bbox,
            'timestamp': current_time,
            'id': len(self.alert_history)
        }
        
        # Avoid duplicate alerts within 2 seconds
        if current_time - self.last_alert_time > 2.0:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            self.last_alert_time = current_time
            print(f"🚨 EMERGENCY ALERT: {vehicle_type.upper()} detected with {confidence:.1%} confidence!")
        
        # Keep only recent active alerts (last 5 seconds)
        self.active_alerts = [a for a in self.active_alerts if current_time - a['timestamp'] < 5.0]
        
    def get_active_count(self):
        return len(self.active_alerts)
        
    def get_total_count(self):
        return len(self.alert_history)

def create_enhanced_overlay(frame, emergency_count, normal_count, alerts, fps=0):
    """Create professional overlay with emergency alerts and statistics"""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    # Header bar
    cv2.rectangle(overlay, (0, 0), (w, 140), COLORS['text_bg'], -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
    
    # Title with emergency indicator
    title_color = COLORS['alert'] if alerts.get_active_count() > 0 else COLORS['header']
    cv2.putText(frame, "EMERGENCY VEHICLE DETECTION SYSTEM", (20, 35), 
                cv2.FONT_HERSHEY_DUPLEX, 1.0, title_color, 2)
    
    # Timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"TIME: {timestamp}", (w-300, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Statistics
    cv2.putText(frame, f"Emergency Vehicles: {emergency_count}", (20, 70), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS['emergency'], 2)
    cv2.putText(frame, f"Normal Vehicles: {normal_count}", (20, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS['normal'], 2)
    
    # Alert status
    active_alerts = alerts.get_active_count()
    total_alerts = alerts.get_total_count()
    alert_text = f"Active Alerts: {active_alerts} | Total: {total_alerts}"
    cv2.putText(frame, alert_text, (w-400, 70), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS['alert'], 2)
    
    # FPS counter
    if fps > 0:
        cv2.putText(frame, f"FPS: {fps:.1f}", (w-150, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    # Emergency alert banner
    if active_alerts > 0:
        alert_y = 150
        cv2.rectangle(frame, (0, alert_y), (w, alert_y + 50), COLORS['alert'], -1)
        cv2.putText(frame, "EMERGENCY VEHICLE DETECTED - PRIORITY CLEARANCE REQUIRED", 
                    (50, alert_y + 30), cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 0, 0), 2)
    
    return frame

def draw_enhanced_detection(frame, box, class_name, confidence, is_emergency=False):
    """Draw enhanced bounding boxes with professional styling"""
    x1, y1, x2, y2 = box
    
    # Choose colors and styling based on vehicle type
    if is_emergency:
        color = COLORS['emergency']
        thickness = 4
        label_bg_color = COLORS['emergency']
        label_text_color = (255, 255, 255)
        prefix = "EMERGENCY"
    else:
        color = COLORS['normal']
        thickness = 2
        label_bg_color = COLORS['normal']
        label_text_color = (0, 0, 0)
        prefix = "VEHICLE"
    
    # Main bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    
    # Corner accents for emergency vehicles
    if is_emergency:
        corner_size = 20
        # Top-left corner
        cv2.line(frame, (x1, y1), (x1 + corner_size, y1), color, thickness + 2)
        cv2.line(frame, (x1, y1), (x1, y1 + corner_size), color, thickness + 2)
        # Top-right corner
        cv2.line(frame, (x2, y1), (x2 - corner_size, y1), color, thickness + 2)
        cv2.line(frame, (x2, y1), (x2, y1 + corner_size), color, thickness + 2)
        # Bottom-left corner
        cv2.line(frame, (x1, y2), (x1 + corner_size, y2), color, thickness + 2)
        cv2.line(frame, (x1, y2), (x1, y2 - corner_size), color, thickness + 2)
        # Bottom-right corner
        cv2.line(frame, (x2, y2), (x2 - corner_size, y2), color, thickness + 2)
        cv2.line(frame, (x2, y2), (x2, y2 - corner_size), color, thickness + 2)
    
    # Label with confidence (no emojis)
    label = f"{prefix}: {class_name.upper()} ({confidence:.1%})"
    (label_width, label_height), baseline = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    
    # Label background
    label_y = y1 - label_height - 10 if y1 - label_height - 10 > 0 else y2 + label_height + 10
    cv2.rectangle(frame, (x1, label_y - label_height - 5), 
                  (x1 + label_width + 10, label_y + 5), label_bg_color, -1)
    
    # Label text
    cv2.putText(frame, label, (x1 + 5, label_y - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, label_text_color, 2)
    
    # Pulsing effect for emergency vehicles
    if is_emergency:
        pulse_intensity = int(abs(np.sin(time.time() * 5)) * 100)
        pulse_color = (pulse_intensity, pulse_intensity, 255)
        cv2.rectangle(frame, (x1-2, y1-2), (x2+2, y2+2), pulse_color, 1)

def print_banner():
    """Print startup banner"""
    print("\n" + "="*70)
    print("EMERGENCY VEHICLE DETECTION SYSTEM")
    print("="*70)
    print("AI-Powered Emergency Response Detection")
    print("Real-time Vehicle Classification")
    print("Instant Alert System")
    print("="*70 + "\n")

def main():
    """Enhanced main function with professional UI and alerts"""
    print_banner()
    
    # Initialize alert system
    alerts = EmergencyAlert()
    
    print("Loading AI models...")
    try:
        emergency_model = YOLO(MODEL_PATH_EMERGENCY)
        print("Emergency detection model loaded")
    except Exception as e:
        print(f"Error loading emergency model: {e}")
        return

    try:
        general_model = YOLO(MODEL_PATH_GENERAL)
        print("General vehicle model loaded")
    except Exception as e:
        print(f"Error loading general model: {e}")
        return

    print(f"Opening video: {VIDEO_PATH}")
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Error: Could not open video file")
        return

    # Video properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Create window
    window_name = "Emergency Vehicle Detection System"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, min(1200, frame_width), min(800, frame_height))

    print("Starting detection system...")
    print("Controls: 'q' = quit, 's' = save screenshot, 'r' = reset alerts")
    print("="*70)

    frame_count = 0
    start_time = time.time()
    fps_counter = 0
    last_fps_time = start_time

    # --- Main Processing Loop ---
    while True:
        ret, frame = cap.read()
        if not ret:
            print("\nEnd of video reached. Restarting...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop video
            continue

        frame_count += 1
        current_time = time.time()
        
        # Calculate FPS
        fps_counter += 1
        if current_time - last_fps_time >= 1.0:
            current_fps = fps_counter / (current_time - last_fps_time)
            fps_counter = 0
            last_fps_time = current_time
        else:
            current_fps = 0

        # --- AI Detection ---
        general_results = general_model(frame, verbose=False)[0]
        emergency_results = emergency_model(frame, verbose=False)[0]

        emergency_count = 0
        normal_count = 0

        # Process normal vehicles
        for box in general_results.boxes:
            confidence = float(box.conf[0])
            if confidence > CONFIDENCE_THRESHOLD:
                class_id = int(box.cls[0])
                class_name = general_results.names[class_id]

                if class_name == NORMAL_CAR_CLASS:
                    bbox = box.xyxy[0].cpu().numpy().astype(int)
                    draw_enhanced_detection(frame, bbox, class_name, confidence, False)
                    normal_count += 1

        # Process emergency vehicles
        for box in emergency_results.boxes:
            confidence = float(box.conf[0])
            if confidence > CONFIDENCE_THRESHOLD:
                class_id = int(box.cls[0])
                class_name = emergency_results.names[class_id]

                if class_name in EMERGENCY_CLASSES:
                    bbox = box.xyxy[0].cpu().numpy().astype(int)
                    draw_enhanced_detection(frame, bbox, class_name, confidence, True)
                    emergency_count += 1
                    
                    # Add to alert system
                    alerts.add_alert(class_name, confidence, bbox)

        # Apply enhanced overlay
        frame = create_enhanced_overlay(frame, emergency_count, normal_count, alerts, current_fps)

        # Display frame
        cv2.imshow(window_name, frame)

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Save screenshot
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"emergency_detection_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            print(f"Screenshot saved: {filename}")
        elif key == ord('r'):
            # Reset alerts
            alerts = EmergencyAlert()
            print("Alert system reset")

        # Print periodic status
        if frame_count % 100 == 0:
            runtime = current_time - start_time
            print(f"Frame {frame_count:6d} | Runtime: {runtime:6.1f}s | "
                  f"Emergency: {alerts.get_total_count():3d} | Normal: {normal_count:3d}")

    # --- Final Report ---
    runtime = time.time() - start_time
    print("\n" + "="*70)
    print("DETECTION SESSION SUMMARY")
    print("="*70)
    print(f"Total Runtime: {runtime:.1f} seconds")
    print(f"Frames Processed: {frame_count:,}")
    print(f"Emergency Vehicles Detected: {alerts.get_total_count()}")
    print(f"Average FPS: {frame_count/runtime:.1f}")
    print("="*70)

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    print("System shutdown complete")

if __name__ == '__main__':
    main()

