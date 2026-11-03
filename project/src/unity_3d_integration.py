#!/usr/bin/env python3
"""
🎮 Unity 3D Traffic Visualization Integration
============================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Enhanced 3D visualization system for SUMO traffic simulation
"""

import os
if 'SUMO_HOME' not in os.environ:
    os.environ['SUMO_HOME'] = '/opt/homebrew/share/sumo'

import cv2
import numpy as np
import gymnasium as gym
from stable_baselines3 import PPO
import sumo_rl
import threading
import time
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO, emit
import traci
import json
from datetime import datetime
import sys
import os
from pathlib import Path

# Add vision processor
sys.path.append(str(Path(__file__).parent / 'vision'))
from processor import VisionProcessor

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).parent.parent
MODEL_PATH = str(PROJECT_ROOT / "models" / "ppo_traffic_model_v2.zip")
VIDEO_PATH_1 = str(PROJECT_ROOT / "videos" / "intersection1.mp4")
VIDEO_PATH_2 = str(PROJECT_ROOT / "videos" / "intersection2.mp4")

NET_FILE = str(PROJECT_ROOT / "sumo_files" / "jaipur.net.xml")
ROUTE_FILE = str(PROJECT_ROOT / "sumo_files" / "jaipur.rou.xml")
TRAFFIC_LIGHT_ID = "J5"

# 3D Visualization polygons (same as 2D but with Z coordinates)
POLYGONS_3D_VIDEO_1 = [
    {"id": "zone1_cam1", "points": [[50, 200, 0], [250, 200, 0], [250, 450, 0], [50, 450, 0]]},
    {"id": "zone2_cam1", "points": [[400, 200, 0], [600, 200, 0], [600, 450, 0], [400, 450, 0]]},
]
POLYGONS_3D_VIDEO_2 = [
    {"id": "zone1_cam2", "points": [[100, 50, 0], [400, 50, 0], [400, 250, 0], [100, 250, 0]]},
    {"id": "zone2_cam2", "points": [[100, 300, 0], [400, 300, 0], [400, 470, 0], [100, 470, 0]]},
]

# Global state for 3D visualization
simulation_3d_data = {
    "vehicles": [],
    "traffic_lights": {},
    "queue_zones": [],
    "ai_decision": "KEEP",
    "timestamp": datetime.now().isoformat(),
    "performance_metrics": {
        "total_vehicles": 0,
        "avg_speed": 0,
        "wait_time": 0,
        "throughput": 0
    }
}

