import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.gpx_loader import GpxLoader
from src.services.valhalla import ValhallaClient

def inspect_outlier(gpx_path):
    print(f"Inspecting: {gpx_path}")
    loader = GpxLoader(gpx_path)
    loader.load()
    input_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    
    client = ValhallaClient()
    # 1. Get Standard JSON (Includes filtering logic)
    print("Fetching Valhalla data...")
    v_data = client.get_standard_course(input_points)
    
    points = v_data['points']
    dist = points['dist']
    grade = points['grade']
    ele = points['ele']
    
    print("\n--- Outlier Inspection (Grade > 20%) ---")
    print(f"{'Idx':<5} | {'Dist(km)':<8} | {'Grade(%)':<8} | {'Ele(m)':<8} | {'Prev Ele':<8} | {'Diff(m)':<8}")
    print("-" * 70)
    
    for i in range(1, len(grade)):
        if abs(grade[i]) > 0.20:
            diff = ele[i] - ele[i-1]
            print(f"{i:<5} | {dist[i]/1000:<8.3f} | {grade[i]*100:<8.1f} | {ele[i]:<8.2f} | {ele[i-1]:<8.2f} | {diff:<8.2f}")

    # Check Neighbors for the worst outlier
    max_g_idx = 0
    max_g = 0
    for i in range(len(grade)):
        if abs(grade[i]) > abs(max_g):
            max_g = grade[i]
            max_g_idx = i
            
    print(f"\n--- Neighborhood of Max Grade (Idx: {max_g_idx}) ---")
    start = max(0, max_g_idx - 3)
    end = min(len(grade), max_g_idx + 4)
    for i in range(start, end):
        mark = "<<" if i == max_g_idx else ""
        d_step = dist[i] - dist[i-1] if i > 0 else 0
        print(f"{i:<5} | {dist[i]:<8.1f}m | {ele[i]:<8.2f}m | G: {grade[i]*100:<6.1f}% | d_step: {d_step:.1f}m {mark}")

if __name__ == "__main__":
    inspect_outlier("data/gpx/Namsan1_7.gpx")
