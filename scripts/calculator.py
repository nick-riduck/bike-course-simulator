from __future__ import annotations
import sys
import os
import math

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.gpx_loader import GpxLoader
from src.core.rider import Rider
from src.engines.base import PhysicsEngine, PhysicsParams

def find_weight_for_target(gpx_path: str, target_time_str: str, target_power: float, cda: float = 0.38):
    """
    Find the rider weight required to achieve a specific time at a specific average power.
    
    Args:
        gpx_path: Path to GPX file.
        target_time_str: "MM:SS" format (e.g., "5:40").
        target_power: Average Power in Watts (e.g., 447).
        cda: Coefficient of Drag * Area (default 0.38).
    """
    # Parse Time
    try:
        m, s = map(int, target_time_str.split(':'))
        target_seconds = m * 60 + s
    except ValueError:
        print("Error: Time must be in MM:SS format")
        return

    # Load Course
    if not os.path.exists(gpx_path):
        print(f"Error: File {gpx_path} not found.")
        return

    loader = GpxLoader(gpx_path)
    loader.load()
    loader.smooth_elevation()
    segments = loader.compress_segments()
    
    total_dist = sum(s.length for s in segments)
    total_gain = sum(max(0, s.end_ele - s.start_ele) for s in segments)
    print(f"Course Loaded: {total_dist/1000:.2f}km, {total_gain:.0f}m 획고")
    print(f"Target: {target_time_str} ({target_seconds}s) @ {target_power}W Avg (CdA: {cda})")

    # Binary Search for Weight
    low_w = 30.0
    high_w = 150.0
    
    best_weight = 0.0
    best_time = 0.0
    
    print(f"Calculating...")
    
    for _ in range(20): # Precision loop
        mid_w = (low_w + high_w) / 2
        
        # We need to find the specific p_base that results in target_power Avg
        # effectively solving: simulate(weight=mid_w, p_base=?) -> avg_power == target_power
        
        # Inner search for p_base to match target_power exactly
        # Because physics engine scales p_base based on grade, input p_base != output Avg Power
        p_base_found = _solve_p_base_for_avg_power(segments, mid_w, target_power, cda)
        
        # Now run simulation with this p_base to get time
        rider = Rider(cp=500, w_prime_max=30000, weight=mid_w) # CP high enough to not bonk
        params = PhysicsParams(bike_weight=8.0, cda=cda) # Standard bike
        engine = PhysicsEngine(rider, params)
        
        # Calculate Max Power Limit (High enough to not be a bottleneck, we are testing theoretical required weight)
        # Using a fixed high limit
        res = engine.simulate_course(segments, p_base_found, max_power_limit=2000.0)
        
        time_diff = res.total_time_sec - target_seconds
        
        # print(f"Debug: W={mid_w:.2f}kg, P_base={p_base_found:.1f}W -> Time={res.total_time_sec:.1f}s (Diff {time_diff:.1f}s)")
        
        if abs(time_diff) < 0.5:
            best_weight = mid_w
            best_time = res.total_time_sec
            break
        
        if time_diff > 0:
            # Too slow -> Need to be lighter
            high_w = mid_w
        else:
            # Too fast -> Can be heavier
            low_w = mid_w
            
        best_weight = mid_w
        best_time = res.total_time_sec

    print("-" * 30)
    print(f"Result for {target_power}W @ {target_time_str} (CdA {cda}):")
    print(f"Required Weight: {best_weight:.2f} kg")
    print(f"Simulated Time : {int(best_time//60)}:{int(best_time%60):02d}")
    print("-" * 30)

def _solve_p_base_for_avg_power(segments, weight, target_avg, cda):
    """
    Find p_base such that the simulation results in target_avg power.
    Using simple bisection.
    """
    low = 0.0
    high = target_avg * 2.0
    
    rider = Rider(cp=1000, w_prime_max=100000, weight=weight)
    params = PhysicsParams(bike_weight=8.0, cda=cda)
    engine = PhysicsEngine(rider, params)
    
    for _ in range(10):
        mid = (low + high) / 2
        res = engine.simulate_course(segments, mid, max_power_limit=2000.0)
        if res.average_power < target_avg:
            low = mid
        else:
            high = mid
    return (low + high) / 2

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python calculator.py <gpx_file> <time_mm:ss> <power_watts> [cda]")
    else:
        cda_val = 0.38
        if len(sys.argv) >= 5:
            cda_val = float(sys.argv[4])
            
        find_weight_for_target(sys.argv[1], sys.argv[2], float(sys.argv[3]), cda_val)
