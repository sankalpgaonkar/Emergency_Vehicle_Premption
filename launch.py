#!/usr/bin/env python3
"""
🚦 AI Traffic Management System - Launcher
==========================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
Easy-to-use launcher for all system components
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def print_banner():
    """Print the system banner"""
    print("\n" + "="*70)
    print("🚦 AI TRAFFIC MANAGEMENT SYSTEM - By Sankalp Gaonkar (@sankalpgaonkar)")
    print("="*70)
    print("🎯 Choose your component:")
    print("1. 🎬 Live Traffic Analysis")
    print("2. 🚨 Emergency Vehicle Detection") 
    print("3. 🌐 Web Dashboard")
    print("4. 📊 Performance Analytics")
    print("5. 🧪 Test Mode (Simulated Data)")
    print("6. 🎮 Simple 3D System (Fast)")
    print("7. 🎯 Full 3D Integration")
    print("8. 🎮 Unity 3D Integration")
    print("9. 🌐 Web 3D Visualization")
    print("10. 🧠 Train AI Models")
    print("11. 🚀 Enhanced Dashboard (Live Detection + Upload + Preemption)")
    print("="*70)

def run_component(component, args=None):
    """Run a specific system component"""
    base_path = Path(__file__).parent
    
    components = {
        'live': {
            'path': base_path / 'project' / 'src' / 'vision' / 'run_live.py',
            'description': '🎬 Starting Live Traffic Analysis...'
        },
        'test': {
            'path': base_path / 'project' / 'src' / 'vision' / 'run_live.py',
            'description': '🧪 Starting Test Mode (Simulated Data)...',
            'args': ['--test']
        },
        'emergency': {
            'path': base_path / 'project' / 'src' / 'vision' / 'emergency_vehicle_detection.py',
            'description': '🚨 Starting Emergency Vehicle Detection...'
        },
        'dashboard': {
            'path': base_path / 'project' / 'src' / 'api' / 'app.py',
            'description': '🌐 Starting Web Dashboard...'
        },
        'analytics': {
            'path': base_path / 'project' / 'results' / 'plot_results.py',
            'description': '📊 Generating Performance Analytics...'
        },
        '3d': {
            'path': base_path / 'project' / 'src' / 'simple_3d_system.py',
            'description': '🎮 Starting Simple 3D Traffic System...'
        },
        '3d-full': {
            'path': base_path / 'project' / 'src' / 'integrated_3d_system.py',
            'description': '🎯 Starting Full Integrated 3D System...'
        },
        'unity': {
            'path': base_path / 'project' / 'src' / 'unity_3d_integration.py',
            'description': '🎯 Starting Unity 3D Integration Server...'
        },
        'web3d': {
            'path': base_path / 'project' / 'src' / 'web_3d_visualization.py',
            'description': '🌐 Starting Web-based 3D Visualization...'
        },
        'enhanced': {
            'path': base_path / 'project' / 'src' / 'extensions' / 'enhanced_dashboard.py',
            'description': '🚀 Starting Enhanced Dashboard (Live + Upload + Preemption)...'
        }
    }
    
    if component not in components:
        print(f"❌ Unknown component: {component}")
        return False
    
    comp_info = components[component]
    
    if not comp_info['path'].exists():
        print(f"❌ Component file not found: {comp_info['path']}")
        return False
    
    print(comp_info['description'])
    
    # Ensure SUMO_HOME is set in environment
    if 'SUMO_HOME' not in os.environ:
        os.environ['SUMO_HOME'] = '/opt/homebrew/share/sumo'
    
    try:
        # Store original directory
        original_dir = os.getcwd()
        
        # For vision and 3D components, stay in project root but run the script with full path
        if component in ['live', 'emergency', 'test', '3d', '3d-full', 'unity', 'web3d', 'enhanced']:
            cmd = [sys.executable, str(comp_info['path'])]
            if 'args' in comp_info:
                cmd.extend(comp_info['args'])
            result = subprocess.run(cmd, capture_output=False, cwd=original_dir)
        else:
            # For other components, change to their directory
            os.chdir(comp_info['path'].parent)
            result = subprocess.run([sys.executable, comp_info['path'].name], 
                                  capture_output=False)
        
        # Restore original directory
        os.chdir(original_dir)
        
        if result.returncode == 0:
            print(f"✅ {component} completed successfully")
        else:
            print(f"❌ {component} exited with code {result.returncode}")
            
        return result.returncode == 0
        
    except KeyboardInterrupt:
        print(f"\n🛑 {component} interrupted by user")
        return True
    except Exception as e:
        print(f"❌ Error running {component}: {e}")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'cv2', 'numpy', 'torch', 'ultralytics', 
        'stable_baselines3', 'flask', 'matplotlib'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("💡 Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies found")
    return True

def interactive_mode():
    """Run in interactive mode"""
    print_banner()
    
    while True:
        try:
            choice = input("\n🎯 Select component (1-5) or 'q' to quit: ").strip().lower()
            
            if choice == 'q' or choice == 'quit':
                print("👋 Goodbye!")
                break
            elif choice == '1':
                run_component('live')
            elif choice == '2':
                run_component('emergency')
            elif choice == '3':
                run_component('dashboard')
            elif choice == '4':
                run_component('analytics')
            elif choice == '5':
                run_component('test')
            elif choice == '6':
                run_component('3d')
            elif choice == '7':
                run_component('3d-full')
            elif choice == '8':
                run_component('unity')
            elif choice == '9':
                run_component('web3d')
            elif choice == '10':
                print("🧠 AI Training modules coming soon!")
            elif choice == '11':
                run_component('enhanced')
            else:
                print("❌ Invalid choice. Please select 1-11 or 'q'")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(
        description="🚦 AI Traffic Management System Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch.py                    # Interactive mode
  python launch.py --component live   # Run live analysis
  python launch.py --component dashboard --check-deps
        """
    )
    
    parser.add_argument(
        '--component', '-c',
        choices=['live', 'emergency', 'dashboard', 'analytics', 'test', '3d', '3d-full', 'unity', 'web3d', 'enhanced'],
        help='Component to run directly'
    )
    
    parser.add_argument(
        '--check-deps', 
        action='store_true',
        help='Check dependencies before running'
    )
    
    parser.add_argument(
        '--list-components',
        action='store_true', 
        help='List available components'
    )
    
    args = parser.parse_args()
    
    if args.list_components:
        print("\n🎯 Available Components:")
        print("- live: Live Traffic Analysis")
        print("- emergency: Emergency Vehicle Detection")
        print("- dashboard: Web Dashboard")
        print("- analytics: Performance Analytics")
        print("- test: Test Mode (Simulated Data)")
        print("- 3d: Simple 3D System (Fast)")
        print("- 3d-full: Full Integrated 3D System")
        print("- unity: Unity 3D Integration Server")
        print("- web3d: Web-based 3D Visualization")
        return
    
    if args.check_deps:
        if not check_dependencies():
            sys.exit(1)
    
    if args.component:
        # Direct component launch
        success = run_component(args.component)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        if args.check_deps or check_dependencies():
            interactive_mode()

if __name__ == '__main__':
    main()