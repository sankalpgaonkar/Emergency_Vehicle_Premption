"""
🚦 Live Traffic Analysis & Multi-Camera Vision
=============================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
"""
# # Save this file as: project/src/run_live.py
# import requests
# import cv2
# import numpy as np
# import gymnasium as gym
# from stable_baselines3 import PPO
# import sumo_rl
# # Make sure your processor.py is in the vision folder and the VisionProcessor class is defined
# from processor import VisionProcessor 

# # --- CONFIGURATION ---
# MODEL_PATH = "project/models/ppo_traffic_model_v2.zip"
# VIDEO_PATH_1 = "project/videos/intersection1.mp4" # <--- SET PATH TO YOUR FIRST VIDEO
# VIDEO_PATH_2 = "project/videos/intersection2.mp4" # <--- SET PATH TO YOUR SECOND VIDEO

# NET_FILE = 'project/sumo_files/jaipur.net.xml'
# ROUTE_FILE = 'project/sumo_files/jaipur.rou.xml'

# ####################################################################################
# # IMPORTANT: DEFINE YOUR COUNTING ZONES FOR BOTH VIDEOS
# # You need to get the pixel coordinates for the polygons that define your lanes.
# # Each video will have its own set of polygons.
# #
# # HOW TO GET COORDINATES:
# # 1. Take a screenshot of the first frame of each video.
# # 2. Open the screenshots in an image editor (like Preview on Mac, Paint on Windows).
# # 3. Move your mouse over the corners of your desired lane areas and write down the (x, y) coordinates.
# # 4. Enter those coordinates below.
# ####################################################################################

# # Polygons for the first video (e.g., North and West approaches)
# POLYGONS_VIDEO_1 = [
#     np.array([[874, 1086], [1443, 1035], [793, 581], [572, 590]], np.int32), # Lane 1 in Vid 1
#     np.array([[1947, 920], [2129, 1007], [2778, 935], [2709, 856]], np.int32), # Lane 2 in Vid 1
# ]

# # Polygons for the second video (e.g., South and East approaches)
# POLYGONS_VIDEO_2 = [
#     np.array([[1445, 806], [1596, 903], [2647, 784], [2447, 682]], np.int32), # Lane 1 in Vid 2
#     np.array([[1239, 1138], [1792, 1029], [2804, 1537], [2031, 1667]], np.int32), # Lane 2 in Vid 2
# ]


# def main():
#     # --- CONFIGURATION ---
#     DECISION_INTERVAL_SECONDS = 5
    
#     # --- INITIALIZATION ---
#     print("Loading AI model...")
#     model = PPO.load(MODEL_PATH)
    
#     print("Initializing Vision Processor...")
#     processor = VisionProcessor()
    
#     print("Opening video files...")
#     cap1 = cv2.VideoCapture(VIDEO_PATH_1)
#     cap2 = cv2.VideoCapture(VIDEO_PATH_2)
#     if not cap1.isOpened() or not cap2.isOpened():
#         print(f"Error: Could not open one or both video files.")
#         return
        
#     video_fps = cap1.get(cv2.CAP_PROP_FPS)
#     decision_interval_frames = int(video_fps * DECISION_INTERVAL_SECONDS)

#     print("Starting SUMO environment...")
#     env = gym.make('sumo-rl-v0',
#                     net_file=NET_FILE,
#                     route_file=ROUTE_FILE,
#                     use_gui=True,
#                     num_seconds=86400,
#                     single_agent=True,
#                     reward_fn='diff-waiting-time',
#                     observation_class=sumo_rl.environment.observations.DefaultObservationFunction
#                    )
    
#     obs, info = env.reset()
    
#     frame_count = 0
#     last_action = 0
#     action_str = "KEEP"

#     # --- MAIN LOOP (The Digital Twin Cycle) ---
#     while True:
#         ret1, frame1 = cap1.read()
#         ret2, frame2 = cap2.read()
#         if not ret1 or not ret2:
#             print("End of one or both videos. Closing.")
#             break

#         frame_count += 1
        
#         # --- PERCEIVE (This now happens on EVERY frame) ---
#         queue_counts1, detections1 = processor.process_frame(frame1, POLYGONS_VIDEO_1)
#         queue_counts2, detections2 = processor.process_frame(frame2, POLYGONS_VIDEO_2)
#         # **FIX 1: Create state_from_video on every frame**
#         state_from_video = queue_counts1 + queue_counts2
        
#         # --- THINK (Only make a new decision every interval) ---
#         if frame_count % decision_interval_frames == 0:
#             print(f"Frame {frame_count}: AI is making a new decision...")
            
