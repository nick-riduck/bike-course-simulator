import argparse
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.gpx_loader import GpxLoader
from src.weather_client import WeatherClient
from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams

def main():
    parser = argparse.ArgumentParser(description="Advanced Cycling Course Simulator")
    
    # Required
    parser.add_argument("gpx", help="Path to GPX file")
    
    # Rider Profile
    parser.add_argument("--cp", type=float, default=250.0, help="Critical Power (FTP) [Watts]")
    parser.add_argument("--w-prime", type=float, default=20000.0, help="Anaerobic Capacity (W') [Joules]")
    parser.add_argument("--weight", type=float, default=70.0, help="Rider Weight [kg]")
    
    # Bike & Physics
    parser.add_argument("--bike-weight", type=float, default=8.0, help="Bike Weight [kg]")
    parser.add_argument("--cda", type=float, default=0.32, help="CdA")
    parser.add_argument("--crr", type=float, default=0.004, help="Crr")
    parser.add_argument("--drafting", type=float, default=0.0, help="Drafting Factor (0.0 - 0.5)")
    
    # Environment
    parser.add_argument("--wind-speed", type=float, default=0.0, help="Wind Speed [m/s]")
    parser.add_argument("--wind-deg", type=float, default=0.0, help="Wind Direction [deg] (0=North)")
    
    args = parser.parse_args()

    # 1. Load GPX
    if not os.path.exists(args.gpx):
        print(f"Error: GPX file not found: {args.gpx}")
        sys.exit(1)
        
    print(f"Loading GPX: {args.gpx} ...")
    loader = GpxLoader(args.gpx)
    loader.load()
    
    # Calculate Elevation Gain before smoothing for reference
    raw_gain = sum(max(0, loader.points[i].ele - loader.points[i-1].ele) for i in range(1, len(loader.points)))
    
    loader.smooth_elevation()
    segments = loader.compress_segments()
    
    # Calculate smoothed metrics
    total_dist = sum(s.length for s in segments)
    total_gain = sum(max(0, s.end_ele - s.start_ele) for s in segments)
    
    print(f"-> Course Stats: {total_dist/1000:.1f} km, {total_gain:.0f}m Gain (Raw: {raw_gain:.0f}m)")
    print(f"-> Course Segments: {len(segments)} (Original: {len(loader.points)} points)")

    # 2. Setup Components
    rider = Rider(cp=args.cp, w_prime_max=args.w_prime, weight=args.weight)
    
    params = PhysicsParams(
        cda=args.cda,
        crr=args.crr,
        bike_weight=args.bike_weight,
        drafting_factor=args.drafting
    )
    
    # Manual Weather Setup
    weather = WeatherClient(use_scenario_mode=True, scenario_data={
        "wind_speed": args.wind_speed,
        "wind_deg": args.wind_deg,
        "temperature": 20.0 # Default
    })
    
    engine = PhysicsEngine(rider, params, weather)
    
    # 3. Run Optimization
    print("\n[Running Physics Engine]")
    print(f"Rider: {args.cp}W CP, {args.w_prime/1000:.1f}kJ W'")
    print("Optimizing pacing strategy...")
    
    result = engine.find_optimal_pacing(segments)
    
    # 4. Report
    print("\n" + "="*40)
    print("      SIMULATION REPORT")
    print("="*40)
    
    h = int(result.total_time_sec // 3600)
    m = int((result.total_time_sec % 3600) // 60)
    s = int(result.total_time_sec % 60)
    
    print(f"Time         : {h}h {m}m {s}s")
    print(f"Avg Speed    : {result.average_speed_kmh:.1f} km/h")
    print(f"Norm Power   : {result.normalized_power:.0f} W")
    print(f"Avg Power    : {result.average_power:.0f} W")
    print(f"Work         : {result.work_kj:.0f} kJ")
    print(f"Min W' Bal   : {result.w_prime_min/1000:.1f} kJ (Remaining)")
    print("-" * 40)
    print(f"Recommended P_base : {result.base_power:.0f} W")
    
    if result.is_success:
        print("Status       : SUCCESS (Feasible)")
        
        # Save detailed logs for visualization
        import json
        import math # Ensure math is available in this scope if needed
        output_data = {
            "summary": {
                "time_str": f"{h}h {m}m {s}s",
                "avg_speed": result.average_speed_kmh,
                "norm_power": result.normalized_power,
                "work_kj": result.work_kj
            },
            "segments": []
        }
        
        # We need to re-run the simulation with optimal P_base to capture segment data
        # Or modify simulate_course/find_optimal_pacing to return the log.
        # For simplicity, let's just re-run simulation logic here since we have the params.
        
        # Re-run for data capture
        print("\nGenerated simulation details for visualization...")
        engine.rider.reset_state()
        curr_v = 0.0
        cum_dist = 0.0
        
        # Re-calc limit for consistency
        est_hours = total_dist/1000.0 / 25.0
        # Use Riegel limit if applied in solver? Yes, but p_base is already the result.
        
        for seg in segments:
            # We need max_power_limit again. 
            # In solver, we used max_cap_factor * cp
            # Let's assume safety cap logic is consistent.
            # Riegel logic was applied to SEARCH SPACE, not cap per segment.
            # Max Cap Factor was used in simulate_course.
            
            # Recalculate caps (Consistency is tricky without refactoring)
            # Let's trust P_base result and apply basic cap.
            # Solver used: max_cap_factor = rider.get_dynamic_max_cap(est_hours)
            
            # Using the optimal P_base found
            p_base = result.base_power
            # Recalculate max cap for the estimated duration found by solver?
            # Actually solver used 'est_hours' from rough estimate.
            max_cap = engine.rider.get_dynamic_max_cap(est_hours) * engine.rider.cp
            
            p_target = engine._calculate_target_power(p_base, seg.grade, max_cap)
            
            # Wind (Scenario)
            wind_s = args.wind_speed
            wind_d = args.wind_deg
            rel_angle = math.radians(wind_d - seg.heading)
            v_headwind = wind_s * math.cos(rel_angle)
            
            v_next, t_sec = engine._solve_segment_physics(seg, p_target, curr_v, v_headwind)
            engine.rider.update_w_prime(p_target, t_sec)
            
            cum_dist += seg.length
            
            output_data["segments"].append({
                "dist_km": cum_dist / 1000.0,
                "ele": seg.end_ele,
                "grade_pct": seg.grade * 100,
                "speed_kmh": (v_next * 3.6),
                "power": p_target,
                "w_prime": engine.rider.w_prime_bal
            })
            curr_v = v_next
            
        with open("simulation_result.json", "w") as f:
            json.dump(output_data, f, indent=2)
        print("Saved to simulation_result.json")

    else:
        print("Status       : FAILED (Bonk Risk)")
        print(f"Reason       : {result.fail_reason}")
    print("="*40)

if __name__ == "__main__":
    main()
