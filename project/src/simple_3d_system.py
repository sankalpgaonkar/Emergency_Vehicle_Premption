#!/usr/bin/env python3
"""
🎮 Simple 3D Traffic Visualization System
========================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Lightweight 3D visualization with simulated data for immediate results
"""

from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
from datetime import datetime
import numpy as np
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'simple_3d_traffic_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global simulation state
simulation_running = True
simulation_data = {
    "vehicles": [],
    "ai_decision": "KEEP",
    "timestamp": datetime.now().isoformat(),
    "performance_metrics": {
        "total_vehicles": 0,
        "avg_speed": 0,
        "queue_total": 0,
        "runtime": 0,
        "frame_count": 0
    }
}

class Simple3DTrafficSystem:
    def __init__(self):
        self.frame_count = 0
        self.start_time = time.time()
        self.vehicle_id_counter = 0
        self.vehicles = {}
        self.setup_routes()
        self.setup_socketio()
        
    def setup_routes(self):
        @app.route('/')
        def dashboard():
            return render_template_string(SIMPLE_3D_HTML)
        
        @app.route('/api/3d_data')
        def get_3d_data():
            return jsonify(simulation_data)
        
        @app.route('/api/status')
        def status():
            return jsonify({
                "status": "running",
                "vehicles": len(simulation_data["vehicles"]),
                "runtime": time.time() - self.start_time
            })
    
    def setup_socketio(self):
        @socketio.on('connect')
        def handle_connect():
            print('🎮 3D Client connected!')
            emit('system_ready', {'status': 'connected'})
        
        @socketio.on('disconnect')
        def handle_disconnect():
            print('🔌 3D Client disconnected')
    
    def generate_vehicle_data(self):
        """Generate realistic vehicle movement data"""
        global simulation_data
        
        # Add new vehicles occasionally
        if random.random() < 0.1 and len(self.vehicles) < 15:
            self.vehicle_id_counter += 1
            vehicle_id = f"vehicle_{self.vehicle_id_counter}"
            
            # Random spawn position on road edges
            spawn_positions = [
                {"x": -20, "z": random.uniform(-2, 2)},  # West entrance
                {"x": 20, "z": random.uniform(-2, 2)},   # East entrance
                {"x": random.uniform(-2, 2), "z": -20}, # South entrance
                {"x": random.uniform(-2, 2), "z": 20}   # North entrance
            ]
            
            spawn = random.choice(spawn_positions)
            vehicle_type = random.choice(["passenger", "truck", "bus"])
            
            self.vehicles[vehicle_id] = {
                "id": vehicle_id,
                "position": {"x": spawn["x"], "y": 0.5, "z": spawn["z"]},
                "rotation": {"x": 0, "y": random.uniform(0, 360), "z": 0},
                "speed": random.uniform(20, 60),
                "type": vehicle_type,
                "color": self.get_vehicle_color(vehicle_type),
                "scale": self.get_vehicle_scale(vehicle_type),
                "target": {"x": -spawn["x"], "z": -spawn["z"]},  # Drive to opposite side
                "active": True
            }
        
        # Update existing vehicles
        vehicles_to_remove = []
        for vehicle_id, vehicle in self.vehicles.items():
            if not vehicle["active"]:
                continue
                
            # Move vehicle towards target
            dx = vehicle["target"]["x"] - vehicle["position"]["x"]
            dz = vehicle["target"]["z"] - vehicle["position"]["z"]
            distance = np.sqrt(dx*dx + dz*dz)
            
            if distance > 1.0:
                # Normalize direction and apply speed
                speed_factor = 0.1
                vehicle["position"]["x"] += (dx / distance) * speed_factor
                vehicle["position"]["z"] += (dz / distance) * speed_factor
                
                # Update rotation to face movement direction
                vehicle["rotation"]["y"] = np.degrees(np.arctan2(dx, dz))
            else:
                # Vehicle reached destination, mark for removal
                vehicles_to_remove.append(vehicle_id)
        
        # Remove vehicles that reached their destination
        for vehicle_id in vehicles_to_remove:
            del self.vehicles[vehicle_id]
        
        # Convert to list for JSON serialization
        vehicles_list = list(self.vehicles.values())
        
        # Generate AI decision (switch every 10 seconds)
        ai_decision = "SWITCH" if (self.frame_count // 300) % 2 == 1 else "KEEP"
        
        # Generate queue data
        queue_counts = [
            random.randint(0, 5),  # Zone 1
            random.randint(0, 4),  # Zone 2
            random.randint(0, 3),  # Zone 3
            random.randint(0, 6)   # Zone 4
        ]
        
        # Update global simulation data
        simulation_data.update({
            "vehicles": vehicles_list,
            "ai_decision": ai_decision,
            "timestamp": datetime.now().isoformat(),
            "performance_metrics": {
                "total_vehicles": len(vehicles_list),
                "avg_speed": np.mean([v["speed"] for v in vehicles_list]) if vehicles_list else 0,
                "queue_total": sum(queue_counts),
                "runtime": time.time() - self.start_time,
                "frame_count": self.frame_count
            }
        })
        
        return simulation_data
    
    def get_vehicle_color(self, vehicle_type):
        """Get color based on vehicle type"""
        colors = {
            "passenger": [0.3, 0.7, 1.0, 1.0],    # Blue
            "truck": [1.0, 0.5, 0.2, 1.0],        # Orange
            "bus": [1.0, 1.0, 0.3, 1.0],          # Yellow
            "emergency": [1.0, 0.2, 0.2, 1.0],    # Red
        }
        return colors.get(vehicle_type, [0.7, 0.7, 0.7, 1.0])
    
    def get_vehicle_scale(self, vehicle_type):
        """Get scale based on vehicle type"""
        scales = {
            "passenger": [1.0, 1.0, 1.0],
            "truck": [1.2, 1.0, 1.8],
            "bus": [1.1, 1.0, 2.2],
            "emergency": [1.0, 1.0, 1.5],
        }
        return scales.get(vehicle_type, [1.0, 1.0, 1.0])
    
    def run_simulation(self):
        """Main simulation loop"""
        print("🎮 Starting simple 3D simulation...")
        
        while simulation_running:
            self.frame_count += 1
            
            # Generate new simulation data
            data = self.generate_vehicle_data()
            
            # Broadcast to connected clients
            socketio.emit('3d_update', data)
            
            # Control simulation speed (30 FPS)
            time.sleep(0.033)
    
    def start_system(self):
        """Start the simple 3D system"""
        print("\n" + "="*60)
        print("🎮 SIMPLE 3D TRAFFIC VISUALIZATION")
        print("="*60)
        print("🌐 Dashboard: http://localhost:5005")
        print("🎯 Features: Instant 3D visualization with simulated traffic")
        print("⚡ Status: Ready to launch!")
        print("="*60)
        
        # Start simulation in background thread
        sim_thread = threading.Thread(target=self.run_simulation)
        sim_thread.daemon = True
        sim_thread.start()
        
        # Start Flask server
        socketio.run(app, host='0.0.0.0', port=5005, debug=False)

# Simple 3D HTML with faster loading
SIMPLE_3D_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎮 Simple 3D Traffic System</title>
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
            padding: 20px;
            border-radius: 12px;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(48, 54, 61, 0.5);
            min-width: 250px;
        }
        
        .hud h3 {
            color: #58a6ff;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            padding: 8px 0;
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
            min-width: 180px;
        }
        
        .ai-decision {
            font-size: 1.3em;
            font-weight: bold;
            margin: 10px 0;
            padding: 12px;
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
            padding: 15px;
            border-radius: 12px;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(48, 54, 61, 0.5);
        }
        
        .control-btn {
            background: linear-gradient(135deg, #58a6ff, #1f6feb);
            border: none;
            color: white;
            padding: 8px 14px;
            margin: 3px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        
        .control-btn:hover {
            background: linear-gradient(135deg, #1f6feb, #0969da);
            transform: translateY(-2px);
        }
        
        .status-ready {
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(35, 134, 54, 0.9);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="canvas-container"></div>
        
        <div class="hud">
            <h3>🚦 Traffic Control</h3>
            <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:8px;">By Sankalp Gaonkar</div>
            <div class="metric">
                <span>Vehicles:</span>
                <span class="metric-value" id="vehicle-count">0</span>
            </div>
            <div class="metric">
                <span>Queue Total:</span>
                <span class="metric-value" id="queue-total">0</span>
            </div>
            <div class="metric">
                <span>Avg Speed:</span>
                <span class="metric-value" id="avg-speed">0.0</span> km/h
            </div>
            <div class="metric">
                <span>Runtime:</span>
                <span class="metric-value" id="runtime">0</span>s
            </div>
            <div class="metric">
                <span>Status:</span>
                <span class="metric-value" id="connection-status">Connecting...</span>
            </div>
        </div>
        
        <div class="ai-status">
            <h4>🤖 AI Engine</h4>
            <div class="ai-decision ai-keep" id="ai-decision">KEEP</div>
        </div>
        
        <div class="controls">
            <h4>🎮 Controls</h4>
            <button class="control-btn" onclick="resetView()">Reset</button>
            <button class="control-btn" onclick="togglePause()">Pause</button>
            <button class="control-btn" onclick="toggleWireframe()">Wire</button>
        </div>
        
        <div class="status-ready">
            ✅ System Ready
        </div>
    </div>

    <script>
        // 3D Scene variables
        let scene, camera, renderer;
        let vehicles = {};
        let isPaused = false;
        let wireframeMode = false;
        
        function init3D() {
            console.log('🎮 Initializing 3D scene...');
            
            // Scene setup
            scene = new THREE.Scene();
            scene.fog = new THREE.Fog(0x0d1117, 20, 80);
            
            // Camera
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(20, 15, 20);
            camera.lookAt(0, 0, 0);
            
            // Renderer
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setClearColor(0x0d1117);
            renderer.shadowMap.enabled = true;
            document.getElementById('canvas-container').appendChild(renderer.domElement);
            
            // Lighting
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(20, 20, 10);
            directionalLight.castShadow = true;
            scene.add(directionalLight);
            
            // Create intersection
            createIntersection();
            
            // Mouse controls
            setupControls();
            
            // Start animation
            animate();
            
            console.log('✅ 3D scene ready!');
        }
        
        function createIntersection() {
            // Ground
            const groundGeometry = new THREE.PlaneGeometry(60, 60);
            const groundMaterial = new THREE.MeshLambertMaterial({ color: 0x2a2a2a });
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.receiveShadow = true;
            scene.add(ground);
            
            // Roads
            const roadMaterial = new THREE.MeshLambertMaterial({ color: 0x1a1a1a });
            
            // North-South road
            const nsRoad = new THREE.Mesh(new THREE.PlaneGeometry(4, 40), roadMaterial);
            nsRoad.rotation.x = -Math.PI / 2;
            nsRoad.position.y = 0.01;
            scene.add(nsRoad);
            
            // East-West road
            const ewRoad = new THREE.Mesh(new THREE.PlaneGeometry(40, 4), roadMaterial);
            ewRoad.rotation.x = -Math.PI / 2;
            ewRoad.position.y = 0.01;
            scene.add(ewRoad);
            
            // Simple traffic lights
            createTrafficLights();
        }
        
        function createTrafficLights() {
            const positions = [[3, 3], [-3, 3], [-3, -3], [3, -3]];
            
            positions.forEach(pos => {
                const group = new THREE.Group();
                
                // Pole
                const pole = new THREE.Mesh(
                    new THREE.CylinderGeometry(0.05, 0.05, 3),
                    new THREE.MeshLambertMaterial({ color: 0x333333 })
                );
                pole.position.y = 1.5;
                group.add(pole);
                
                // Light
                const light = new THREE.Mesh(
                    new THREE.SphereGeometry(0.2),
                    new THREE.MeshLambertMaterial({ color: 0x00ff00, emissive: 0x004400 })
                );
                light.position.y = 3.2;
                group.add(light);
                
                group.position.set(pos[0], 0, pos[1]);
                scene.add(group);
            });
        }
        
        function setupControls() {
            let mouseDown = false;
            let mouseX = 0, mouseY = 0;
            let cameraAngleX = 0.8, cameraAngleY = 0.3;
            let cameraDistance = 30;
            
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
                cameraDistance = Math.max(5, Math.min(60, cameraDistance));
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
                    const geometry = new THREE.BoxGeometry(0.6, 0.3, 1.2);
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
            camera.position.set(20, 15, 20);
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
            console.log('🌐 Connected to server');
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').style.color = '#3fb950';
        });
        
        socket.on('system_ready', () => {
            console.log('✅ System ready');
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
            }
        });
        
        // Window resize
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // Initialize immediately
        console.log('🚀 Starting 3D system...');
        init3D();
    </script>
</body>
</html>
"""

def main():
    system = Simple3DTrafficSystem()
    system.start_system()

if __name__ == '__main__':
    main()