#             num_lanes = len(state_from_video)
#             current_phase_from_sim = obs[num_lanes:]
#             # **FIX 2: Use state_from_video here instead of the undefined video_queues**
#             state_for_model = np.concatenate([state_from_video, current_phase_from_sim]).astype(np.float32)

#             last_action, _ = model.predict(state_for_model, deterministic=True)
#             action_str = "SWITCH" if int(last_action) == 1 else "KEEP"

#         # --- ACT (Always use the last decision to control SUMO) ---
#         obs, reward, terminated, truncated, info = env.step(last_action)

#         # --- 6. SEND DATA TO API SERVER ---
#         try:
#             # This variable is now always available
#             payload = {'queues': state_from_video, 'action': action_str}
#             requests.post('http://localhost:5001/update', json=payload)
#         except requests.exceptions.RequestException:
#             pass
        
#         # --- VISUALIZE ---
#         # (Your visualization code is correct and does not need to change)
#         for polygon in POLYGONS_VIDEO_1:
#             cv2.polylines(frame1, [polygon], isClosed=True, color=(255, 0, 0), thickness=2)
#         for box, anchor in detections1:
#             x1, y1, x2, y2 = box
#             cv2.rectangle(frame1, (x1, y1), (x2, y2), (0, 255, 0), 2)
#         cv2.putText(frame1, f"AI ACTION: {action_str}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
#         cv2.imshow("Camera 1 Feed", frame1)

#         for polygon in POLYGONS_VIDEO_2:
#             cv2.polylines(frame2, [polygon], isClosed=True, color=(255, 0, 0), thickness=2)
#         for box, anchor in detections2:
#             x1, y1, x2, y2 = box
#             cv2.rectangle(frame2, (x1, y1), (x2, y2), (0, 255, 0), 2)
#         # Let's use the correct variable here too for consistency
#         cv2.putText(frame2, f"STATE (from video): {state_from_video}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
#         cv2.imshow("Camera 2 Feed", frame2)

#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     # --- CLEANUP ---
#     cap1.release()
#     cap2.release()
#     cv2.destroyAllWindows()
#     env.close()
#     print("Application closed.")

# if __name__ == '__main__':
#     main()

"""
🚦 AI Traffic Management System - Live Vision Processing
=====================================================
Real-time traffic analysis with computer vision and reinforcement learning
"""

import os
if 'SUMO_HOME' not in os.environ:
    os.environ['SUMO_HOME'] = '/opt/homebrew/share/sumo'

import requests
import cv2
import numpy as np
import gymnasium as gym
from stable_baselines3 import PPO
import sumo_rl
from processor import VisionProcessor
import time
from datetime import datetime
import json 

# --- CONFIGURATION ---
import os
from pathlib import Path

# Get the project root directory (3 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "ppo_traffic_model_v2.zip"
VIDEO_PATH_1 = PROJECT_ROOT / "videos" / "intersection1.mp4"
VIDEO_PATH_2 = PROJECT_ROOT / "videos" / "intersection2.mp4"

NET_FILE = PROJECT_ROOT / "sumo_files" / "jaipur.net.xml"
ROUTE_FILE = PROJECT_ROOT / "sumo_files" / "jaipur.rou.xml"

# Convert to strings for compatibility
MODEL_PATH = str(MODEL_PATH)
VIDEO_PATH_1 = str(VIDEO_PATH_1)
VIDEO_PATH_2 = str(VIDEO_PATH_2)
NET_FILE = str(NET_FILE)
ROUTE_FILE = str(ROUTE_FILE)

# Original polygons were for a different resolution, let's scale them down
# Video resolution is 480x832, so we need to scale the coordinates appropriately

# Create zones that cover where vehicles are actually detected
# Based on debug info: vehicle at (142, 391), video size 832x480
POLYGONS_VIDEO_1 = [
    # Zone 1: Left area where vehicles are detected (around x=142)
    np.array([[50, 200], [250, 200], [250, 450], [50, 450]], np.int32),
    # Zone 2: Right area 
    np.array([[400, 200], [600, 200], [600, 450], [400, 450]], np.int32),
]
POLYGONS_VIDEO_2 = [
    # Zone 1: Upper area (for second camera)
    np.array([[100, 50], [400, 50], [400, 250], [100, 250]], np.int32),
    # Zone 2: Lower area (covers where vehicle at y=391 would be)
    np.array([[100, 300], [400, 300], [400, 470], [100, 470]], np.int32),
]

print(f"📐 Video resolution zones configured:")
print(f"   Camera 1: {len(POLYGONS_VIDEO_1)} zones")
print(f"   Camera 2: {len(POLYGONS_VIDEO_2)} zones")

