import sys
import os
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.gpx_loader import GpxLoader
from src.core.rider import Rider
from src.engines.base import PhysicsEngine, PhysicsParams
from src.services.valhalla import ValhallaClient
from cli import _convert_json_to_segments

def run_pacing_test(gpx_path):
    print(f"--- Pacing Comparison Test: {os.path.basename(gpx_path)} ---")
    print(f"Rider: 80kg, Bike: 15kg, Target: 400W")
    
    # 1. Setup Rider & Params
    rider = Rider(cp=500, w_prime_max=50000, weight=80) # High CP to maintain 400W
    params = PhysicsParams(bike_weight=15, cda=0.35)
    
    # 2. Legacy Simulation
    print("\n[1] Running Legacy Simulation...")
    loader = GpxLoader(gpx_path)
    loader.load()
    loader.smooth_elevation()
    legacy_segments = loader.compress_segments()
    
    engine = PhysicsEngine(rider, params)
    
    v_prev = 0.1
    total_time_legacy = 0.0
    for i, seg in enumerate(legacy_segments):
        v_next, t_sec, is_walking, _raw_v = engine._solve_segment_physics(seg, 400.0, v_prev, 0.0, f_limit=engine.rider.get_max_force())
        v_prev = v_next
        total_time_legacy += t_sec

    # 3. Valhalla Simulation
    print("[2] Running Valhalla Simulation...")
    v_client = ValhallaClient()
    
    # [Up-sampling] Ensure points are dense enough (max 30m) for Valhalla Map Matching
    # Especially important for sparse GPX files like Seorak (1.2km gaps)
    raw_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    input_points = []
    if raw_points:
        input_points.append(raw_points[0])
        for i in range(1, len(raw_points)):
            prev = input_points[-1]
            curr = raw_points[i]
            d = v_client._haversine(prev['lat'], prev['lon'], curr['lat'], curr['lon'])
            
            if d > 30.0:
                count = int(d / 30.0)
                for k in range(1, count + 1):
                    frac = k / (count + 1)
                    input_points.append({
                        "lat": prev['lat'] + (curr['lat'] - prev['lat']) * frac,
                        "lon": prev['lon'] + (curr['lon'] - prev['lon']) * frac
                    })
            input_points.append(curr)

    print(f"DEBUG: Total input points for Valhalla (Up-sampled): {len(input_points)}")
    
    try:
        v_data = v_client.get_standard_course(input_points)
    except Exception as e:
        print(f"CRITICAL ERROR: Valhalla processing failed: {e}")
        sys.exit(1)
        
    valhalla_segments = _convert_json_to_segments(v_data)
    
    v_prev = 0.1
    total_time_valhalla = 0.0
    for i, seg in enumerate(valhalla_segments):
        v_next, t_sec, is_walking, _raw_v = engine._solve_segment_physics(seg, 400.0, v_prev, 0.0, f_limit=engine.rider.get_max_force())
        v_prev = v_next
        total_time_valhalla += t_sec

    # 4. Report
    def format_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f"{h}h {m}m {s}s"

    legacy_dist_km = sum(s.length for s in legacy_segments)/1000
    valhalla_dist_km = sum(s.length for s in valhalla_segments)/1000
    
    legacy_ascent = int(sum(max(0, s.end_ele - s.start_ele) for s in legacy_segments))
    valhalla_ascent = int(sum(max(0, s.end_ele - s.start_ele) for s in valhalla_segments))
    
    legacy_max_g = max([s.grade * 100 for s in legacy_segments]) if legacy_segments else 0
    valhalla_max_g = max([s.grade * 100 for s in valhalla_segments]) if valhalla_segments else 0

    print("\n" + "="*45)
    print(f"{'Metric':<15} | {'Legacy':<12} | {'Valhalla':<12}")
    print("-" * 45)
    print(f"{'Time':<15} | {format_time(total_time_legacy):<12} | {format_time(total_time_valhalla):<12}")
    print(f"{'Distance':<15} | {legacy_dist_km:>10.1f}km | {valhalla_dist_km:>10.1f}km")
    print(f"{'Real Ascent':<15} | {legacy_ascent:>10d}m | {valhalla_ascent:>10d}m")
    print(f"{'Max Grade':<15} | {legacy_max_g:>10.1f}% | {valhalla_max_g:>10.1f}%")
    print(f"{'Avg Speed':<15} | {legacy_dist_km/max(0.1, (total_time_legacy/3600)):>10.1f}kph | {valhalla_dist_km/max(0.1, (total_time_valhalla/3600)):>10.1f}kph")
    print("="*45)

if __name__ == "__main__":
    gpx = "data/gpx/20seorak.gpx"
    run_pacing_test(gpx)