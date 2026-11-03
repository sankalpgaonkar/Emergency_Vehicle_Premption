#!/usr/bin/env python3
"""
🎮 Integrated 3D Traffic Management System
=========================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Complete 3D visualization integrated with existing traffic AI system
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
from flask import Flask, render_template_string, jsonify
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

# Detection zones (same as 2D system)
POLYGONS_VIDEO_1 = [
    np.array([[50, 200], [250, 200], [250, 450], [50, 450]], np.int32),
    np.array([[400, 200], [600, 200], [600, 450], [400, 450]], np.int32),
]
POLYGONS_VIDEO_2 = [
    np.array([[100, 50], [400, 50], [400, 250], [100, 250]], np.int32),
    np.array([[100, 300], [400, 300], [400, 470], [100, 470]], np.int32),
]

class Integrated3DTrafficSystem:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'integrated_3d_traffic_2024'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Initialize components
        self.setup_routes()
        self.setup_socketio()
        self.init_ai_system()
        
        # 3D simulation data
        self.simulation_data = {
            "vehicles": [],
            "traffic_lights": {},
            "queue_zones": [],
            "ai_decision": "KEEP",
            "timestamp": datetime.now().isoformat(),
            "performance_metrics": {}
        }
        
        # Analytics
        self.frame_count = 0
        self.last_action = 0
        self.start_time = time.time()
        
    def init_ai_system(self):
        """Initialize AI model and vision system"""
        print("🤖 Loading AI model...")
        self.model = PPO.load(MODEL_PATH)
        print("✅ AI model loaded!")
        
        print("👁️  Initializing vision processor...")
        self.processor = VisionProcessor()
        print("✅ Vision system ready!")
        
        print("📹 Opening video streams...")
        self.cap1 = cv2.VideoCapture(VIDEO_PATH_1)
        self.cap2 = cv2.VideoCapture(VIDEO_PATH_2)
        print("✅ Video streams connected!")
        
        print("🌐 Starting SUMO environment...")
        self.env = gym.make('sumo-rl-v0', 
                           net_file=NET_FILE, 
                           route_file=ROUTE_FILE, 
                           use_gui=False,  # Disable 2D GUI for 3D visualization
                           num_seconds=86400, 
                           single_agent=True, 
                           reward_fn='diff-waiting-time')
        self.obs, self.info = self.env.reset()
        print("✅ SUMO environment ready!")
        
    def setup_routes(self):
        @self.app.route('/')
        def dashboard():
            return render_template_string(INTEGRATED_3D_HTML)
        
        @self.app.route('/api/3d_data')
        def get_3d_data():
            return jsonify(self.simulation_data)
        
        @self.app.route('/api/system_status')
        def system_status():
            runtime = time.time() - self.start_time
            return jsonify({
                "status": "active",
                "runtime": runtime,
                "frame_count": self.frame_count,
                "vehicles": len(self.simulation_data["vehicles"]),
                "ai_decision": self.simulation_data["ai_decision"]
            })
    
    def setup_socketio(self):
        @self.socketio.on('connect')
        def handle_connect():
            print('🎮 3D Client connected!')
            emit('system_status', {'status': 'connected'})
        
        @self.socketio.on('request_update')
        def handle_update_request():
            emit('3d_update', self.simulation_data)
    
    def process_video_feeds(self):
        """Process video feeds for queue detection"""
        ret1, frame1 = self.cap1.read()
        ret2, frame2 = self.cap2.read()
        
        if not ret1 or not ret2:
            # Reset videos if they end
            self.cap1.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.cap2.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return [0, 0, 0, 0]
        
        # Process frames for queue detection
        queue_counts1, _ = self.processor.process_frame(frame1, POLYGONS_VIDEO_1)
        queue_counts2, _ = self.processor.process_frame(frame2, POLYGONS_VIDEO_2)
        
        # Ensure we have 4 zones
        if len(queue_counts1) != 2:
            queue_counts1 = [0, 0]
        if len(queue_counts2) != 2:
            queue_counts2 = [0, 0]
            
        return queue_counts1 + queue_counts2
    
    def extract_3d_vehicles(self):
        """Extract vehicle data for 3D visualization"""
        vehicles_3d = []
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            
            for v_id in vehicle_ids:
                pos = traci.vehicle.getPosition(v_id)
                angle = traci.vehicle.getAngle(v_id)
                speed = traci.vehicle.getSpeed(v_id)
                vehicle_type = traci.vehicle.getTypeID(v_id)
                
                # Convert SUMO coordinates to 3D world coordinates
                world_pos = self.sumo_to_world_coords(pos[0], pos[1])
                
                vehicle_data = {
                    "id": v_id,
                    "position": {
                        "x": world_pos[0],
                        "y": 0.5,  # Height above ground
                        "z": world_pos[1]
                    },
                    "rotation": {
                        "x": 0,
                        "y": -angle,  # Convert to Unity rotation
                        "z": 0
                    },
                    "speed": speed * 3.6,  # Convert m/s to km/h
                    "type": vehicle_type,
                    "color": self.get_vehicle_color(vehicle_type),
                    "scale": self.get_vehicle_scale(vehicle_type)
                }
                vehicles_3d.append(vehicle_data)
                
        except Exception as e:
            print(f"Error extracting vehicles: {e}")
        
        return vehicles_3d
    
    def sumo_to_world_coords(self, sumo_x, sumo_y):
        """Convert SUMO coordinates to 3D world coordinates"""
        # Scale and center for better visualization
        world_x = (sumo_x - 250) * 0.05
        world_z = (sumo_y - 250) * 0.05
        return [world_x, world_z]
    
    def get_vehicle_color(self, vehicle_type):
        """Get color based on vehicle type"""
        colors = {
            "passenger": [0.3, 0.7, 1.0, 1.0],    # Blue
            "truck": [1.0, 0.5, 0.2, 1.0],        # Orange
            "bus": [1.0, 1.0, 0.3, 1.0],          # Yellow
            "emergency": [1.0, 0.2, 0.2, 1.0],    # Red
            "default": [0.7, 0.7, 0.7, 1.0]       # Gray
        }
        return colors.get(vehicle_type, colors["default"])
    
    def get_vehicle_scale(self, vehicle_type):
        """Get scale based on vehicle type"""
        scales = {
            "passenger": [1.0, 1.0, 1.0],
            "truck": [1.2, 1.0, 1.8],
            "bus": [1.1, 1.0, 2.2],
            "emergency": [1.0, 1.0, 1.5],
            "default": [1.0, 1.0, 1.0]
        }
        return scales.get(vehicle_type, scales["default"])
    
    def extract_traffic_lights(self):
        """Extract traffic light data"""
        try:
            tls_state = traci.trafficlight.getRedYellowGreenState(TRAFFIC_LIGHT_ID)
            
            return {
                "intersection_id": TRAFFIC_LIGHT_ID,
                "state": tls_state,
                "lights": [
                    {
                        "id": f"light_{i}",
                        "state": state,
                        "color": self.get_light_color(state),
                        "position": self.get_light_position(i)
                    }
                    for i, state in enumerate(tls_state)
                ]
            }
        except:
            return {"intersection_id": TRAFFIC_LIGHT_ID, "state": "rrrr", "lights": []}
    
    def get_light_color(self, state):
        """Convert traffic light state to color"""
        colors = {
            'r': [1.0, 0.0, 0.0],  # Red
            'y': [1.0, 1.0, 0.0],  # Yellow
            'g': [0.0, 1.0, 0.0],  # Green
            'G': [0.0, 1.0, 0.0],  # Green priority
        }
        return colors.get(state.lower(), [0.5, 0.5, 0.5])
    
    def get_light_position(self, light_index):
        """Get 3D position for traffic light"""
        positions = [
            [3, 5, 3],   # NE
            [-3, 5, 3],  # NW
            [-3, 5, -3], # SW
            [3, 5, -3]   # SE
        ]
        return positions[light_index % len(positions)]
    
    def run_simulation(self):
        """Main simulation loop"""
        print("🎮 Starting integrated 3D simulation...")
        
        decision_interval = 150  # Make AI decision every 150 frames (~5 seconds at 30fps)
        
        while True:
            self.frame_count += 1
            
            # Process video feeds for queue detection
            queue_state = self.process_video_feeds()
            
            # AI decision making
            if self.frame_count % decision_interval == 0:
                try:
                    num_lanes = len(queue_state)
                    current_phase = self.obs[num_lanes:]
                    state_for_model = np.concatenate([queue_state, current_phase]).astype(np.float32)
                    self.last_action, _ = self.model.predict(state_for_model, deterministic=True)
                    print(f"🤖 AI Decision: {'SWITCH' if self.last_action == 1 else 'KEEP'} (Frame {self.frame_count})")
                except Exception as e:
                    print(f"AI decision error: {e}")
            
            # Step SUMO simulation
            try:
                self.obs, reward, terminated, truncated, info = self.env.step(self.last_action)
                
                if terminated or truncated:
                    self.obs, self.info = self.env.reset()
                    
            except Exception as e:
                print(f"SUMO step error: {e}")
            
            # Extract 3D data
            vehicles_3d = self.extract_3d_vehicles()
            traffic_lights_3d = self.extract_traffic_lights()
            
            # Update simulation data
            self.simulation_data = {
                "vehicles": vehicles_3d,
                "traffic_lights": traffic_lights_3d,
                "queue_zones": [
                    {"id": "zone1_cam1", "count": queue_state[0], "position": [-5, 0, 5]},
                    {"id": "zone2_cam1", "count": queue_state[1], "position": [5, 0, 5]},
                    {"id": "zone1_cam2", "count": queue_state[2], "position": [-5, 0, -5]},
                    {"id": "zone2_cam2", "count": queue_state[3], "position": [5, 0, -5]},
                ],
                "ai_decision": "SWITCH" if self.last_action == 1 else "KEEP",
                "timestamp": datetime.now().isoformat(),
                "performance_metrics": {
                    "total_vehicles": len(vehicles_3d),
                    "avg_speed": np.mean([v["speed"] for v in vehicles_3d]) if vehicles_3d else 0,
                    "queue_total": sum(queue_state),
                    "runtime": time.time() - self.start_time,
                    "frame_count": self.frame_count
                }
            }
            
            # Broadcast to connected clients
            self.socketio.emit('3d_update', self.simulation_data)
            
            # Control simulation speed
            time.sleep(0.033)  # ~30 FPS
    
    def start_system(self):
        """Start the integrated 3D system"""
        # Start simulation in background thread
        sim_thread = threading.Thread(target=self.run_simulation)
        sim_thread.daemon = True
        sim_thread.start()
        
        print("\n" + "="*60)
        print("🎮 INTEGRATED 3D TRAFFIC MANAGEMENT SYSTEM")
        print("="*60)
        print("🌐 3D Dashboard: http://localhost:5004")
        print("📡 API Endpoint: http://localhost:5004/api/3d_data")
        print("🎯 Features: Real-time 3D visualization + AI traffic control")
        print("="*60)
        
        # Start Flask server
        self.socketio.run(self.app, host='0.0.0.0', port=5004, debug=False)

# 3D Dashboard HTML
INTEGRATED_3D_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎮 Integrated 3D Traffic Management</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #21262d 100%);
            color: #f0f6fc;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
        }
        
        #container {
            position: relative;
            width: 100vw;
            height: 100vh;
        }
        
        #canvas-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        
        .hud {
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: rgba(13, 17, 23, 0.9);
            padding: 25px;
            border-radius: 12px;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(48, 54, 61, 0.5);
            min-width: 280px;
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
        }
        
        .hud h3 {
            color: #58a6ff;
            margin-bottom: 20px;
            font-size: 1.3em;
            font-weight: 600;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 12px 0;
            padding: 10px 0;
            border-bottom: 1px solid rgba(48, 54, 61, 0.3);
        }
        
        .metric:last-child { border-bottom: none; }
        
        .metric-value {
            color: #3fb950;
            font-weight: 600;
            font-family: 'Courier New', monospace;
        }
        
        .ai-status {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(13, 17, 23, 0.9);
            padding: 20px;
            border-radius: 12px;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(48, 54, 61, 0.5);
            text-align: center;
            min-width: 200px;
        }
        
        .ai-decision {
            font-size: 1.5em;
            font-weight: bold;
            margin: 10px 0;
            padding: 15px;
            border-radius: 8px;
            text-transform: uppercase;
        }
        
        .ai-keep {
            background: linear-gradient(135deg, #238636, #2ea043);
            color: white;
        }
        
        .ai-switch {
            background: linear-gradient(135deg, #d1242f, #f85149);
            color: white;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .controls {
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
            background: rgba(13, 17, 23, 0.9);
            padding: 20px;
            border-radius: 12px;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(48, 54, 61, 0.5);
        }
        
        .control-btn {
            background: linear-gradient(135deg, #58a6ff, #1f6feb);
            border: none;
            color: white;
            padding: 10px 16px;
            margin: 5px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s ease;
        }
        
        .control-btn:hover {
            background: linear-gradient(135deg, #1f6feb, #0969da);
            transform: translateY(-2px);
        }
        
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 2000;
            text-align: center;
        }
        
        .spinner {
            border: 4px solid rgba(88, 166, 255, 0.1);
            border-left: 4px solid #58a6ff;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="canvas-container"></div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <h3>Loading 3D Traffic System...</h3>
            <p>Initializing AI and simulation components</p>
        </div>
        
        <div class="hud">
            <h3>🚦 System Status</h3>
            <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:8px;">By Sankalp Gaonkar</div>
            <div class="metric">
                <span>Active Vehicles:</span>
                <span class="metric-value" id="vehicle-count">0</span>
            </div>
            <div class="metric">
                <span>Total Queue:</span>
                <span class="metric-value" id="queue-total">0</span>
            </div>
            <div class="metric">
                <span>Average Speed:</span>
                <span class="metric-value" id="avg-speed">0.0</span> km/h
            </div>
            <div class="metric">
                <span>Runtime:</span>
                <span class="metric-value" id="runtime">0</span>s
            </div>
            <div class="metric">
                <span>Frame Count:</span>
                <span class="metric-value" id="frame-count">0</span>
            </div>
            <div class="metric">
                <span>Connection:</span>
                <span class="metric-value" id="connection-status">Connecting...</span>
            </div>
        </div>
        
        <div class="ai-status">
            <h4>🤖 AI Decision Engine</h4>
            <div class="ai-decision ai-keep" id="ai-decision">KEEP</div>
            <p>Real-time traffic optimization</p>
        </div>
        
        <div class="controls">
            <h4>🎮 3D Controls</h4>
            <button class="control-btn" onclick="resetView()">Reset Camera</button>
            <button class="control-btn" onclick="togglePause()">Pause/Play</button>
            <button class="control-btn" onclick="toggleWireframe()">Wireframe</button>
        </div>
    </div>

    <script>
        // 3D Scene variables
        let scene, camera, renderer;
        let vehicles = {};
        let isPaused = false;
        let wireframeMode = false;
        
        function init3D() {
            // Scene setup
            scene = new THREE.Scene();
            scene.fog = new THREE.Fog(0x0d1117, 30, 100);
            
            // Camera
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(25, 20, 25);
            
            // Renderer
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setClearColor(0x0d1117);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            document.getElementById('canvas-container').appendChild(renderer.domElement);
            
            // Lighting
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(30, 30, 20);
            directionalLight.castShadow = true;
            scene.add(directionalLight);
            
            // Create intersection
            createIntersection();
            
            // Mouse controls
            setupControls();
            
            // Start animation
            animate();
            
            // Hide loading
            document.getElementById('loading').style.display = 'none';
        }
        
        function createIntersection() {
            // Ground
            const groundGeometry = new THREE.PlaneGeometry(80, 80);
            const groundMaterial = new THREE.MeshLambertMaterial({ color: 0x2a2a2a });
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.receiveShadow = true;
            scene.add(ground);
            
            // Roads
            const roadMaterial = new THREE.MeshLambertMaterial({ color: 0x1a1a1a });
            
            // Main roads
            const nsRoad = new THREE.Mesh(new THREE.PlaneGeometry(6, 50), roadMaterial);
            nsRoad.rotation.x = -Math.PI / 2;
            nsRoad.position.y = 0.01;
            scene.add(nsRoad);
            
            const ewRoad = new THREE.Mesh(new THREE.PlaneGeometry(50, 6), roadMaterial);
            ewRoad.rotation.x = -Math.PI / 2;
            ewRoad.position.y = 0.01;
            scene.add(ewRoad);
            
            // Traffic lights
            createTrafficLights();
        }
        
        function createTrafficLights() {
            const positions = [[4, 4], [-4, 4], [-4, -4], [4, -4]];
            
            positions.forEach(pos => {
                const group = new THREE.Group();
                
                // Pole
                const pole = new THREE.Mesh(
                    new THREE.CylinderGeometry(0.1, 0.1, 5),
                    new THREE.MeshLambertMaterial({ color: 0x333333 })
                );
                pole.position.y = 2.5;
                group.add(pole);
                
                // Light housing
                const housing = new THREE.Mesh(
                    new THREE.BoxGeometry(0.4, 1.2, 0.2),
                    new THREE.MeshLambertMaterial({ color: 0x222222 })
                );
                housing.position.y = 5.5;
                group.add(housing);
                
                group.position.set(pos[0], 0, pos[1]);
                scene.add(group);
            });
        }
        
        function setupControls() {
            let mouseDown = false;
            let mouseX = 0, mouseY = 0;
            let cameraAngleX = 0, cameraAngleY = 0;
            let cameraDistance = 40;
            
            renderer.domElement.addEventListener('mousedown', (e) => {
                mouseDown = true;
                mouseX = e.clientX;
                mouseY = e.clientY;
            });
            
            renderer.domElement.addEventListener('mouseup', () => mouseDown = false);
            
            renderer.domElement.addEventListener('mousemove', (e) => {
                if (mouseDown) {
                    cameraAngleX += (e.clientX - mouseX) * 0.01;
                    cameraAngleY += (e.clientY - mouseY) * 0.01;
                    cameraAngleY = Math.max(-Math.PI/2, Math.min(Math.PI/2, cameraAngleY));
                    updateCamera();
                    mouseX = e.clientX;
                    mouseY = e.clientY;
                }
            });
            
            renderer.domElement.addEventListener('wheel', (e) => {
                cameraDistance += e.deltaY * 0.1;
                cameraDistance = Math.max(10, Math.min(80, cameraDistance));
                updateCamera();
            });
            
            function updateCamera() {
                camera.position.x = Math.cos(cameraAngleX) * Math.cos(cameraAngleY) * cameraDistance;
                camera.position.y = Math.sin(cameraAngleY) * cameraDistance;
                camera.position.z = Math.sin(cameraAngleX) * Math.cos(cameraAngleY) * cameraDistance;
                camera.lookAt(0, 0, 0);
            }
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
                    const geometry = new THREE.BoxGeometry(0.8, 0.4, 1.6);
                    const material = new THREE.MeshLambertMaterial({
                        color: new THREE.Color(vehicle.color[0], vehicle.color[1], vehicle.color[2])
                    });
                    vehicles[vehicle.id] = new THREE.Mesh(geometry, material);
                    vehicles[vehicle.id].castShadow = true;
                    scene.add(vehicles[vehicle.id]);
                }
                
                // Update position and rotation
                vehicles[vehicle.id].position.set(
                    vehicle.position.x,
                    vehicle.position.y,
                    vehicle.position.z
                );
                vehicles[vehicle.id].rotation.y = vehicle.rotation.y * Math.PI / 180;
            });
        }
        
        function animate() {
            requestAnimationFrame(animate);
            if (!isPaused) {
                renderer.render(scene, camera);
            }
        }
        
        // Control functions
        function resetView() {
            camera.position.set(25, 20, 25);
            camera.lookAt(0, 0, 0);
        }
        
        function togglePause() {
            isPaused = !isPaused;
        }
        
        function toggleWireframe() {
            wireframeMode = !wireframeMode;
            scene.traverse(child => {
                if (child.material) {
                    child.material.wireframe = wireframeMode;
                }
            });
        }
        
        // Socket.IO
        const socket = io();
        
        socket.on('connect', () => {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').style.color = '#3fb950';
        });
        
        socket.on('3d_update', (data) => {
            if (data.vehicles) {
                updateVehicles(data.vehicles);
            }
            
            // Update UI
            document.getElementById('vehicle-count').textContent = data.vehicles ? data.vehicles.length : 0;
            
            const aiDecision = document.getElementById('ai-decision');
            aiDecision.textContent = data.ai_decision || 'KEEP';
            aiDecision.className = `ai-decision ${data.ai_decision === 'SWITCH' ? 'ai-switch' : 'ai-keep'}`;
            
            if (data.performance_metrics) {
                document.getElementById('queue-total').textContent = data.performance_metrics.queue_total || 0;
                document.getElementById('avg-speed').textContent = (data.performance_metrics.avg_speed || 0).toFixed(1);
                document.getElementById('runtime').textContent = Math.round(data.performance_metrics.runtime || 0);
                document.getElementById('frame-count').textContent = data.performance_metrics.frame_count || 0;
            }
        });
        
        // Window resize
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // Initialize
        init3D();
    </script>
</body>
</html>
"""

def main():
    system = Integrated3DTrafficSystem()
    system.start_system()

if __name__ == '__main__':
    main()