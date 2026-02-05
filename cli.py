import argparse
import sys
import os
import json
import math
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.gpx_loader import GpxLoader, Segment
from src.weather_client import WeatherClient
from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams
from src.valhalla_client import ValhallaClient, SURFACE_MAP
import time

def _convert_json_to_segments(v_data: dict) -> list[Segment]:
    """
    Convert Valhalla Standard JSON v1.0 to Physics Engine Segments.
    Maps surf_id to actual Crr values.
    """
    # Crr Mapping Table (Source of Truth)
    CRR_TABLE = {
        0: 0.004570, # unknown -> asphalt
        1: 0.004570, # asphalt
        2: 0.003427, # concrete
        3: 0.005713, # wood/metal
        4: 0.005713, # paving_stones
        5: 0.005713, # cycleway
        6: 0.007998, # compacted
        7: 0.015000  # gravel/dirt
    }
    
    segments = []
    points = v_data["points"]
    v_segs = v_data["segments"]
    
    count = v_data["stats"]["segments_count"]
    
    for i in range(count):
        p_start_idx = v_segs["p_start"][i]
        p_end_idx = v_segs["p_end"][i]
        
        # Get start/end properties from points array
        start_dist = points["dist"][p_start_idx]
        end_dist = points["dist"][p_end_idx]
        start_ele = points["ele"][p_start_idx]
        end_ele = points["ele"][p_end_idx]
        start_lat = points["lat"][p_start_idx]
        start_lon = points["lon"][p_start_idx]
        end_lat = points["lat"][p_end_idx]
        end_lon = points["lon"][p_end_idx]
        
        # Segment properties
        avg_grade = v_segs["avg_grade"][i]
        avg_head = v_segs["avg_head"][i]
        length = v_segs["length"][i]
        
        # Resolve Crr
        surf_id = v_segs["surf_id"][i]
        crr_val = CRR_TABLE.get(surf_id, 0.004570)
        
        seg = Segment(
            index=i,
            start_dist=start_dist,
            end_dist=end_dist,
            length=length,
            grade=avg_grade,
            heading=avg_head,
            start_ele=start_ele,
            end_ele=end_ele,
            crr=crr_val,
            lat=end_lat, # Current point lat (for compatibility)
            lon=end_lon,
            start_lat=start_lat,
            start_lon=start_lon
        )
        segments.append(seg)
        
    return segments

