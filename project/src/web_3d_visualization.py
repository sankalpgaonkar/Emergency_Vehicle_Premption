#!/usr/bin/env python3
"""
🌐 Web-based 3D Traffic Visualization
====================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Advanced 3D traffic visualization using Three.js and WebGL
"""

from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
from datetime import datetime
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'web_3d_traffic_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# 3D Visualization HTML with advanced Three.js
WEB_3D_VISUALIZATION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌐 3D Traffic Visualization</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/dat-gui/0.7.9/dat.gui.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
            color: white;
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
            background: rgba(0, 0, 0, 0.8);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
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
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-value {
            color: #3fb950;
            font-weight: bold;
            font-family: 'Courier New', monospace;
        }
        
        .controls {
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        
        .control-button {
            background: linear-gradient(135deg, #58a6ff, #1f6feb);
            border: none;
            color: white;
            padding: 8px 16px;
            margin: 5px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        
        .control-button:hover {
            background: linear-gradient(135deg, #1f6feb, #0969da);
            transform: translateY(-2px);
        }
        
        .legend {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            max-width: 200px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin: 8px 0;
        }
        
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 3px;
            margin-right: 10px;
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
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-left: 4px solid #58a6ff;
            border-radius: 50%;
            width: 50px;
            height: 50px;
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
            <p>Loading 3D Traffic Simulation...</p>
        </div>
        
        <div class="hud">
            <h3>🚦 Traffic Control Center</h3>
            <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:8px;">By Sankalp Gaonkar</div>
            <div class="metric">
                <span>Active Vehicles:</span>
                <span class="metric-value" id="vehicle-count">0</span>
            </div>
            <div class="metric">
                <span>AI Decision:</span>
                <span class="metric-value" id="ai-decision">KEEP</span>
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
                <span>Throughput:</span>
                <span class="metric-value" id="throughput">0</span> veh/h
            </div>
            <div class="metric">
                <span>Connection:</span>
                <span class="metric-value" id="connection-status">Connecting...</span>
            </div>
        </div>
        
        <div class="legend">
            <h4>🎨 Vehicle Types</h4>
            <div class="legend-item">
                <div class="legend-color" style="background: #58a6ff;"></div>
                <span>Cars</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #f9826c;"></div>
                <span>Trucks</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #ffd700;"></div>
                <span>Buses</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #ff4444;"></div>
                <span>Emergency</span>
            </div>
        </div>
        
        <div class="controls">
            <h4>🎮 Camera Controls</h4>
            <button class="control-button" onclick="resetCamera()">Reset View</button>
            <button class="control-button" onclick="toggleAnimation()">Pause/Play</button>
            <button class="control-button" onclick="toggleWireframe()">Wireframe</button>
            <button class="control-button" onclick="toggleFullscreen()">Fullscreen</button>
        </div>
    </div>

    <script>
        // 3D Scene Setup
        let scene, camera, renderer, controls;
        let vehicles = {};
        let roads = [];
        let trafficLights = [];
        let animationPaused = false;
        let wireframeMode = false;
        
        // Initialize Three.js scene
        function init3DScene() {
            // Scene
            scene = new THREE.Scene();
            scene.fog = new THREE.Fog(0x0a0a0a, 50, 200);
            
            // Camera
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(30, 25, 30);
            
            // Renderer
            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setClearColor(0x0a0a0a, 1);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            document.getElementById('canvas-container').appendChild(renderer.domElement);
            
            // Lighting
            setupLighting();
            
            // Create intersection
            createIntersection();
            
            // Camera controls (mouse interaction)
            setupCameraControls();
            
            // Start animation loop
            animate();
            
            // Hide loading screen
            document.getElementById('loading').style.display = 'none';
        }
        
        function setupLighting() {
            // Ambient light
            const ambientLight = new THREE.AmbientLight(0x404040, 0.4);
            scene.add(ambientLight);
            
            // Main directional light (sun)
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(50, 50, 25);
            directionalLight.castShadow = true;
            directionalLight.shadow.mapSize.width = 2048;
            directionalLight.shadow.mapSize.height = 2048;
            scene.add(directionalLight);
            
            // Street lights
            for (let i = 0; i < 4; i++) {
                const streetLight = new THREE.PointLight(0xffaa00, 0.5, 30);
                const angle = (i / 4) * Math.PI * 2;
                streetLight.position.set(
                    Math.cos(angle) * 15,
                    8,
                    Math.sin(angle) * 15
                );
                scene.add(streetLight);
                
                // Street light pole
                const poleGeometry = new THREE.CylinderGeometry(0.2, 0.2, 8);
                const poleMaterial = new THREE.MeshLambertMaterial({ color: 0x333333 });
                const pole = new THREE.Mesh(poleGeometry, poleMaterial);
                pole.position.copy(streetLight.position);
                pole.position.y = 4;
                scene.add(pole);
            }
        }
        
        function createIntersection() {
            // Ground
            const groundGeometry = new THREE.PlaneGeometry(100, 100);
            const groundMaterial = new THREE.MeshLambertMaterial({ color: 0x2a2a2a });
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.receiveShadow = true;
            scene.add(ground);
            
            // Roads
            createRoads();
            
            // Traffic lights
            createTrafficLights();
            
            // Buildings
            createBuildings();
        }
        
        function createRoads() {
            // Main intersection roads
            const roadMaterial = new THREE.MeshLambertMaterial({ color: 0x1a1a1a });
            
            // North-South road
            const nsRoadGeometry = new THREE.PlaneGeometry(8, 60);
            const nsRoad = new THREE.Mesh(nsRoadGeometry, roadMaterial);
            nsRoad.rotation.x = -Math.PI / 2;
            nsRoad.position.y = 0.01;
            scene.add(nsRoad);
            
            // East-West road
            const ewRoadGeometry = new THREE.PlaneGeometry(60, 8);
            const ewRoad = new THREE.Mesh(ewRoadGeometry, roadMaterial);
            ewRoad.rotation.x = -Math.PI / 2;
            ewRoad.position.y = 0.01;
            scene.add(ewRoad);
            
            // Road markings
            createRoadMarkings();
        }
        
        function createRoadMarkings() {
            const markingMaterial = new THREE.MeshLambertMaterial({ color: 0xffffff });
            
            // Center lines
            for (let i = -25; i <= 25; i += 5) {
                if (Math.abs(i) > 4) {
                    const marking = new THREE.Mesh(
                        new THREE.PlaneGeometry(0.2, 2),
                        markingMaterial
                    );
                    marking.rotation.x = -Math.PI / 2;
                    marking.position.set(0, 0.02, i);
                    scene.add(marking);
                    
                    const marking2 = new THREE.Mesh(
                        new THREE.PlaneGeometry(2, 0.2),
                        markingMaterial
                    );
                    marking2.rotation.x = -Math.PI / 2;
                    marking2.position.set(i, 0.02, 0);
                    scene.add(marking2);
                }
            }
        }
        
        function createTrafficLights() {
            const positions = [
                { x: 6, z: 6 },
                { x: -6, z: 6 },
                { x: -6, z: -6 },
                { x: 6, z: -6 }
            ];
            
            positions.forEach((pos, index) => {
                const lightGroup = new THREE.Group();
                
                // Pole
                const poleGeometry = new THREE.CylinderGeometry(0.1, 0.1, 4);
                const poleMaterial = new THREE.MeshLambertMaterial({ color: 0x333333 });
                const pole = new THREE.Mesh(poleGeometry, poleMaterial);
                pole.position.y = 2;
                lightGroup.add(pole);
                
                // Light housing
                const housingGeometry = new THREE.BoxGeometry(0.5, 1.5, 0.3);
                const housingMaterial = new THREE.MeshLambertMaterial({ color: 0x222222 });
                const housing = new THREE.Mesh(housingGeometry, housingMaterial);
                housing.position.y = 4.5;
                lightGroup.add(housing);
                
                // Individual lights
                const lightColors = [0xff0000, 0xffff00, 0x00ff00]; // Red, Yellow, Green
                lightColors.forEach((color, i) => {
                    const lightGeometry = new THREE.SphereGeometry(0.15);
                    const lightMaterial = new THREE.MeshLambertMaterial({ 
                        color: color,
                        emissive: color,
                        emissiveIntensity: 0.2
                    });
                    const light = new THREE.Mesh(lightGeometry, lightMaterial);
                    light.position.set(0, 4.5 + (i - 1) * 0.4, 0.2);
                    lightGroup.add(light);
                });
                
                lightGroup.position.set(pos.x, 0, pos.z);
                scene.add(lightGroup);
                trafficLights.push(lightGroup);
            });
        }
        
        function createBuildings() {
            const buildingPositions = [
                { x: 20, z: 20, w: 8, h: 12, d: 8 },
                { x: -20, z: 20, w: 6, h: 8, d: 6 },
                { x: -20, z: -20, w: 10, h: 15, d: 10 },
                { x: 20, z: -20, w: 7, h: 10, d: 7 }
            ];
            
            buildingPositions.forEach(building => {
                const geometry = new THREE.BoxGeometry(building.w, building.h, building.d);
                const material = new THREE.MeshLambertMaterial({ 
                    color: new THREE.Color().setHSL(0.6, 0.2, 0.3 + Math.random() * 0.2)
                });
                const mesh = new THREE.Mesh(geometry, material);
                mesh.position.set(building.x, building.h / 2, building.z);
                mesh.castShadow = true;
                scene.add(mesh);
            });
        }
        
        function setupCameraControls() {
            let mouseDown = false;
            let mouseX = 0;
            let mouseY = 0;
            let cameraAngleX = 0;
            let cameraAngleY = 0;
            let cameraDistance = 50;
            
            renderer.domElement.addEventListener('mousedown', (e) => {
                mouseDown = true;
                mouseX = e.clientX;
                mouseY = e.clientY;
            });
            
            renderer.domElement.addEventListener('mouseup', () => {
                mouseDown = false;
            });
            
            renderer.domElement.addEventListener('mousemove', (e) => {
                if (mouseDown) {
                    const deltaX = e.clientX - mouseX;
                    const deltaY = e.clientY - mouseY;
                    
                    cameraAngleX += deltaX * 0.01;
                    cameraAngleY += deltaY * 0.01;
                    cameraAngleY = Math.max(-Math.PI/2, Math.min(Math.PI/2, cameraAngleY));
                    
                    updateCameraPosition();
                    
                    mouseX = e.clientX;
                    mouseY = e.clientY;
                }
            });
            
            renderer.domElement.addEventListener('wheel', (e) => {
                cameraDistance += e.deltaY * 0.1;
                cameraDistance = Math.max(10, Math.min(100, cameraDistance));
                updateCameraPosition();
            });
            
            function updateCameraPosition() {
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
                    // Create new vehicle
                    const geometry = new THREE.BoxGeometry(1, 0.5, 2);
                    const material = new THREE.MeshLambertMaterial({ 
                        color: new THREE.Color(vehicle.color[0], vehicle.color[1], vehicle.color[2])
                    });
                    const mesh = new THREE.Mesh(geometry, material);
                    mesh.castShadow = true;
                    vehicles[vehicle.id] = mesh;
                    scene.add(mesh);
                }
                
                // Update position and rotation
                const mesh = vehicles[vehicle.id];
                mesh.position.set(
                    vehicle.position.x,
                    vehicle.position.y,
                    vehicle.position.z
                );
                mesh.rotation.y = vehicle.rotation.y * Math.PI / 180;
            });
        }
        
        function animate() {
            requestAnimationFrame(animate);
            
            if (!animationPaused) {
                // Rotate traffic lights
                trafficLights.forEach((light, index) => {
                    light.rotation.y += 0.001;
                });
                
                renderer.render(scene, camera);
            }
        }
        
        // Control functions
        function resetCamera() {
            camera.position.set(30, 25, 30);
            camera.lookAt(0, 0, 0);
        }
        
        function toggleAnimation() {
            animationPaused = !animationPaused;
        }
        
        function toggleWireframe() {
            wireframeMode = !wireframeMode;
            scene.traverse((child) => {
                if (child.material) {
                    child.material.wireframe = wireframeMode;
                }
            });
        }
        
        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }
        
        // Socket.IO connection
        const socket = io();
        
        socket.on('connect', function() {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').style.color = '#3fb950';
        });
        
        socket.on('disconnect', function() {
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('connection-status').style.color = '#f85149';
        });
        
        socket.on('3d_data_update', function(data) {
            if (data.vehicles) {
                updateVehicles(data.vehicles);
            }
            
            // Update HUD
            document.getElementById('vehicle-count').textContent = data.vehicles ? data.vehicles.length : 0;
            document.getElementById('ai-decision').textContent = data.ai_decision || 'KEEP';
            
            if (data.performance_metrics) {
                document.getElementById('queue-total').textContent = data.performance_metrics.queue_total || 0;
                document.getElementById('avg-speed').textContent = (data.performance_metrics.avg_speed || 0).toFixed(1);
                document.getElementById('throughput').textContent = Math.round(data.performance_metrics.throughput || 0);
            }
        });
        
        // Handle window resize
        window.addEventListener('resize', function() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // Initialize when page loads
        window.addEventListener('load', function() {
            init3DScene();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def web_3d_dashboard():
    return render_template_string(WEB_3D_VISUALIZATION_HTML)

@app.route('/api/3d_status')
def status_3d():
    return jsonify({
        "status": "active",
        "visualization": "web_3d",
        "features": ["three.js", "webgl", "real-time", "interactive"]
    })

@socketio.on('connect')
def handle_connect():
    print('🌐 Web 3D client connected!')
    emit('connected', {'status': 'connected'})

def simulate_traffic_data():
    """Simulate traffic data for demonstration"""
    while True:
        # Generate sample 3D traffic data
        vehicles = []
        for i in range(np.random.randint(5, 15)):
            vehicle = {
                "id": f"vehicle_{i}",
                "position": {
                    "x": np.random.uniform(-20, 20),
                    "y": 0.5,
                    "z": np.random.uniform(-20, 20)
                },
                "rotation": {
                    "x": 0,
                    "y": np.random.uniform(0, 360),
                    "z": 0
                },
                "speed": np.random.uniform(20, 60),
                "type": np.random.choice(["passenger", "truck", "bus"]),
                "color": [
                    np.random.uniform(0.2, 1.0),
                    np.random.uniform(0.2, 1.0),
                    np.random.uniform(0.2, 1.0),
                    1.0
                ]
            }
            vehicles.append(vehicle)
        
        data = {
            "vehicles": vehicles,
            "ai_decision": np.random.choice(["KEEP", "SWITCH"]),
            "performance_metrics": {
                "queue_total": np.random.randint(0, 20),
                "avg_speed": np.random.uniform(25, 55),
                "throughput": np.random.uniform(100, 500)
            }
        }
        
        socketio.emit('3d_data_update', data)
        time.sleep(1)  # Update every second

def main():
    # Start simulation thread
    sim_thread = threading.Thread(target=simulate_traffic_data)
    sim_thread.daemon = True
    sim_thread.start()
    
    print("🌐 Starting Web 3D Traffic Visualization...")
    print("🎮 Dashboard: http://localhost:5003")
    print("🎯 Features: Interactive 3D scene, real-time updates, camera controls")
    
    socketio.run(app, host='0.0.0.0', port=5003, debug=False)

if __name__ == '__main__':
    main()