import cv2
import numpy as np
import gymnasium as gym
from stable_baselines3 import PPO
import sumo_rl
from processor import VisionProcessor 
import threading
import time
from flask import Flask, jsonify
import traci

# --- CONFIGURATION ---
MODEL_PATH = "project/models/ppo_traffic_model_v2.zip"
VIDEO_PATH_1 = "project/videos/intersection1.mp4"
VIDEO_PATH_2 = "project/videos/intersection2.mp4"

NET_FILE = 'project/sumo_files/jaipur.net.xml'
ROUTE_FILE = 'project/sumo_files/jaipur.rou.xml'

# IMPORTANT: You must find the ID of your traffic light in the .net.xml file
TRAFFIC_LIGHT_ID = "J5" # e.g., "J1" or "cluster_23_24_25"

POLYGONS_VIDEO_1 = [
    np.array([[874, 1086], [1443, 1035], [793, 581], [572, 590]], np.int32),
    np.array([[1947, 920], [2129, 1007], [2778, 935], [2709, 856]], np.int32),
]
POLYGONS_VIDEO_2 = [
    np.array([[1445, 806], [1596, 903], [2647, 784], [2447, 682]], np.int32),
    np.array([[1239, 1138], [1792, 1029], [2804, 1537], [2031, 1667]], np.int32),
]

# --- Global variable to share data between simulation thread and Flask ---
latest_simulation_data = {
    "vehicles": [],
    "tls_state": ""
}

# --- The simulation logic will run in this function ---
def run_simulation():
    global latest_simulation_data

    # --- INITIALIZATION ---
    DECISION_INTERVAL_SECONDS = 5
    print("Loading AI model...")
    model = PPO.load(MODEL_PATH)
    print("Initializing Vision Processor...")
    processor = VisionProcessor()
    print("Opening video files...")
    cap1 = cv2.VideoCapture(VIDEO_PATH_1)
    cap2 = cv2.VideoCapture(VIDEO_PATH_2)
    if not cap1.isOpened() or not cap2.isOpened():
        print(f"Error: Could not open one or both video files.")
        return
    video_fps = cap1.get(cv2.CAP_PROP_FPS)
    decision_interval_frames = int(video_fps * DECISION_INTERVAL_SECONDS)
    
    print("Starting SUMO environment...")
    # use_gui=False is recommended for server mode, but True is fine for debugging
    env = gym.make('sumo-rl-v0', net_file=NET_FILE, route_file=ROUTE_FILE, use_gui=True, num_seconds=86400, single_agent=True, reward_fn='diff-waiting-time', observation_class=sumo_rl.environment.observations.DefaultObservationFunction)
    
    obs, info = env.reset()
    frame_count = 0
    last_action = 0

    # --- MAIN LOOP ---
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()
        if not ret1 or not ret2:
            # Loop videos if they end
            print("Resetting video files.")
            cap1.set(cv2.CAP_PROP_POS_FRAMES, 0)
            cap2.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        frame_count += 1
        
        # --- PERCEIVE ---
        queue_counts1, _ = processor.process_frame(frame1, POLYGONS_VIDEO_1)
        queue_counts2, _ = processor.process_frame(frame2, POLYGONS_VIDEO_2)
        state_from_video = queue_counts1 + queue_counts2
        
        # --- THINK & ACT ---
        if frame_count % decision_interval_frames == 0:
            num_lanes = len(state_from_video)
            current_phase_from_sim = obs[num_lanes:]
            state_for_model = np.concatenate([state_from_video, current_phase_from_sim]).astype(np.float32)
            last_action, _ = model.predict(state_for_model, deterministic=True)
            
        obs, reward, terminated, truncated, info = env.step(last_action)

        # --- DATA EXTRACTION FOR UNITY ---
        # Get all vehicle data
        current_vehicles = []
        vehicle_ids = traci.vehicle.getIDList()
        for v_id in vehicle_ids:
            pos = traci.vehicle.getPosition(v_id)
            angle = traci.vehicle.getAngle(v_id)
            current_vehicles.append({
                "id": v_id,
                "x": pos[0],
                "y": pos[1], # In SUMO, z is often represented by y
                "angle": angle
            })
        
        # Get traffic light state
        tls_state_str = traci.trafficlight.getRedYellowGreenState(TRAFFIC_LIGHT_ID)
        
        # --- UPDATE GLOBAL STATE (thread-safe) ---
        latest_simulation_data = {
            "vehicles": current_vehicles,
            "tls_state": tls_state_str
        }

        if terminated or truncated:
            obs, info = env.reset()

# --- Flask Server Setup ---
app = Flask(__name__)

@app.route('/get_sumo_data')
def get_sumo_data():
    return jsonify(latest_simulation_data)

def main():
    print("Starting simulation thread...")
    sim_thread = threading.Thread(target=run_simulation)
    sim_thread.daemon = True
    sim_thread.start()
    
    print("Starting Flask server for Unity...")
    # Use 0.0.0.0 to make it accessible from other devices on the same network
    app.run(host='0.0.0.0', port=5001)

if __name__ == '__main__':
    main()