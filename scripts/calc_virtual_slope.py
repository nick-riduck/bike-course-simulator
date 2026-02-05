
import sys
import os
import argparse
import math

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams
from src.gpx_loader import Segment

def create_virtual_segment(distance_km, elevation_gain_m):
    """
    Creates a single straight segment with constant grade.
    """
    dist_m = distance_km * 1000.0
    grade = elevation_gain_m / dist_m if dist_m > 0 else 0
    
    # Create a single segment
    # Lat/Lon are dummy values (not used for physics except heading)
    seg = Segment(
        index=0,
        start_dist=0.0,
        end_dist=dist_m,
        length=dist_m,
        grade=grade,
        heading=0.0,
        start_ele=0.0,
        end_ele=elevation_gain_m,
        lat=37.1, lon=127.1, # End point
        start_lat=37.0, start_lon=127.0,
        shifted_start_lat=0.0, shifted_start_lon=0.0,
        shifted_end_lat=0.0, shifted_end_lon=0.0
    )
    return [seg]

def run_virtual_test(args):
    # 1. Input Validation
    if args.grade is not None:
        gain = (args.dist * 1000) * (args.grade / 100)
        print(f"Virtual Course: {args.dist} km @ {args.grade}% Grade (Calc Gain: {gain:.1f} m)")
    else:
        gain = args.gain
        grade = (gain / (args.dist * 1000)) * 100
        print(f"Virtual Course: {args.dist} km, Gain {gain} m (Avg Grade: {grade:.2f}%)")

    # 2. Rider Setup
    # Default Rider A
    weight = args.weight if args.weight else 85.0
    cp = 281.0
    w_prime = 52000.0
    
    rider = Rider(weight=weight, cp=cp, w_prime_max=w_prime)
    
    # Rider A's PDC (Used if power is not specified)
    rider.pdc = {
        5: 978, 15: 836, 30: 658, 60: 519, 120: 461, 
        180: 442, 300: 424, 480: 390, 600: 370, 1200: 314, 3600: 296
    }
    
    params = PhysicsParams(bike_weight=8.5)
    engine = PhysicsEngine(rider, params)
    
    segments = create_virtual_segment(args.dist, gain)
    
    # 3. Simulation
    if args.power:
        print(f"Mode: Fixed Power ({args.power} W)")
        # max_power_limit을 넉넉하게 주어 토크 리밋 외에는 제한 없게 함
        result = engine.simulate_course(segments, p_base=float(args.power), max_power_limit=float(args.power)*1.5)
    else:
        print(f"Mode: Optimal Pacing (Rider A Capability)")
        result = engine.find_optimal_pacing(segments)
        
    # 4. Result Output
    h = int(result.total_time_sec // 3600)
    m = int((result.total_time_sec % 3600) // 60)
    s = int(result.total_time_sec % 60)
    
    print("-" * 40)
    if result.is_success:
        print(f"Time       : {h}h {m}m {s}s")
        print(f"Avg Speed  : {result.average_speed_kmh:.2f} km/h")
        print(f"Avg Power  : {result.average_power:.1f} W")
        print(f"NP         : {result.normalized_power:.1f} W")
        print(f"VAM        : {gain / (result.total_time_sec/3600):.0f} m/h")
        if not args.power:
            print(f"PDC Limit  : {engine._get_dynamic_pdc_limit(result.total_time_sec):.1f} W")
    else:
        print("Result     : DNF (BONK)")
        print(f"Last Time  : {h}h {m}m {s}s")
    print("-" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bike Simulator Virtual Slope Calculator")
    parser.add_argument("--dist", type=float, required=True, help="Distance in km")
    parser.add_argument("--gain", type=float, help="Elevation gain in meters")
    parser.add_argument("--grade", type=float, help="Average grade in %% (optional, overrides gain)")
    parser.add_argument("--power", type=float, help="Target power in Watts (optional)")
    parser.add_argument("--weight", type=float, help="Rider weight in kg (default: 85)")
    
    args = parser.parse_args()
    
    if args.gain is None and args.grade is None:
        parser.error("Either --gain or --grade must be provided")
        
    run_virtual_test(args)
