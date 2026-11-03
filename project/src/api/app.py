"""
🚦 AI Traffic Management System - Web API Server
===============================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Real-time traffic control API with modern web dashboard
"""

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO, emit
from stable_baselines3 import PPO
import numpy as np
from datetime import datetime
import json
import time

print("🚀 Starting AI Traffic Management API Server...")

# --- Load AI Model ---
try:
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    MODEL_PATH = str(PROJECT_ROOT / "models" / "ppo_traffic_model_v2.zip")
    model = PPO.load(MODEL_PATH)
    print("✅ AI model loaded successfully.")
except Exception as e:
    print(f"❌ Error loading AI model: {e}")
    model = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'traffic_ai_secret_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global statistics
stats = {
    'connections': 0,
    'predictions': 0,
    'start_time': time.time(),
    'last_prediction': None,
    'current_queues': [],
    'last_action': 'KEEP'
}

# Modern HTML Dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚦 AI Traffic Management Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap');
        
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }
        
        body {
            font-family: 'Rajdhani', sans-serif;
            background: 
                radial-gradient(ellipse at top, rgba(13, 110, 253, 0.15) 0%, transparent 70%),
                radial-gradient(ellipse at bottom, rgba(25, 135, 84, 0.15) 0%, transparent 70%),
                linear-gradient(135deg, #0d1117 0%, #161b22 25%, #21262d 50%, #30363d 75%, #161b22 100%);
            color: #f0f6fc;
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                repeating-linear-gradient(
                    90deg,
                    transparent,
                    transparent 2px,
                    rgba(0, 255, 65, 0.03) 2px,
                    rgba(0, 255, 65, 0.03) 4px
                );
            pointer-events: none;
            z-index: 1;
        }
        
        .header {
            background: linear-gradient(135deg, rgba(13, 17, 23, 0.95) 0%, rgba(22, 27, 34, 0.9) 100%);
            padding: 40px 20px;
            text-align: center;
            border-bottom: 1px solid rgba(48, 54, 61, 0.8);
            backdrop-filter: blur(20px) saturate(180%);
            position: relative;
            z-index: 2;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, 
                transparent 0%, 
                rgba(0, 255, 65, 0.1) 25%, 
                rgba(0, 212, 255, 0.1) 50%, 
                rgba(255, 0, 128, 0.1) 75%, 
                transparent 100%);
            animation: headerGlow 4s ease-in-out infinite alternate;
        }
        
        .header h1 {
            font-family: 'Orbitron', monospace;
            font-size: 3.2em;
            font-weight: 700;
            margin-bottom: 15px;
            background: linear-gradient(135deg, #58a6ff 0%, #1f6feb 25%, #0969da 50%, #0550ae 75%, #033d8b 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            position: relative;
            z-index: 3;
            letter-spacing: 2px;
        }
        
        .header p {
            font-size: 1.2em;
            font-weight: 400;
            opacity: 0.8;
            letter-spacing: 1px;
            position: relative;
            z-index: 3;
            color: #7d8590;
        }
        
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            padding: 30px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 2;
        }
        
        .card {
            background: linear-gradient(135deg, 
                rgba(22, 27, 34, 0.8) 0%, 
                rgba(33, 38, 45, 0.6) 50%, 
                rgba(48, 54, 61, 0.4) 100%);
            border-radius: 16px;
            padding: 28px;
            backdrop-filter: blur(16px) saturate(180%);
            border: 1px solid rgba(48, 54, 61, 0.5);
            box-shadow: 
                0 16px 40px rgba(0, 0, 0, 0.4),
                0 8px 16px rgba(0, 0, 0, 0.2),
                inset 0 1px 0 rgba(240, 246, 252, 0.1);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(0, 255, 65, 0.1), 
                transparent);
            transition: left 0.6s ease;
        }
        
        .card:hover {
            transform: translateY(-8px);
            box-shadow: 
                0 24px 48px rgba(0, 0, 0, 0.5),
                0 12px 24px rgba(88, 166, 255, 0.15),
                0 0 0 1px rgba(88, 166, 255, 0.2),
                inset 0 1px 0 rgba(240, 246, 252, 0.15);
            border-color: rgba(88, 166, 255, 0.3);
        }
        
        .card:hover::before {
            left: 100%;
        }
        
        .card h3 {
            font-family: 'Orbitron', monospace;
            color: #58a6ff;
            margin-bottom: 24px;
            font-size: 1.3em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: relative;
        }
        
        .card h3::after {
            content: '';
            position: absolute;
            bottom: -8px;
            left: 0;
            width: 40px;
            height: 2px;
            background: linear-gradient(90deg, #58a6ff, transparent);
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 16px 0;
            padding: 16px 18px;
            background: linear-gradient(135deg, 
                rgba(13, 17, 23, 0.6) 0%, 
                rgba(22, 27, 34, 0.4) 100%);
            border-radius: 10px;
            border: 1px solid rgba(48, 54, 61, 0.3);
            transition: all 0.2s ease;
        }
        
        .metric:hover {
            background: linear-gradient(135deg, 
                rgba(88, 166, 255, 0.08) 0%, 
                rgba(22, 27, 34, 0.6) 100%);
            border-color: rgba(88, 166, 255, 0.2);
        }
        
        .metric-value {
            font-weight: 600;
            font-size: 1.1em;
            color: #58a6ff;
            font-family: 'Orbitron', monospace;
        }
        
        .status-indicator {
            display: inline-block;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 10px currentColor;
            animation: statusPulse 2s ease-in-out infinite;
        }
        
        .status-online { 
            background: radial-gradient(circle, #3fb950, #238636);
            box-shadow: 0 0 12px rgba(63, 185, 80, 0.4);
        }
        
        .status-offline { 
            background: radial-gradient(circle, #f85149, #da3633);
            box-shadow: 0 0 12px rgba(248, 81, 73, 0.4);
        }
        
        .action-display {
            text-align: center;
            padding: 30px;
            font-family: 'Orbitron', monospace;
            font-size: 2.2em;
            font-weight: 700;
            border-radius: 15px;
            margin: 15px 0;
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 2px;
            transition: all 0.4s ease;
        }
        
        .action-keep {
            background: linear-gradient(135deg, #238636, #2ea043, #3fb950);
            color: white;
            box-shadow: 0 8px 24px rgba(35, 134, 54, 0.3);
        }
        
        .action-switch {
            background: linear-gradient(135deg, #d1242f, #f85149, #ff7b72);
            color: white;
            box-shadow: 0 8px 24px rgba(209, 36, 47, 0.3);
            animation: switchPulse 1.5s ease-in-out infinite alternate;
        }
        
        .queue-bar {
            height: 25px;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 15px;
            overflow: hidden;
            margin: 8px 0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            position: relative;
        }
        
        .queue-fill {
            height: 100%;
            background: linear-gradient(90deg, 
                #3fb950 0%, 
                #58a6ff 25%, 
                #f9826c 50%, 
                #a5a5a5 75%, 
                #3fb950 100%);
            background-size: 200% 100%;
            transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
            animation: queueFlow 4s linear infinite;
            border-radius: 12px;
            box-shadow: 0 0 12px rgba(88, 166, 255, 0.2);
        }
        
        .timestamp {
            font-size: 0.95em;
            opacity: 0.8;
            text-align: center;
            margin-top: 15px;
            font-weight: 300;
            letter-spacing: 1px;
        }
        
        @keyframes gradientShift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }
        
        @keyframes headerGlow {
            0% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        @keyframes statusPulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.8; }
        }
        
        @keyframes switchPulse {
            0% { box-shadow: 0 0 20px rgba(253, 126, 20, 0.4); }
            100% { box-shadow: 0 0 30px rgba(253, 126, 20, 0.8), 0 0 40px rgba(255, 193, 7, 0.4); }
        }
        
        @keyframes queueFlow {
            0% { background-position: 0% 0%; }
            100% { background-position: 200% 0%; }
        }
        
        .chart-container {
            background: linear-gradient(135deg, rgba(0, 0, 0, 0.3), rgba(26, 26, 46, 0.2));
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.3);
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #00ff41, #00d4ff);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg, #00d4ff, #ff0080);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Traffic Management System</h1>
        <p>Real-time Traffic Optimization & Analytics Dashboard • Developed by Sankalp Gaonkar</p>
    </div>
    
    <div class="dashboard">
        <div class="card">
            <h3>System Status</h3>
            <div class="metric">
                <span>Connection Status:</span>
                <span><span id="status-indicator" class="status-indicator status-offline"></span><span id="connection-status">Disconnected</span></span>
            </div>
            <div class="metric">
                <span>Predictions Made:</span>
                <span class="metric-value" id="predictions-count">0</span>
            </div>
            <div class="metric">
                <span>Uptime:</span>
                <span class="metric-value" id="uptime">00:00:00</span>
            </div>
            <div class="metric">
                <span>Last Prediction:</span>
                <span class="metric-value" id="last-prediction">Never</span>
            </div>
            <div class="metric">
                <span>Live System:</span>
                <span class="metric-value" id="live-system-status">Disconnected</span>
            </div>
        </div>
        
        <div class="card">
            <h3>Current Action</h3>
            <div id="current-action" class="action-display action-keep">
                KEEP CURRENT PHASE
            </div>
            <div class="timestamp" id="action-timestamp">
                Waiting for data...
            </div>
        </div>
        
        <div class="card">
            <h3>Traffic Queues</h3>
            <div id="queue-display">
                <div class="metric">
                    <span>Zone 1:</span>
                    <div class="queue-bar"><div class="queue-fill" style="width: 0%"></div></div>
                    <span class="metric-value">0 vehicles</span>
                </div>
                <div class="metric">
                    <span>Zone 2:</span>
                    <div class="queue-bar"><div class="queue-fill" style="width: 0%"></div></div>
                    <span class="metric-value">0 vehicles</span>
                </div>
                <div class="metric">
                    <span>Zone 3:</span>
                    <div class="queue-bar"><div class="queue-fill" style="width: 0%"></div></div>
                    <span class="metric-value">0 vehicles</span>
                </div>
                <div class="metric">
                    <span>Zone 4:</span>
                    <div class="queue-bar"><div class="queue-fill" style="width: 0%"></div></div>
                    <span class="metric-value">0 vehicles</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>Performance Analytics</h3>
            <div class="chart-container">
                <canvas id="performance-chart" width="400" height="200"></canvas>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let performanceData = [];
        let chart;
        
        // Initialize chart
        const ctx = document.getElementById('performance-chart').getContext('2d');
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Total Queue Length',
                    data: [],
                    borderColor: '#00ff41',
                    backgroundColor: 'rgba(0, 255, 65, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: { color: '#ffffff' } }
                },
                scales: {
                    x: { ticks: { color: '#ffffff' } },
                    y: { ticks: { color: '#ffffff' } }
                }
            }
        });
        
        socket.on('connect', function() {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('status-indicator').className = 'status-indicator status-online';
            console.log('Connected to AI Traffic Server');
        });
        
        socket.on('disconnect', function() {
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('status-indicator').className = 'status-indicator status-offline';
        });
        
        socket.on('traffic_update', function(data) {
            console.log('Received traffic update:', data);
            updateDashboard(data);
        });
        
        function updateDashboard(data) {
            // Update live system status
            document.getElementById('live-system-status').textContent = 'Connected';
            document.getElementById('live-system-status').style.color = '#00ff41';
            
            // Update action display
            const actionElement = document.getElementById('current-action');
            const actionClass = data.action === 'SWITCH' ? 'action-switch' : 'action-keep';
            actionElement.className = `action-display ${actionClass}`;
            actionElement.textContent = data.action === 'SWITCH' ? 'SWITCH TRAFFIC LIGHT' : 'KEEP CURRENT PHASE';
            
            // Update queues
            const queueDisplay = document.getElementById('queue-display');
            const maxQueue = Math.max(...data.queues, 1);
            
            data.queues.forEach((count, index) => {
                const percentage = (count / maxQueue) * 100;
                const metrics = queueDisplay.children[index];
                if (metrics) {
                    const bar = metrics.querySelector('.queue-fill');
                    const value = metrics.querySelector('.metric-value');
                    if (bar && value) {
                        bar.style.width = percentage + '%';
                        value.textContent = count + ' vehicles';
                    }
                }
            });
            
            // Update chart
            const now = new Date().toLocaleTimeString();
            const totalQueue = data.queues.reduce((a, b) => a + b, 0);
            
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(totalQueue);
            
            if (chart.data.labels.length > 20) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            
            chart.update('none');
            
            // Update timestamp
            document.getElementById('action-timestamp').textContent = 
                'Updated: ' + new Date().toLocaleString();
        }
        
        // Update stats periodically
        setInterval(() => {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('predictions-count').textContent = data.predictions;
                    document.getElementById('uptime').textContent = formatUptime(data.uptime);
                    document.getElementById('last-prediction').textContent = 
                        data.last_prediction || 'Never';
                });
        }, 1000);
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Serve the modern dashboard"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/stats')
def get_stats():
    """API endpoint for system statistics"""
    current_stats = stats.copy()
    current_stats['uptime'] = time.time() - stats['start_time']
    return jsonify(current_stats)