class Unity3DTrafficSystem:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'unity_3d_traffic_2024'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.setup_routes()
        self.setup_socketio()
        
        # Initialize AI and vision systems
        self.model = PPO.load(MODEL_PATH)
        self.processor = VisionProcessor()
        
        # Video capture
        self.cap1 = cv2.VideoCapture(VIDEO_PATH_1)
        self.cap2 = cv2.VideoCapture(VIDEO_PATH_2)
        
        # SUMO environment
        self.env = gym.make('sumo-rl-v0', 
                           net_file=NET_FILE, 
                           route_file=ROUTE_FILE, 
                           use_gui=False,  # Disable SUMO GUI for 3D visualization
                           num_seconds=86400, 
                           single_agent=True, 
                           reward_fn='diff-waiting-time')
        
        self.obs, self.info = self.env.reset()
        self.frame_count = 0
        self.last_action = 0
        
    def setup_routes(self):
        @self.app.route('/')
        def unity_dashboard():
            return render_template_string(UNITY_3D_DASHBOARD_HTML)
        
        @self.app.route('/api/3d_data')
        def get_3d_data():
            """API endpoint for Unity to fetch 3D simulation data"""
            return jsonify(simulation_3d_data)
        
        @self.app.route('/api/unity_status')
        def unity_status():
            return jsonify({
                "status": "active",
                "vehicles_count": len(simulation_3d_data["vehicles"]),
                "last_update": simulation_3d_data["timestamp"],
                "ai_decision": simulation_3d_data["ai_decision"]
            })
    
    def setup_socketio(self):
        @self.socketio.on('connect')
        def handle_connect():
            print('🎮 Unity client connected!')
            emit('unity_connected', {'status': 'connected'})
        
        @self.socketio.on('request_3d_update')
        def handle_3d_request():
            emit('3d_data_update', simulation_3d_data)
    
    def extract_3d_vehicle_data(self):
        """Extract vehicle data with 3D positioning"""
        vehicles_3d = []
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            for v_id in vehicle_ids:
                pos = traci.vehicle.getPosition(v_id)
                angle = traci.vehicle.getAngle(v_id)
                speed = traci.vehicle.getSpeed(v_id)
                vehicle_type = traci.vehicle.getTypeID(v_id)
                
                # Convert SUMO coordinates to Unity 3D coordinates
                unity_pos = self.sumo_to_unity_coordinates(pos[0], pos[1])
                
                vehicle_data = {
                    "id": v_id,
                    "position": {
                        "x": unity_pos[0],
                        "y": 0.5,  # Height above ground
                        "z": unity_pos[1]
                    },
                    "rotation": {
                        "x": 0,
                        "y": angle,
                        "z": 0
                    },
                    "speed": speed,
                    "type": vehicle_type,
                    "color": self.get_vehicle_color(vehicle_type),
                    "scale": self.get_vehicle_scale(vehicle_type)
                }
                vehicles_3d.append(vehicle_data)
                
        except Exception as e:
            print(f"Error extracting 3D vehicle data: {e}")
        
        return vehicles_3d
    
    def sumo_to_unity_coordinates(self, sumo_x, sumo_y):
        """Convert SUMO coordinates to Unity world coordinates"""
        # Scale and offset for better 3D visualization
        unity_x = (sumo_x - 500) * 0.01  # Center and scale
        unity_z = (sumo_y - 500) * 0.01  # Center and scale
        return [unity_x, unity_z]
    
    def get_vehicle_color(self, vehicle_type):
        """Get color based on vehicle type"""
        colors = {
            "passenger": [0.2, 0.6, 1.0, 1.0],  # Blue
            "truck": [1.0, 0.4, 0.2, 1.0],      # Orange
            "bus": [0.8, 0.8, 0.2, 1.0],        # Yellow
            "emergency": [1.0, 0.2, 0.2, 1.0],  # Red
            "default": [0.6, 0.6, 0.6, 1.0]     # Gray
        }
        return colors.get(vehicle_type, colors["default"])
    
    def get_vehicle_scale(self, vehicle_type):
        """Get scale based on vehicle type"""
        scales = {
            "passenger": [1.0, 1.0, 1.0],
            "truck": [1.5, 1.2, 2.0],
            "bus": [1.3, 1.3, 2.5],
            "emergency": [1.1, 1.1, 1.8],
            "default": [1.0, 1.0, 1.0]
        }
        return scales.get(vehicle_type, scales["default"])
    
    def extract_traffic_light_data(self):
        """Extract traffic light states for 3D visualization"""
        try:
            tls_state = traci.trafficlight.getRedYellowGreenState(TRAFFIC_LIGHT_ID)
            
            # Convert SUMO traffic light state to 3D visualization data
            lights_3d = {
                "intersection_id": TRAFFIC_LIGHT_ID,
                "state": tls_state,
                "lights": []
            }
            
            # Parse each light state
            for i, state in enumerate(tls_state):
                light_data = {
                    "id": f"light_{i}",
                    "state": state,
                    "color": self.get_light_color(state),
                    "intensity": 1.0 if state in ['G', 'g'] else 0.3
                }
                lights_3d["lights"].append(light_data)
            
            return lights_3d
            
        except Exception as e:
            print(f"Error extracting traffic light data: {e}")
            return {"intersection_id": TRAFFIC_LIGHT_ID, "state": "rrrr", "lights": []}
    
    def get_light_color(self, state):
        """Convert SUMO light state to RGB color"""
        colors = {
            'r': [1.0, 0.0, 0.0],  # Red
            'y': [1.0, 1.0, 0.0],  # Yellow
            'g': [0.0, 1.0, 0.0],  # Green
            'G': [0.0, 1.0, 0.0],  # Green (priority)
        }
        return colors.get(state.lower(), [0.5, 0.5, 0.5])  # Default gray
    
    def process_vision_data(self):
        """Process video feeds for queue detection"""
        ret1, frame1 = self.cap1.read()
        ret2, frame2 = self.cap2.read()
        
        if not ret1 or not ret2:
            # Reset videos if they end
            self.cap1.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.cap2.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return [0, 0, 0, 0]
        
        # Process frames for queue detection
        polygons_2d_1 = [np.array([[50, 200], [250, 200], [250, 450], [50, 450]], np.int32),
                         np.array([[400, 200], [600, 200], [600, 450], [400, 450]], np.int32)]
        polygons_2d_2 = [np.array([[100, 50], [400, 50], [400, 250], [100, 250]], np.int32),
                         np.array([[100, 300], [400, 300], [400, 470], [100, 470]], np.int32)]
        
        queue_counts1, _ = self.processor.process_frame(frame1, polygons_2d_1)
        queue_counts2, _ = self.processor.process_frame(frame2, polygons_2d_2)
        
        return queue_counts1 + queue_counts2
    
    def run_simulation_loop(self):
        """Main simulation loop for 3D visualization"""
        global simulation_3d_data
        
        print("🎮 Starting 3D Traffic Simulation...")
        
        while True:
            self.frame_count += 1
            
            # Process vision data
            queue_state = self.process_vision_data()
            
            # AI decision making (every 5 seconds)
            if self.frame_count % 150 == 0:  # Assuming 30 FPS
                num_lanes = len(queue_state)
                current_phase = self.obs[num_lanes:]
                state_for_model = np.concatenate([queue_state, current_phase]).astype(np.float32)
                self.last_action, _ = self.model.predict(state_for_model, deterministic=True)
            
            # Step SUMO simulation
            self.obs, reward, terminated, truncated, info = self.env.step(self.last_action)
            
            # Extract 3D data
            vehicles_3d = self.extract_3d_vehicle_data()
            traffic_lights_3d = self.extract_traffic_light_data()
            
            # Update global 3D state
            simulation_3d_data = {
                "vehicles": vehicles_3d,
                "traffic_lights": traffic_lights_3d,
                "queue_zones": [
                    {"id": "zone1_cam1", "count": queue_state[0], "color": [0.2, 0.8, 1.0, 0.3]},
                    {"id": "zone2_cam1", "count": queue_state[1], "color": [0.2, 0.8, 1.0, 0.3]},
                    {"id": "zone1_cam2", "count": queue_state[2], "color": [1.0, 0.6, 0.2, 0.3]},
                    {"id": "zone2_cam2", "count": queue_state[3], "color": [1.0, 0.6, 0.2, 0.3]},
                ],
                "ai_decision": "SWITCH" if self.last_action == 1 else "KEEP",
                "timestamp": datetime.now().isoformat(),
                "performance_metrics": {
                    "total_vehicles": len(vehicles_3d),
                    "avg_speed": np.mean([v["speed"] for v in vehicles_3d]) if vehicles_3d else 0,
                    "queue_total": sum(queue_state),
                    "throughput": len(vehicles_3d) * 3.6  # Rough throughput calculation
                }
            }
            
            # Broadcast to Unity clients
            self.socketio.emit('3d_data_update', simulation_3d_data)
            
            if terminated or truncated:
                self.obs, self.info = self.env.reset()
            
            time.sleep(0.033)  # ~30 FPS
    
    def start_server(self):
        """Start the 3D visualization server"""
        # Start simulation in separate thread
        sim_thread = threading.Thread(target=self.run_simulation_loop)
        sim_thread.daemon = True
        sim_thread.start()
        
        print("🎮 Starting Unity 3D Integration Server...")
        print("🌐 Unity Dashboard: http://localhost:5002")
        print("📡 3D Data API: http://localhost:5002/api/3d_data")
        
        self.socketio.run(self.app, host='0.0.0.0', port=5002, debug=False)