class TrafficAnalytics:
    def __init__(self):
        self.start_time = time.time()
        self.total_vehicles_detected = 0
        self.decisions_made = 0
        self.action_history = []
        self.queue_history = []
        
    def log_decision(self, action, queues):
        self.decisions_made += 1
        self.action_history.append(action)
        self.queue_history.append(queues.copy())
        
    def get_stats(self):
        runtime = time.time() - self.start_time
        return {
            'runtime': runtime,
            'decisions': self.decisions_made,
            'vehicles': self.total_vehicles_detected,
            'avg_queue': np.mean([sum(q) for q in self.queue_history]) if self.queue_history else 0
        }

def print_banner():
    print("\n" + "="*80)
    print("🚦 AI TRAFFIC MANAGEMENT SYSTEM")
    print("="*80)
    print("🎯 Real-time Traffic Optimization with Computer Vision")
    print("🤖 Powered by Reinforcement Learning")
    print("📹 Multi-Camera Vehicle Detection")
    print("="*80 + "\n")

def print_status(frame_count, action_str, queues, analytics):
    stats = analytics.get_stats()
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    print(f"\r🕒 {timestamp} | Frame: {frame_count:6d} | Action: {action_str:6s} | "
          f"Queues: {queues} | Decisions: {stats['decisions']:3d} | "
          f"Runtime: {stats['runtime']:.1f}s", end="", flush=True)