@app.route('/api/update_traffic', methods=['POST'])
def update_traffic():
    """Receive traffic data from live analysis system"""
    try:
        data = request.get_json()
        
        if data and 'queues' in data and 'action' in data:
            # Update global stats
            stats['current_queues'] = data['queues']
            stats['last_action'] = data['action']
            stats['last_prediction'] = datetime.now().strftime('%H:%M:%S')
            
            # Broadcast to all connected dashboard clients
            socketio.emit('traffic_update', {
                'action': data['action'],
                'queues': data['queues'],
                'timestamp': datetime.now().isoformat()
            })
            
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid data format'}), 400
            
    except Exception as e:
        print(f"❌ Error updating traffic data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    stats['connections'] += 1
    print(f'🌐 Web client connected! Total connections: {stats["connections"]}')
    emit('connection_confirmed', {'status': 'connected', 'timestamp': datetime.now().isoformat()})

@socketio.on('get_ai_action')
def handle_ai_request(data):
    """Handle AI prediction requests with enhanced logging"""
    if model is None:
        print("❌ Model not loaded, cannot perform prediction.")
        emit('error', {'message': 'AI model not available'})
        return

    try:
        # Extract state data
        state = np.array(data['queues'], dtype=np.float32)
        
        # Make prediction
        action, _ = model.predict(state, deterministic=True)
        action_int = int(action)
        action_str = "SWITCH" if action_int == 1 else "KEEP"
        
        # Update statistics
        stats['predictions'] += 1
        stats['last_prediction'] = datetime.now().strftime('%H:%M:%S')
        stats['current_queues'] = data['queues']
        stats['last_action'] = action_str
        
        # Send response
        response = {
            'action': action_int,
            'action_str': action_str,
            'queues': data['queues'],
            'timestamp': datetime.now().isoformat(),
            'prediction_id': stats['predictions']
        }
        
        emit('ai_action_response', response)
        
        # Broadcast to all connected clients for dashboard updates
        socketio.emit('traffic_update', {
            'action': action_str,
            'queues': data['queues'],
            'timestamp': datetime.now().isoformat()
        })
        
        print(f"🤖 Prediction #{stats['predictions']}: State {state} → Action: {action_str}")
        
    except Exception as e:
        print(f"❌ Error processing AI request: {e}")
        emit('error', {'message': str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    print('🔌 Web client disconnected.')

if __name__ == '__main__':
    print("🌐 Starting web server on http://localhost:5001")
    print("📊 Dashboard available at: http://localhost:5001")
    print("🔗 API endpoint: http://localhost:5001/api/stats")
    print("="*60)
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)