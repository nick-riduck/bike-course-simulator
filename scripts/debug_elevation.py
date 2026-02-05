import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.valhalla_client import ValhallaClient

def calculate_grade(dist, ele):
    """Calculate grade (%) from distance and elevation arrays."""
    grades = [0.0]
    for i in range(1, len(dist)):
        d = dist[i] - dist[i-1]
        if d > 0:
            g = (ele[i] - ele[i-1]) / d
            grades.append(g * 100)
        else:
            grades.append(0.0)
    return grades

def calculate_ascent(ele):
    """Calculate cumulative elevation gain (m)."""
    gain = 0
    for i in range(1, len(ele)):
        diff = ele[i] - ele[i-1]
        if diff > 0:
            gain += diff
    return gain

def moving_average(data, window_size):
    """Simple Moving Average with Edge Padding (Same as ValhallaClient)."""
    if window_size <= 1: return data
    pad_size = window_size // 2
    # Ensure data is a list for padding
    data_list = list(data)
    padded = [data_list[0]] * pad_size + data_list + [data_list[-1]] * pad_size
    smoothed = []
    for i in range(len(data_list)):
        window = padded[i : i + window_size]
        smoothed.append(sum(window) / len(window))
    return np.array(smoothed)

def analyze_elevation(gpx_path):
    print(f"Analyzing: {gpx_path}")
    
    # 1. Load Original GPX
    loader = GpxLoader(gpx_path)
    loader.load()
    orig_dist = [p.distance_from_start for p in loader.points]
    orig_ele = [p.ele for p in loader.points]
    orig_grade = calculate_grade(orig_dist, orig_ele)
    
    # 2. Get Valhalla Data (Currently implemented with Window 21 + 10m Resampling)
    client = ValhallaClient()
    
    # [Up-sampling] 30m
    raw_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    input_points = []
    if raw_points:
        input_points.append(raw_points[0])
        for i in range(1, len(raw_points)):
            prev = input_points[-1]
            curr = raw_points[i]
            d = client._haversine(prev['lat'], prev['lon'], curr['lat'], curr['lon'])
            if d > 30.0:
                count = int(d / 30.0)
                for k in range(1, count + 1):
                    frac = k / (count + 1)
                    input_points.append({
                        "lat": prev['lat'] + (curr['lat'] - prev['lat']) * frac,
                        "lon": prev['lon'] + (curr['lon'] - prev['lon']) * frac
                    })
            input_points.append(curr)
    
    print("Fetching Valhalla data...")
    v_data = client.get_standard_course(input_points)
    
    # Valhalla Processed (Final)
    val_dist = v_data['points']['dist']
    val_ele = v_data['points']['ele']
    val_grade = [g * 100 for g in v_data['points']['grade']]
    
    val_ascent = v_data['stats']['ascent']
    orig_ascent = calculate_ascent(orig_ele)
    
    print(f"\n--- Final Comparison ---")
    print(f"Original Ascent: {orig_ascent:.1f}m")
    print(f"Valhalla Ascent: {val_ascent:.1f}m")
    print(f"Max Grade: {max(val_grade):.1f}%")
    print(f"Min Grade: {min(val_grade):.1f}%")

    # 3. Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Elevation Plot
    ax1.plot(orig_dist, orig_ele, label='Original GPX', color='red', alpha=0.6, linewidth=1.5)
    ax1.plot(val_dist, val_ele, label='Valhalla (Window 21 + 10m Resample)', color='green', linewidth=2)
    ax1.set_ylabel('Elevation (m)')
    ax1.set_title(f'Elevation Profile: Original vs Valhalla Processed\n({os.path.basename(gpx_path)})')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Grade Plot
    ax2.plot(orig_dist, orig_grade, label='Original Grade', color='red', alpha=0.3)
    ax2.plot(val_dist, val_grade, label='Valhalla Processed Grade', color='green', linewidth=1.5)
    ax2.set_ylabel('Grade (%)')
    ax2.set_xlabel('Distance (m)')
    ax2.set_ylim(-25, 25)
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.2)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    output_img = "data/output/elevation_analysis.png"
    plt.tight_layout()
    plt.savefig(output_img)
    print(f"Analysis saved to {output_img}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_elevation.py <gpx_file>")
    else:
        analyze_elevation(sys.argv[1])
