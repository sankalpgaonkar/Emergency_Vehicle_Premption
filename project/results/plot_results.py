"""
🚦 AI Traffic Management System - Performance Analytics Dashboard
================================================================
Professional visualization of traffic optimization results
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec

# Set modern styling
plt.style.use('dark_background')
sns.set_palette("husl")

# Paths to results files
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
AI_CSV_PATH = str(PROJECT_ROOT / "results" / "results_v3.csv")
BASELINE_CSV_PATH = str(PROJECT_ROOT / "results" / "results.csv")

def create_professional_dashboard():
    """Create a comprehensive analytics dashboard"""
    
    # Read the data
    try:
        ai_df = pd.read_csv(AI_CSV_PATH)
        baseline_df = pd.read_csv(BASELINE_CSV_PATH)
    except FileNotFoundError as e:
        print(f"❌ Error: Could not find results file - {e}")
        return
    
    # Calculate performance metrics
    ai_total_wait = ai_df['cumulative_wait_time'].iloc[-1]
    baseline_total_wait = baseline_df['cumulative_wait_time'].iloc[-1]
    improvement = ((baseline_total_wait - ai_total_wait) / baseline_total_wait) * 100
    
    # Create figure with custom layout
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle('🚦 AI Traffic Management System - Performance Dashboard', 
                 fontsize=24, fontweight='bold', y=0.95)
    
    # Create grid layout
    gs = GridSpec(3, 4, figure=fig, hspace=0.3, wspace=0.3)
    
    # Main performance comparison (large plot)
    ax1 = fig.add_subplot(gs[0:2, 0:3])
    
    # Plot with enhanced styling
    ax1.plot(ai_df['timestep'], ai_df['cumulative_wait_time'], 
             label='🤖 AI Agent', linewidth=3, color='#00ff41', alpha=0.9)
    ax1.plot(baseline_df['timestep'], baseline_df['cumulative_wait_time'], 
             label='⏰ Fixed Timer Baseline', linewidth=3, color='#ff4444', 
             linestyle='--', alpha=0.8)
    
    ax1.fill_between(ai_df['timestep'], ai_df['cumulative_wait_time'], 
                     alpha=0.2, color='#00ff41')
    ax1.fill_between(baseline_df['timestep'], baseline_df['cumulative_wait_time'], 
                     alpha=0.2, color='#ff4444')
    
    ax1.set_xlabel('Simulation Time (steps)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Cumulative Wait Time (seconds)', fontsize=14, fontweight='bold')
    ax1.set_title('Performance Comparison Over Time', fontsize=16, fontweight='bold', pad=20)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.legend(fontsize=12, loc='upper left', framealpha=0.9)
    
    # Add performance improvement annotation
    ax1.annotate(f'🎯 {improvement:.1f}% Improvement', 
                xy=(0.7, 0.8), xycoords='axes fraction',
                fontsize=16, fontweight='bold', color='#00ff41',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.8))
    
    # Key metrics panel
    ax2 = fig.add_subplot(gs[0, 3])
    ax2.axis('off')
    
    metrics_text = f"""
    📊 KEY METRICS
    ═══════════════
    
    🤖 AI Total Wait: {ai_total_wait:,.0f}s
    ⏰ Baseline Wait: {baseline_total_wait:,.0f}s
    
    🎯 Improvement: {improvement:.1f}%
    💰 Time Saved: {baseline_total_wait - ai_total_wait:,.0f}s
    
    📈 Efficiency Gain: {(1 - ai_total_wait/baseline_total_wait)*100:.1f}%
    """
    
    ax2.text(0.05, 0.95, metrics_text, transform=ax2.transAxes, fontsize=12,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle="round,pad=0.5", facecolor='#1a1a1a', alpha=0.9))
    
    # Performance distribution
    ax3 = fig.add_subplot(gs[1, 3])
    
    # Calculate wait time differences
    ai_diff = np.diff(ai_df['cumulative_wait_time'])
    baseline_diff = np.diff(baseline_df['cumulative_wait_time'])
    
    ax3.hist([ai_diff, baseline_diff], bins=30, alpha=0.7, 
             label=['AI Agent', 'Baseline'], color=['#00ff41', '#ff4444'])
    ax3.set_xlabel('Wait Time per Step', fontsize=10)
    ax3.set_ylabel('Frequency', fontsize=10)
    ax3.set_title('Wait Time Distribution', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    # Efficiency trend
    ax4 = fig.add_subplot(gs[2, 0:2])
    
    # Calculate rolling efficiency
    window = 100
    ai_rolling = ai_df['cumulative_wait_time'].rolling(window=window).mean()
    baseline_rolling = baseline_df['cumulative_wait_time'].rolling(window=window).mean()
    efficiency = (1 - ai_rolling / baseline_rolling) * 100
    
    ax4.plot(ai_df['timestep'][window:], efficiency[window:], 
             color='#ffaa00', linewidth=2, label='Rolling Efficiency')
    ax4.axhline(y=improvement, color='#00ff41', linestyle='--', 
                label=f'Overall: {improvement:.1f}%')
    ax4.fill_between(ai_df['timestep'][window:], efficiency[window:], 
                     alpha=0.3, color='#ffaa00')
    
    ax4.set_xlabel('Simulation Time (steps)', fontsize=12)
    ax4.set_ylabel('Efficiency Improvement (%)', fontsize=12)
    ax4.set_title('AI Efficiency Trend (Rolling Average)', fontsize=14, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend(fontsize=10)
    
    # System info panel
    ax5 = fig.add_subplot(gs[2, 2:4])
    ax5.axis('off')
    
    system_info = f"""
    🔧 SYSTEM INFORMATION
    ═══════════════════
    
    📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    📊 Data Points: {len(ai_df):,} timesteps
    🎮 Simulation Duration: {ai_df['timestep'].iloc[-1]:,} steps
    
    🤖 AI Model: PPO (Proximal Policy Optimization)
    👁️  Vision: YOLOv8 + Custom Tracking
    🌐 Environment: SUMO Traffic Simulation
    
    ✅ Status: Analysis Complete
    """
    
    ax5.text(0.05, 0.95, system_info, transform=ax5.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle="round,pad=0.5", facecolor='#1a1a1a', alpha=0.9))
    
    # Add timestamp
    fig.text(0.99, 0.01, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
             ha='right', va='bottom', fontsize=8, alpha=0.7)
    
    plt.tight_layout()
    
    # Save high-quality version
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    plt.savefig(f'traffic_performance_dashboard_{timestamp}.png', 
                dpi=300, bbox_inches='tight', facecolor='black')
    
    print(f"📊 Dashboard saved as: traffic_performance_dashboard_{timestamp}.png")
    print(f"🎯 Performance Improvement: {improvement:.1f}%")
    print(f"💰 Time Saved: {baseline_total_wait - ai_total_wait:,.0f} seconds")
    
    plt.show()

def create_comparison_summary():
    """Create a simple comparison summary"""
    try:
        ai_df = pd.read_csv(AI_CSV_PATH)
        baseline_df = pd.read_csv(BASELINE_CSV_PATH)
        
        ai_total = ai_df['cumulative_wait_time'].iloc[-1]
        baseline_total = baseline_df['cumulative_wait_time'].iloc[-1]
        improvement = ((baseline_total - ai_total) / baseline_total) * 100
        
        print("\n" + "="*60)
        print("🚦 AI TRAFFIC MANAGEMENT - PERFORMANCE SUMMARY")
        print("="*60)
        print(f"🤖 AI Agent Total Wait Time:     {ai_total:>12,.0f} seconds")
        print(f"⏰ Baseline Total Wait Time:     {baseline_total:>12,.0f} seconds")
        print(f"💰 Time Saved:                  {baseline_total - ai_total:>12,.0f} seconds")
        print(f"🎯 Performance Improvement:      {improvement:>12.1f}%")
        print("="*60)
        
        if improvement > 0:
            print("✅ AI system is performing BETTER than baseline!")
        else:
            print("⚠️  AI system needs optimization")
            
    except Exception as e:
        print(f"❌ Error creating summary: {e}")

if __name__ == '__main__':
    print("🚀 Generating AI Traffic Management Dashboard...")
    create_professional_dashboard()
    create_comparison_summary()