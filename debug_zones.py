#!/usr/bin/env python3
"""
🔍 Zone Debug Tool
=================
Visualize detection zones and vehicle positions to debug why queues show [0,0]
"""

import sys
sys.path.append('project/src/vision')
import cv2
import numpy as np
from processor import VisionProcessor

def debug_zones():
    """Debug zone detection by visualizing polygons and vehicle positions"""
    print("🔍 Zone Debug Tool")
    print("="*50)
    
    # Load test frame
    cap = cv2.VideoCapture('project/videos/intersection1.mp4')
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("❌ Could not load video frame")
        return
    
    print(f"✅ Frame loaded: {frame.shape}")
    
    # Define polygons (same as in run_live.py) - updated to cover actual vehicle positions
    polygons = [
        # Zone 1: Left area where vehicles are detected (around x=142)
        np.array([[50, 200], [250, 200], [250, 450], [50, 450]], np.int32),
        # Zone 2: Right area 
        np.array([[400, 200], [600, 200], [600, 450], [400, 450]], np.int32),
    ]
    
    print("🔍 Initializing processor...")
    processor = VisionProcessor()
    
    print("🔍 Processing frame...")
    queue_counts, detections = processor.process_frame(frame, polygons)
    
    print(f"📊 Results:")
    print(f"   Queue counts: {queue_counts}")
    print(f"   Total detections: {len(detections)}")
    
    # Create visualization
    debug_frame = frame.copy()
    
    # Draw polygons (border only, no fill)
    for i, polygon in enumerate(polygons):
        cv2.polylines(debug_frame, [polygon], isClosed=True, color=(0, 255, 255), thickness=2)
        
        # Label polygon
        M = cv2.moments(polygon)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.putText(debug_frame, f"ZONE {i+1}", (cx-50, cy), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    
    # Draw detections
    vehicles_in_zones = 0
    for detection in detections:
        box, anchor_point, det_type, details, tracker_id = detection
        x1, y1, x2, y2 = box
        
        # Check if vehicle is in any zone
        in_zone = False
        for polygon in polygons:
            if cv2.pointPolygonTest(polygon, anchor_point, False) >= 0:
                in_zone = True
                vehicles_in_zones += 1
                break
        
        # Color code: Green if in zone, Red if outside zones
        color = (0, 255, 0) if in_zone else (0, 0, 255)
        
        # Draw bounding box
        cv2.rectangle(debug_frame, (x1, y1), (x2, y2), color, 2)
        
        # Draw anchor point
        cv2.circle(debug_frame, anchor_point, 5, color, -1)
        
        # Label
        status = "IN ZONE" if in_zone else "OUTSIDE"
        cv2.putText(debug_frame, f"{status}", (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    print(f"📊 Analysis:")
    print(f"   Vehicles detected: {len(detections)}")
    print(f"   Vehicles in zones: {vehicles_in_zones}")
    print(f"   Vehicles outside zones: {len(detections) - vehicles_in_zones}")
    
    # Save debug image
    cv2.imwrite('debug_zones.jpg', debug_frame)
    print(f"💾 Debug image saved as: debug_zones.jpg")
    
    # Show image if possible
    try:
        cv2.imshow('Zone Debug', debug_frame)
        print("👁️  Press any key to close the debug window...")
        key = cv2.waitKey(0)
        cv2.destroyAllWindows()
        print(f"✅ Window closed (key pressed: {key})")
    except Exception as e:
        print(f"ℹ️  GUI not available: {e}")
        print("   Debug image saved instead")
    
    # Suggest fixes
    if vehicles_in_zones == 0 and len(detections) > 0:
        print("\n💡 SUGGESTIONS:")
        print("   - Polygon coordinates might be wrong for this video resolution")
        print("   - Try adjusting polygon coordinates in run_live.py")
        print("   - Check if video resolution matches expected coordinates")
    elif vehicles_in_zones > 0:
        print("\n✅ GOOD: Some vehicles are being detected in zones!")
        print("   - The system should work correctly")

if __name__ == '__main__':
    debug_zones()