# Unity 3D Dashboard HTML
UNITY_3D_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎮 Unity 3D Traffic Visualization</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            font-family: 'Arial', sans-serif;
            overflow: hidden;
        }
        
        #unity-container {
            position: relative;
            width: 100vw;
            height: 100vh;
        }
        
        #three-canvas {
            position: absolute;
            top: 0;
            left: 0;
            z-index: 1;
        }
        
        .overlay {
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 10;
            background: rgba(0, 0, 0, 0.8);
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        
        .metric {
            margin: 10px 0;
            font-size: 14px;
        }
        
        .metric-value {
            color: #00ff41;
            font-weight: bold;
        }
        
        .unity-instructions {
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 10;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 10px;
            max-width: 300px;
        }
    </style>
</head>
<body>
    <div id="unity-container">
        <canvas id="three-canvas"></canvas>
        
        <div class="overlay">
            <h3>🎮 3D Traffic Simulation</h3>
            <div class="metric">Vehicles: <span class="metric-value" id="vehicle-count">0</span></div>
            <div class="metric">AI Decision: <span class="metric-value" id="ai-decision">KEEP</span></div>
            <div class="metric">Queue Total: <span class="metric-value" id="queue-total">0</span></div>
            <div class="metric">Avg Speed: <span class="metric-value" id="avg-speed">0</span> km/h</div>
            <div class="metric">Status: <span class="metric-value" id="connection-status">Connecting...</span></div>
        </div>
        
        <div class="unity-instructions">
            <h4>🎯 Unity Integration</h4>
            <p><strong>API Endpoint:</strong><br>
            <code>http://localhost:5002/api/3d_data</code></p>
            <p><strong>WebSocket:</strong><br>
            <code>ws://localhost:5002</code></p>
            <p>Connect your Unity project to this endpoint to receive real-time 3D traffic data.</p>
        </div>
    </div>

    <script>
        // Three.js 3D Visualization
        let scene, camera, renderer;
        let vehicles = {};
        
        function initThreeJS() {
            scene = new THREE.Scene();
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('three-canvas'), alpha: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setClearColor(0x000000, 0);
            
            // Add lights
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(10, 10, 5);
            scene.add(directionalLight);
            
            // Add ground plane
            const groundGeometry = new THREE.PlaneGeometry(50, 50);
            const groundMaterial = new THREE.MeshLambertMaterial({ color: 0x333333 });
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            scene.add(ground);
            
            // Position camera
            camera.position.set(0, 15, 20);
            camera.lookAt(0, 0, 0);
            
            animate();
        }
        
        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        
        function updateVehicles(vehicleData) {
            // Remove old vehicles
            Object.keys(vehicles).forEach(id => {
                if (!vehicleData.find(v => v.id === id)) {
                    scene.remove(vehicles[id]);
                    delete vehicles[id];
                }
            });
            
            // Add/update vehicles
            vehicleData.forEach(vehicle => {
                if (!vehicles[vehicle.id]) {
                    // Create new vehicle
                    const geometry = new THREE.BoxGeometry(0.5, 0.3, 1);
                    const material = new THREE.MeshLambertMaterial({ 
                        color: new THREE.Color(vehicle.color[0], vehicle.color[1], vehicle.color[2])
                    });
                    vehicles[vehicle.id] = new THREE.Mesh(geometry, material);
                    scene.add(vehicles[vehicle.id]);
                }
                
                // Update position
                vehicles[vehicle.id].position.set(
                    vehicle.position.x,
                    vehicle.position.y,
                    vehicle.position.z
                );
                vehicles[vehicle.id].rotation.y = vehicle.rotation.y * Math.PI / 180;
            });
        }
        
        // Socket.IO connection
        const socket = io();
        
        socket.on('connect', function() {
            document.getElementById('connection-status').textContent = 'Connected';
        });
        
        socket.on('3d_data_update', function(data) {
            updateVehicles(data.vehicles);
            
            // Update UI
            document.getElementById('vehicle-count').textContent = data.vehicles.length;
            document.getElementById('ai-decision').textContent = data.ai_decision;
            document.getElementById('queue-total').textContent = data.performance_metrics.queue_total;
            document.getElementById('avg-speed').textContent = data.performance_metrics.avg_speed.toFixed(1);
        });
        
        // Initialize
        initThreeJS();
        
        // Handle window resize
        window.addEventListener('resize', function() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>
"""

def main():
    unity_system = Unity3DTrafficSystem()
    unity_system.start_server()

if __name__ == '__main__':
    main()