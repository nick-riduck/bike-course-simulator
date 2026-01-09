import json
import os
import sys

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib required")
    sys.exit(1)

def visualize_result(json_path):
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    segments = data['segments']
    summary = data['summary']
    
    dist = [s['dist_km'] for s in segments]
    ele = [s['ele'] for s in segments]
    speed = [s['speed_kmh'] for s in segments]
    power = [s['power'] for s in segments]
    w_prime = [s['w_prime'] / 1000.0 for s in segments] # kJ

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    
    # 1. Elevation
    ax1.plot(dist, ele, color='gray', label='Elevation (m)')
    ax1.fill_between(dist, ele, color='gray', alpha=0.1)
    ax1.set_ylabel('Elevation (m)')
    ax1.set_title(f"Simulation Result: {summary['time_str']} / {summary['avg_speed']:.1f} km/h / NP {summary['norm_power']:.0f}W")
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    # 2. Speed
    ax2.plot(dist, speed, color='blue', label='Speed (km/h)', linewidth=1)
    ax2.axhline(y=60, color='red', linestyle=':', label='60km/h Warning')
    ax2.set_ylabel('Speed (km/h)')
    ax2.legend(loc='upper right')
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    # 3. Power & W'
    ax3.plot(dist, power, color='orange', label='Power (W)', alpha=0.7, linewidth=1)
    ax3.set_ylabel('Power (W)')
    
    # Twin axis for W'
    ax4 = ax3.twinx()
    ax4.plot(dist, w_prime, color='green', label="W' Balance (kJ)", linewidth=1.5)
    ax4.set_ylabel("W' Balance (kJ)")
    ax4.set_ylim(bottom=0)
    
    lines, labels = ax3.get_legend_handles_labels()
    lines2, labels2 = ax4.get_legend_handles_labels()
    ax3.legend(lines + lines2, labels + labels2, loc='upper right')
    
    ax3.set_xlabel('Distance (km)')
    ax3.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    output_img = "simulation_analysis.png"
    plt.savefig(output_img)
    print(f"Saved visualization to {output_img}")

if __name__ == "__main__":
    visualize_result("simulation_result.json")
