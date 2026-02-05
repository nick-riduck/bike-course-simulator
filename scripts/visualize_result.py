import json
import os
import sys
import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
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
    
    # 1. Extract Raw Data
    raw_dist = np.array([s['dist_km'] for s in segments])
    raw_ele = np.array([s['ele'] for s in segments])
    raw_speed = np.array([s['speed_kmh'] for s in segments])
    raw_power = np.array([s['power'] for s in segments])
    raw_grade = np.array([s['grade_pct'] for s in segments])
    raw_w_prime = np.array([s['w_prime'] / 1000.0 for s in segments]) 

    # 2. Resample for Section Analysis (100m Step)
    max_dist = raw_dist[-1]
    resample_dist = np.arange(0, max_dist, 0.1) # 100m step
    
    # Interpolate Elevation
    resample_ele = np.interp(resample_dist, raw_dist, raw_ele)
    
    # Calculate Grade
    resample_grade = np.diff(resample_ele, append=resample_ele[-1]) / 100.0 * 100.0
    
    # 3. Detect Sections based on Resampled Grade
    sections = []
    current_type = "FLAT"
    start_km = 0.0
    
    def get_type(g):
        if g > 2.0: return "UP"
        elif g < -2.0: return "DOWN"
        else: return "FLAT"

    current_type = get_type(resample_grade[0])
    
    for i in range(1, len(resample_dist)):
        window = resample_grade[i:i+5]
        if len(window) == 0: break
        avg_g = np.mean(window)
        next_type = get_type(avg_g)
        
        curr_dist = resample_dist[i]
        seg_len = curr_dist - start_km
        
        if next_type != current_type and seg_len > 1.0:
            sections.append({
                "type": current_type,
                "start": start_km,
                "end": curr_dist
            })
            current_type = next_type
            start_km = curr_dist
            
    sections.append({
        "type": current_type,
        "start": start_km,
        "end": max_dist
    })
    
    # 4. Calculate Stats using RAW Data
    raw_times = np.array([s.get('time_sec', 0) for s in segments])
    
    analyzed_sections = []
    
    for sec in sections:
        # Mask for raw data
        mask = (raw_dist >= sec['start']) & (raw_dist <= sec['end'])
        if not np.any(mask): continue
        
        s_dist_arr = raw_dist[mask]
        s_pwr_arr = raw_power[mask]
        s_ele_arr = raw_ele[mask]
        s_time_arr = raw_times[mask]
        
        dist_len = s_dist_arr[-1] - s_dist_arr[0]
        if dist_len <= 0: continue
        
        # Precise Time from pre-calculated time_sec
        total_sec = s_time_arr[-1] - s_time_arr[0]
        time_hours = total_sec / 3600.0
        
        avg_pwr = np.mean(s_pwr_arr)
        avg_grad = (s_ele_arr[-1] - s_ele_arr[0]) / (dist_len * 1000) * 100 
        
        analyzed_sections.append({
            "type": sec['type'],
            "start": sec['start'],
            "end": sec['end'],
            "avg_pwr": avg_pwr,
            "avg_grad": avg_grad,
            "time_h": time_hours
        })

    # --- Plotting ---
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    
    # 1. Elevation
    ax1.plot(raw_dist, raw_ele, color='#555555', label='Elevation (m)', linewidth=1)
    ax1.fill_between(raw_dist, raw_ele, color='#DDDDDD', alpha=0.5)
    
    # Highlight All Major Sections
    for s in analyzed_sections:
        if (s['end'] - s['start']) < 1.0:
            continue
            
        color = 'gray'
        label_color = 'black'
        type_label = ""
        
        if s['type'] == "UP":
            color = 'red'
            label_color = 'red'
            type_label = "UP"
        elif s['type'] == "DOWN":
            color = 'blue'
            label_color = 'blue'
            type_label = "DN"
        else:
            color = 'green'
            label_color = 'green'
            type_label = "FL"

        ax1.axvspan(s['start'], s['end'], color=color, alpha=0.1)
        
        mid = (s['start'] + s['end']) / 2
        mask = (raw_dist >= s['start']) & (raw_dist <= s['end'])
        max_y = np.max(raw_ele[mask]) if np.any(mask) else 0
        
        t_min = int(s['time_h'] * 60)
        t_sec = int((s['time_h'] * 3600) % 60)
        
        label = f"{type_label}\n{s['avg_grad']:.1f}%\n{int(s['avg_pwr'])}W\n{t_min}m{t_sec}s"
        
        ax1.text(mid, max_y + 20, label, ha='center', va='bottom', fontsize=8, color=label_color, fontweight='bold')

    ax1.set_ylabel('Elevation (m)')
    ax1.set_title(f"Simulation Analysis: {summary['time_str']} / {summary['avg_speed']:.1f} km/h / NP {summary['norm_power']:.0f}W")
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    # 2. Speed
    ax2.plot(raw_dist, raw_speed, color='blue', label='Speed (km/h)', linewidth=0.8)
    ax2.axhline(y=60, color='red', linestyle=':', label='Warning (60km/h)')
    ax2.set_ylabel('Speed (km/h)')
    ax2.legend(loc='upper right')
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    # 3. Power & W'
    ax3.plot(raw_dist, raw_power, color='orange', label='Power (W)', alpha=0.6, linewidth=0.8)
    ax3.set_ylabel('Power (W)')
    
    ax4 = ax3.twinx()
    ax4.plot(raw_dist, raw_w_prime, color='green', label="W' Balance (kJ)", linewidth=1.5)
    ax4.set_ylabel("W' Balance (kJ)")
    ax4.set_ylim(bottom=0)
    
    lines, labels = ax3.get_legend_handles_labels()
    lines2, labels2 = ax4.get_legend_handles_labels()
    ax3.legend(lines + lines2, labels + labels2, loc='upper right')
    
    ax3.set_xlabel('Distance (km)')
    ax3.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    output_img = "simulation_analysis.png"
    plt.savefig(output_img, dpi=150)
    print(f"Saved annotated visualization to {output_img}")

if __name__ == "__main__":
    visualize_result("simulation_result.json")