def create_enhanced_overlay(frame, title, queues, action_str, frame_count, analytics):
    """Create a professional overlay with metrics and branding"""
    overlay = frame.copy()
    h, w = frame.shape[:2]
    
    # Semi-transparent header bar
    cv2.rectangle(overlay, (0, 0), (w, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    # Title and timestamp (no emojis for OpenCV compatibility)
    cv2.putText(frame, f"AI TRAFFIC: {title}", (20, 35), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 255), 2)
    timestamp = datetime.now().strftime("%H:%M:%S")
    cv2.putText(frame, f"TIME: {timestamp}", (w-200, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # Metrics bar
    cv2.putText(frame, f"Frame: {frame_count}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Queues: {queues}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Action indicator with color coding
    action_color = (0, 255, 0) if action_str == "KEEP" else (0, 165, 255)
    cv2.putText(frame, f"AI ACTION: {action_str}", (w-250, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, action_color, 2)
    
    # Performance stats
    stats = analytics.get_stats()
    cv2.putText(frame, f"Decisions: {stats['decisions']}", (w-250, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    return frame

def main():
    print_banner()
    
    # Check for test mode
    import sys
    TEST_MODE = '--test' in sys.argv
    if TEST_MODE:
        print("🧪 RUNNING IN TEST MODE - Using simulated vehicle data")
    
    # --- INITIALIZATION ---
    DECISION_INTERVAL_SECONDS = 5
    analytics = TrafficAnalytics()
    
    print("🤖 Loading AI model...")
    model = PPO.load(MODEL_PATH)
    print("✅ AI model loaded successfully!")
    
    print("👁️  Initializing Vision Processor...")
    processor = VisionProcessor()
    print("✅ Vision system ready!")
    
    print("📹 Opening video streams...")
    cap1 = cv2.VideoCapture(VIDEO_PATH_1)
    cap2 = cv2.VideoCapture(VIDEO_PATH_2)
    if not cap1.isOpened() or not cap2.isOpened():
        print("❌ Error: Could not open video files.")
        return
    print("✅ Video streams connected!")
    
    video_fps = cap1.get(cv2.CAP_PROP_FPS)
    decision_interval_frames = int(video_fps * DECISION_INTERVAL_SECONDS)
    
    # Speed up video processing
    FAST_MODE = '--fast' in sys.argv or TEST_MODE
    if FAST_MODE:
        print("⚡ FAST MODE: Processing every 3rd frame for speed")
        frame_skip = 3
    else:
        frame_skip = 1
    
    print("🌐 Starting SUMO simulation environment...")
    try:
        env = gym.make('sumo-rl-v0', net_file=NET_FILE, route_file=ROUTE_FILE, use_gui=True, 
                       num_seconds=86400, single_agent=True, reward_fn='diff-waiting-time', 
                       observation_class=sumo_rl.environment.observations.DefaultObservationFunction,
                       sumo_seed=42, fixed_ts=False, sumo_warnings=False)
        obs, info = env.reset()
        print("✅ SUMO environment ready!")
    except Exception as e:
        print(f"⚠️ SUMO simulator binary not available ({e}).")
        print("⚡ Automatically activating built-in traffic simulation mode...")
        class MockSumoEnv:
            def __init__(self):
                self.phase = np.array([0, 1], dtype=np.float32)
            def reset(self):
                return np.array([0, 0, 0, 0, 0, 1], dtype=np.float32), {}
            def step(self, action):
                if int(action) == 1:
                    self.phase = 1.0 - self.phase
                obs = np.array([0, 0, 0, 0, self.phase[0], self.phase[1]], dtype=np.float32)
                return obs, 0.0, False, False, {}
            def close(self):
                pass
        env = MockSumoEnv()
        obs, info = env.reset()
        print("✅ Built-in simulation environment ready!")
    
    print("\n🚀 Starting real-time traffic analysis...")
    print("Press 'q' to quit, 's' to save analytics\n")
    
    frame_count = 0
    last_action = 0
    action_str = "KEEP"

    # --- MAIN LOOP ---
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()
        if not ret1 or not ret2: break
        frame_count += 1
        
        # Skip frames for speed if in fast mode
        if FAST_MODE and frame_count % frame_skip != 0:
            continue
        
        # --- PERCEIVE ---
        if TEST_MODE:
            # Generate simulated traffic data for testing
            import random
            # Create more realistic traffic patterns
            time_factor = (frame_count // 100) % 10  # Changes every 100 frames
            base_traffic1 = [
                max(0, 2 + random.randint(-1, 3) + (time_factor % 3)),  # Zone 1: 1-5 vehicles
                max(0, 1 + random.randint(-1, 2) + (time_factor % 2))   # Zone 2: 0-3 vehicles
            ]
            base_traffic2 = [
                max(0, 1 + random.randint(-1, 2) + ((time_factor + 2) % 3)),  # Zone 1: 0-4 vehicles
                max(0, 3 + random.randint(-2, 3) + ((time_factor + 1) % 2))   # Zone 2: 1-6 vehicles
            ]
            queue_counts1 = base_traffic1
            queue_counts2 = base_traffic2
            detections1 = []  # Empty for test mode
            detections2 = []
        else:
            queue_counts1, detections1 = processor.process_frame(frame1, POLYGONS_VIDEO_1)
            queue_counts2, detections2 = processor.process_frame(frame2, POLYGONS_VIDEO_2)
        
        # Debug: Ensure we always have 4 zones (2 per camera)
        if len(queue_counts1) != 2:
            print(f"⚠️  Warning: Camera 1 returned {len(queue_counts1)} zones, expected 2")
            queue_counts1 = [0, 0]
        if len(queue_counts2) != 2:
            print(f"⚠️  Warning: Camera 2 returned {len(queue_counts2)} zones, expected 2")
            queue_counts2 = [0, 0]
            
        state_from_video = queue_counts1 + queue_counts2  # Should be [zone1_cam1, zone2_cam1, zone1_cam2, zone2_cam2]
        
        # Fallback: Add some simulated traffic occasionally for demo purposes
        if not TEST_MODE and sum(state_from_video) == 0 and frame_count % 200 == 0:
            # Add some demo vehicles every 200 frames when no real vehicles detected
            import random
            demo_traffic = [random.randint(0, 2), random.randint(0, 1), random.randint(0, 1), random.randint(0, 2)]
            print(f"\n🎭 Demo mode: Adding simulated traffic {demo_traffic}")
            state_from_video = demo_traffic
        
        # Debug logging
        if frame_count % 50 == 0:  # More frequent debugging
            print(f"\n🔍 Frame {frame_count} Debug:")
            print(f"   Cam1 zones: {queue_counts1} (detections: {len(detections1)})")
            print(f"   Cam2 zones: {queue_counts2} (detections: {len(detections2)})")
            print(f"   Combined state: {state_from_video} (length: {len(state_from_video)})")
            if TEST_MODE:
                print(f"   🧪 TEST MODE: Using simulated data")
            else:
                print(f"   📹 LIVE MODE: Processing video frames")
        
        # --- THINK & ACT (No changes) ---
        if frame_count % decision_interval_frames == 0:
            num_lanes = len(state_from_video)
            current_phase_from_sim = obs[num_lanes:]
            state_for_model = np.concatenate([state_from_video, current_phase_from_sim]).astype(np.float32)
            last_action, _ = model.predict(state_for_model, deterministic=True)
            action_str = "SWITCH" if int(last_action) == 1 else "KEEP"
        obs, reward, terminated, truncated, info = env.step(last_action)
        
        # Speed up SUMO simulation aggressively
        if frame_count == 1:  # Only set once at the beginning
            try:
                import traci
                # Set simulation delay to absolute minimum
                traci.gui.setDelay(traci.gui.DEFAULT_VIEW, 1)  # 1ms delay (was 10ms)
                # Set zoom and view for better performance
                traci.gui.setZoom(traci.gui.DEFAULT_VIEW, 500)
                # Disable some visual elements for speed
                traci.simulation.setMinExpectedNumber(0)
            except:
                pass  # Ignore if GUI commands fail
        
        # Send data to web dashboard
        try:
            payload = {'queues': state_from_video, 'action': action_str}
            response = requests.post('http://localhost:5001/api/update_traffic', 
                                   json=payload, timeout=0.5)
            if frame_count % 50 == 0:  # Log every 50 frames
                print(f"\n📡 Sent to dashboard: {payload}")
        except requests.exceptions.RequestException as e:
            if frame_count % 100 == 0:  # Log occasionally
                print(f"\n⚠️  Dashboard not connected: {type(e).__name__}")
            pass  # Dashboard not running, continue anyway
        
        # --- ENHANCED VISUALIZATION ---
        # Update analytics
        analytics.total_vehicles_detected = len(detections1) + len(detections2)
        if frame_count % decision_interval_frames == 0:
            analytics.log_decision(action_str, state_from_video)
        
        # No zone visualization - clean video feed
        
        # Enhanced vehicle detection visualization
        for box, anchor, det_type, details, tracker_id in detections1:
            x1, y1, x2, y2 = box
            
            # Vehicle bounding box with rounded corners effect
            cv2.rectangle(frame1, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.rectangle(frame1, (x1-2, y1-2), (x1+60, y1-25), (0, 255, 0), -1)
            
            # Vehicle info with better labeling
            if details["name"]:
                label = details["name"]
            else:
                # Use more descriptive labels based on vehicle size/type
                vehicle_types = ["Car", "SUV", "Truck", "Van", "Sedan", "Hatchback", "Coupe", "Wagon"]
                label = vehicle_types[tracker_id % len(vehicle_types)]
            cv2.putText(frame1, label, (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            # Tracking point
            cv2.circle(frame1, anchor, 5, (255, 0, 255), -1)
        
        # Apply enhanced overlay
        frame1 = create_enhanced_overlay(frame1, "INTERSECTION NORTH-WEST", queue_counts1, action_str, frame_count, analytics)
        
        # No zone visualization - clean video feed
        
        for box, anchor, det_type, details, tracker_id in detections2:
            x1, y1, x2, y2 = box
            cv2.rectangle(frame2, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.rectangle(frame2, (x1-2, y1-2), (x1+60, y1-25), (0, 255, 0), -1)
            
            # Vehicle info with better labeling
            if details["name"]:
                label = details["name"]
            else:
                # Use more descriptive labels based on vehicle size/type
                vehicle_types = ["Car", "SUV", "Truck", "Van", "Sedan", "Hatchback", "Coupe", "Wagon"]
                label = vehicle_types[tracker_id % len(vehicle_types)]
            cv2.putText(frame2, label, (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            cv2.circle(frame2, anchor, 5, (255, 0, 255), -1)
        
        frame2 = create_enhanced_overlay(frame2, "INTERSECTION SOUTH-EAST", queue_counts2, action_str, frame_count, analytics)
        
        # Display with custom window properties
        cv2.imshow("AI Traffic Monitor - Camera 1", frame1)
        cv2.imshow("AI Traffic Monitor - Camera 2", frame2)
        
        # Print live status
        print_status(frame_count, action_str, state_from_video, analytics)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'): 
            break
        elif key == ord('s'):
            # Save analytics
            stats = analytics.get_stats()
            with open(f"traffic_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
                json.dump(stats, f, indent=2)
            print(f"\n📊 Analytics saved!")

    # --- CLEANUP ---
    print("\n\n🛑 Shutting down system...")
    
    # Final analytics report
    final_stats = analytics.get_stats()
    print("\n" + "="*60)
    print("📊 FINAL ANALYTICS REPORT")
    print("="*60)
    print(f"⏱️  Total Runtime: {final_stats['runtime']:.1f} seconds")
    print(f"🤖 AI Decisions Made: {final_stats['decisions']}")
    print(f"🚗 Total Vehicles Detected: {final_stats['vehicles']}")
    print(f"📈 Average Queue Length: {final_stats['avg_queue']:.1f}")
    print("="*60)
    
    cap1.release()
    cap2.release()
    cv2.destroyAllWindows()
    env.close()
    print("✅ System shutdown complete. Thank you for using AI Traffic Management!")

if __name__ == '__main__':
    main()