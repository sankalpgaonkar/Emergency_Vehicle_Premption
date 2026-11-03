#!/usr/bin/env python3
"""
🧪 Model Loading Test
====================
Quick test to verify all models and files can be loaded correctly
"""

import os
import sys
from pathlib import Path

def test_model_loading():
    """Test if all required models and files exist and can be loaded"""
    print("🧪 Testing AI Traffic Management System Components...")
    print("="*60)
    
    # Get project root
    project_root = Path(__file__).parent / "project"
    
    # Test files to check
    test_files = {
        "AI Model": project_root / "models" / "ppo_traffic_model_v2.zip",
        "Emergency Model": project_root / "models" / "yolo_emergency_detector.pt", 
        "Video 1": project_root / "videos" / "intersection1.mp4",
        "Video 2": project_root / "videos" / "intersection2.mp4",
        "Emergency Video": project_root / "videos" / "emergency2.mp4",
        "SUMO Network": project_root / "sumo_files" / "jaipur.net.xml",
        "SUMO Routes": project_root / "sumo_files" / "jaipur.rou.xml",
        "Results AI": project_root / "results" / "results_v3.csv",
        "Results Baseline": project_root / "results" / "results.csv"
    }
    
    print("📁 File Existence Check:")
    print("-" * 40)
    all_exist = True
    
    for name, path in test_files.items():
        if path.exists():
            size = path.stat().st_size / (1024*1024)  # Size in MB
            print(f"✅ {name:<15}: {path.name} ({size:.1f} MB)")
        else:
            print(f"❌ {name:<15}: {path} (NOT FOUND)")
            all_exist = False
    
    print("\n🤖 AI Model Loading Test:")
    print("-" * 40)
    
    try:
        from stable_baselines3 import PPO
        model_path = project_root / "models" / "ppo_traffic_model_v2.zip"
        model = PPO.load(str(model_path))
        print("✅ PPO model loaded successfully")
        
        # Test prediction with dummy data
        import numpy as np
        dummy_state = np.array([1, 2, 3, 4, 0, 1], dtype=np.float32)
        action, _ = model.predict(dummy_state, deterministic=True)
        print(f"✅ Model prediction test: {action} (type: {type(action)})")
        
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        all_exist = False
    
    print("\n👁️  Vision System Test:")
    print("-" * 40)
    
    try:
        import cv2
        from ultralytics import YOLO
        
        # Test OpenCV
        print(f"✅ OpenCV version: {cv2.__version__}")
        
        # Test YOLO (this will download if not present)
        print("📥 Loading YOLO model (may download on first run)...")
        yolo_model = YOLO('yolov8n.pt')  # Use nano for faster loading
        print("✅ YOLO model loaded successfully")
        
    except Exception as e:
        print(f"❌ Vision system test failed: {e}")
        all_exist = False
    
    print("\n📊 Dependencies Check:")
    print("-" * 40)
    
    required_packages = [
        'cv2', 'numpy', 'torch', 'ultralytics', 
        'stable_baselines3', 'flask', 'matplotlib', 'pandas'
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            all_exist = False
    
    print("\n" + "="*60)
    if all_exist:
        print("🎉 ALL TESTS PASSED! System is ready to run.")
        print("💡 You can now use: python launch.py")
    else:
        print("⚠️  Some components are missing or failed to load.")
        print("💡 Try: pip install -r requirements.txt")
    print("="*60)
    
    return all_exist

if __name__ == '__main__':
    test_model_loading()