def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="Advanced Cycling Course Simulator")
    
    # Course
    parser.add_argument("gpx", help="Path to GPX or JSON course file")
    parser.add_argument("--use-valhalla", action="store_true", help="Use Valhalla for map matching and segmentation")
    
    # Rider Selection & Profile Overrides
    parser.add_argument("--rider", type=str, default="rider_a", help="Rider ID in rider_data.json")
    parser.add_argument("--cp", type=float, default=None, help="CP [Watts] override")
    parser.add_argument("--w-prime", type=float, default=None, help="W' [Joules] override")
    parser.add_argument("--weight", type=float, default=None, help="Weight [kg] override")
    
    # Bike & Physics
    parser.add_argument("--bike-weight", type=float, default=8.0, help="Bike Weight [kg]")
    parser.add_argument("--cda", type=float, default=0.32, help="CdA")
    parser.add_argument("--crr", type=float, default=0.004, help="Crr")
    parser.add_argument("--drafting", type=float, default=0.0, help="Drafting Factor (0.0 - 0.5)")
    
    # Environment
    parser.add_argument("--wind-speed", type=float, default=0.0, help="Wind Speed [m/s]")
    parser.add_argument("--wind-deg", type=float, default=0.0, help="Wind Direction [deg] (0=North)")
    
    args = parser.parse_args()

    # 1. Load Course (GPX or JSON)
    if not os.path.exists(args.gpx):
        print(f"Error: File not found: {args.gpx}")
        sys.exit(1)
        
    loader = GpxLoader(args.gpx)
    segments = []
    raw_gain = 0.0
    
    # [NEW] Valhalla Integration Path
    if args.use_valhalla:
        print("[Mode] Using Valhalla Pipeline (Map Matching & Segmentation)")
        
        # 1-1. Extract Points from Input (GPX or JSON)
        input_points = []
        if args.gpx.lower().endswith(".json"):
            with open(args.gpx, 'r') as f:
                data = json.load(f)
                # Handle control_points format if exists, else raw list
                raw_list = data.get('control_points', data) if isinstance(data, dict) else data
                # Normalize to dict list
                for p in raw_list:
                    if isinstance(p, dict): input_points.append(p)
                    elif isinstance(p, list) and len(p) >= 2: input_points.append({"lat": p[0], "lon": p[1]})
        else:
            # GPX
            loader.load()
            # Sampling for request optimization (Valhalla handles up to ~20k points, but sampling is safer)
            # Take every point for now, Valhalla trace is robust
            input_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
            
        print(f"-> Input Points: {len(input_points)}")
        
        # 1-2. Call Valhalla
        v_client = ValhallaClient()
        try:
            print(f"-> Requesting Map Matching from {v_client.url} ...")
            v_data = v_client.get_standard_course(input_points)
            
            # 1-3. Convert to Physics Segments
            segments = _convert_json_to_segments(v_data)
            
            # Stats from Valhalla Result
            total_dist = v_data["stats"]["distance"] * 1000 # km -> m check unit! (Valhalla stat is meter? wait check parser)
            # Checked parser: distance is in meters (round(total_dist, 1))
            total_dist = v_data["stats"]["distance"] 
            total_gain = v_data["stats"]["ascent"]
            raw_gain = total_gain # Valhalla result is already smoothed/processed
            
            print(f"-> Valhalla Refined: {total_dist/1000:.1f} km, {total_gain:.0f}m Gain")
            
        except Exception as e:
            print(f"Error communicating with Valhalla: {e}")
            sys.exit(1)

    # [OLD] Legacy Local Logic
    elif args.gpx.lower().endswith(".json"):
        print(f"Loading JSON Course: {args.gpx} ...")
        with open(args.gpx, 'r') as f:
            data = json.load(f)
            # Support both raw list or wrapped structure
            seg_list = data.get('segments', data) if isinstance(data, dict) else data
            loader.load_from_json_data(seg_list)
            segments = loader.segments
            total_dist = sum(s.length for s in segments)
            total_gain = sum(max(0, s.end_ele - s.start_ele) for s in segments)
    else:
        # GPX
        loader.load()
        raw_gain = sum(max(0, loader.points[i].ele - loader.points[i-1].ele) for i in range(1, len(loader.points)))
        loader.smooth_elevation()
        segments = loader.compress_segments()
        total_dist = sum(s.length for s in segments)
        total_gain = sum(max(0, s.end_ele - s.start_ele) for s in segments)
    
    if not args.use_valhalla:
        print(f"-> Course Stats: {total_dist/1000:.1f} km, {total_gain:.0f}m Gain (Raw: {raw_gain:.0f}m)")
    
    # 2. Setup Rider Data
    rider_name = "Unknown"
    pdc_data = {}
    cp_val, wp_val, weight_val = 250.0, 20000.0, 70.0 # Defaults
    
    try:
        rider_data_path = "data/config/rider_data.json"
        if os.path.exists(rider_data_path):
            with open(rider_data_path, "r") as f:
                all_riders = json.load(f)
                r_info = all_riders.get(args.rider, {})
                rider_name = r_info.get("name", args.rider)
                pdc_data = r_info.get("pdc", {})
                cp_val = r_info.get("cp", 250.0)
                wp_val = r_info.get("w_prime", 20000.0)
                weight_val = r_info.get("weight_kg", 70.0)
    except Exception as e:
        print(f"Warning: Could not load rider data: {e}")

    # CLI Overrides
    if args.cp is not None: cp_val = args.cp
    if args.w_prime is not None: wp_val = args.w_prime
    if args.weight is not None: weight_val = args.weight

    # Use original rider data (Removed 95% scale)
    rider = Rider(cp=cp_val, w_prime_max=wp_val, weight=weight_val, pdc=pdc_data)
    params = PhysicsParams(cda=args.cda, crr=args.crr, bike_weight=args.bike_weight, drafting_factor=args.drafting)
    weather = WeatherClient(use_scenario_mode=True, scenario_data={"wind_speed": args.wind_speed, "wind_deg": args.wind_deg, "temperature": 20.0})
    engine = PhysicsEngine(rider, params, weather)
    
    # 3. Run Optimization
    print("\n[Running Physics Engine]")
    print(f"Rider: {cp_val}W CP, {wp_val/1000:.1f}kJ W'")
    result = engine.find_optimal_pacing(segments)
    
    # 4. Report
    print("\n" + "="*40)
    print("      SIMULATION REPORT")
    print("="*40)
    h, m, s = int(result.total_time_sec // 3600), int((result.total_time_sec % 3600) // 60), int(result.total_time_sec % 60)
    print(f"Time         : {h}h {m}m {s}s")
    print(f"Avg Speed    : {result.average_speed_kmh:.1f} km/h")
    print(f"Norm Power   : {result.normalized_power:.0f} W")
    print(f"Avg Power    : {result.average_power:.0f} W")
    print(f"Work         : {result.work_kj:.0f} kJ")
    print(f"Min W' Bal   : {result.w_prime_min/1000:.1f} kJ (Remaining)")
    
    if result.is_success:
        print("-" * 40)
        print(f"Recommended P_base : {result.base_power:.0f} W")
        print("Status       : SUCCESS (Feasible)")
        
        # Capture segment details for visualization
        output_data = {"summary": {"time_str": f"{h}h {m}m {s}s", "avg_speed": result.average_speed_kmh, "norm_power": result.normalized_power, "work_kj": result.work_kj}, "segments": []}
        
        engine.rider.reset_state()
        curr_v = 0.1 # Start from rest (0.1 m/s)
        cum_dist = 0.0
        curr_total_time = 0.0
        est_hours = total_dist / 1000.0 / 25.0
        
        for seg in segments:
            # Re-calculate P_target (Simplified but consistent)
            p_base = result.base_power
            est_sec = est_hours * 3600
            pdc_lim = engine.rider.get_pdc_power(est_sec)
            riegel_lim = engine.rider.cp * ((1.0 / max(1.0, est_hours)) ** 0.07)
            alpha_val = 1.0 if est_sec <= 1200 else (0.0 if est_sec >= 7200 else (1.0 - (est_sec - 1200) / 6000) ** 1.5)
            final_p_limit = alpha_val * pdc_lim + (1.0 - alpha_val) * riegel_lim * 1.2
            
            p_target = engine._calculate_target_power(p_base, seg.grade, final_p_limit)
            
            # Wind
            rel_angle = math.radians(args.wind_deg - seg.heading)
            v_headwind = args.wind_speed * math.cos(rel_angle)
            
            v_next, t_sec, is_walking, _raw_v = engine._solve_segment_physics(seg, p_target, curr_v, v_headwind, f_limit=engine.rider.get_max_force())
            
            p_actual = 30.0 if is_walking else p_target
            
            engine.rider.update_w_prime(p_actual, t_sec)
            cum_dist += seg.length
            curr_total_time += t_sec
            output_data["segments"].append({
                "dist_km": cum_dist / 1000.0, 
                "ele": seg.end_ele, 
                "grade_pct": seg.grade * 100, 
                "speed_kmh": (v_next * 3.6), 
                "power": p_actual, 
                "w_prime": engine.rider.w_prime_bal,
                "time_sec": curr_total_time,
                "lat": getattr(seg, 'lat', 0.0),
                "lon": getattr(seg, 'lon', 0.0),
                "heading": getattr(seg, 'heading', 0.0)
            })
            curr_v = v_next
            
        with open("simulation_result.json", "w") as f:
            json.dump(output_data, f, indent=2)
        
        # Stats from memory
        speeds = [s["speed_kmh"] for s in output_data["segments"]]
        max_spd = max(speeds) if speeds else 0
        dist_over_70 = sum(output_data["segments"][i]["dist_km"] - output_data["segments"][i-1]["dist_km"] if i > 0 else 0 for i, s in enumerate(output_data["segments"]) if s["speed_kmh"] > 70)
        
        print("-" * 40)
        print(f"[Safety Check] Max Speed: {max_spd:.1f} km/h")
        print(f"[Safety Check] >70km/h: {dist_over_70:.2f} km")
        print("-" * 40)
    else:
        print("Status       : FAILED")
        print(f"Reason       : {result.fail_reason}")
    print("="*40)
    print(f"[System] Calculation Time: {time.time() - start_time:.2f} sec")

if __name__ == "__main__":
    main()