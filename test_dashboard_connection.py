#!/usr/bin/env python3
"""
🧪 Dashboard Connection Test
===========================
Test the connection between live traffic system and web dashboard
"""

import requests
import time
import json
from datetime import datetime

def test_dashboard_connection():
    """Test sending data to the dashboard"""
    print("🧪 Testing Dashboard Connection...")
    print("="*50)
    
    # Extended test data simulating live traffic with more realistic patterns
    test_scenarios = [
        {'queues': [0, 0, 0, 0], 'action': 'KEEP'},
        {'queues': [1, 0, 0, 1], 'action': 'KEEP'},
        {'queues': [2, 1, 1, 1], 'action': 'KEEP'},
        {'queues': [3, 2, 1, 2], 'action': 'SWITCH'},
        {'queues': [2, 1, 2, 1], 'action': 'KEEP'},
        {'queues': [4, 3, 2, 3], 'action': 'SWITCH'},
        {'queues': [3, 2, 3, 2], 'action': 'KEEP'},
        {'queues': [5, 4, 1, 2], 'action': 'SWITCH'},
        {'queues': [2, 1, 0, 1], 'action': 'KEEP'},
        {'queues': [1, 0, 1, 0], 'action': 'KEEP'},
    ]
    
    dashboard_url = 'http://localhost:5001/api/update_traffic'
    
    print("📡 Testing API endpoint with continuous data stream...")
    print("⏰ This will run for 30 seconds to test dashboard persistence")
    
    # Run continuous test for 30 seconds
    start_time = time.time()
    test_duration = 30  # seconds
    scenario_index = 0
    
    while time.time() - start_time < test_duration:
        try:
            scenario = test_scenarios[scenario_index % len(test_scenarios)]
            
            # Add some randomness to make it more realistic
            import random
            realistic_scenario = {
                'queues': [max(0, q + random.randint(-1, 2)) for q in scenario['queues']],
                'action': scenario['action']
            }
            
            elapsed = time.time() - start_time
            print(f"\r🔄 [{elapsed:5.1f}s] Sending: {realistic_scenario}", end="", flush=True)
            
            response = requests.post(dashboard_url, json=realistic_scenario, timeout=2)
            
            if response.status_code != 200:
                print(f"\n❌ Error: HTTP {response.status_code}")
                break
                
        except requests.exceptions.ConnectionError:
            print("\n❌ Connection failed - Dashboard server not running")
            print("💡 Start dashboard with: python launch.py --component dashboard")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            break
        
        scenario_index += 1
        time.sleep(0.5)  # Send data every 500ms
    
    print("\n" + "="*50)
    print("🎯 Continuous test completed!")
    print("💡 Check the dashboard at: http://localhost:5001")
    print("📊 Data should persist and show live updates for 30 seconds")

if __name__ == '__main__':
    test_dashboard_connection()