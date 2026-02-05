import sys
import os
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.ode_validator import PyfunValidator
from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams
from src.gpx_loader import Segment, GpxLoader

def run_check():
    # 1. Setup Validator
    # Setup Legacy Engine (Target)
    rider = Rider(weight=81.0, cp=300, w_prime_max=20000) # Rider 81kg
    params = PhysicsParams(
        bike_weight=10.0, 
        cda=0.314, 
        crr=0.003, 
        drivetrain_loss=0.03
    )
    engine = PhysicsEngine(rider, params)
    
    # Setup Validator (Same Params)
    validator = PyfunValidator(
        rider_mass=rider.weight,
        bike_mass=params.bike_weight,
        cda=params.cda,
        crr=params.crr,
        loss=params.drivetrain_loss
    )
    
    print(f"=== Physics Kernel Accuracy Check ===")
    print(f"Params: Mass={rider.weight+params.bike_weight}kg, CdA={params.cda}, Crr={params.crr}, Loss={params.drivetrain_loss}")
    print(f"{'Case':<25} | {'Input':<30} | {'Legacy':<10} | {'Exact(ODE)':<10} | {'Diff':<10} | {'Result':<6}")
    print("-" * 110)
    
    # Define Test Cases
    # (Name, v_init_kmh, dist_m, grade_pct, power_w)
    cases = [
        ("1. Flat Accel", 30.0, 1000.0, 0.0, 200.0),
        ("2. Uphill Grind", 10.0, 500.0, 10.0, 300.0),
        ("3. Downhill (No Brake)", 40.0, 1000.0, -3.0, 0.0),
        ("4. Downhill (Brake)", 60.0, 1000.0, -10.0, 0.0), # > 50km/h check
        ("5. Walking Mode", 3.0, 100.0, 15.0, 100.0),
    ]
    
    for name, v_kmh, dist, grade_pct, power in cases:
        v_in = v_kmh / 3.6
        grade = grade_pct / 100.0
        
        # 1. Legacy Engine Calculation
        dummy_seg = Segment(0, 0, dist, dist, grade, 0, 0, 0) 
        dummy_seg.length = dist
        dummy_seg.grade = grade
        
        v_next_legacy, t_leg, _, _ = engine._solve_segment_physics(dummy_seg, power, v_in, 0.0, 9999.0)
        
        # 2. Validator Calculation
        v_next_ode, t_ode = validator.get_exact_final_speed(v_in, dist, grade, power)
        
        # Compare
        v_leg_kmh = v_next_legacy * 3.6
        v_ode_kmh = v_next_ode * 3.6
        diff = v_leg_kmh - v_ode_kmh
        
        pass_fail = "PASS" if abs(diff) < 0.1 else "FAIL"
        
        input_str = f"{v_kmh}kmh/{power}W/{grade_pct}%"
        print(f"{name:<25} | {input_str:<30} | {v_leg_kmh:>8.2f}km/h | {v_ode_kmh:>8.2f}km/h | {diff:>+8.2f} | {pass_fail}")

    print("-" * 110)

def run_real_world_test(gpx_path, engine, validator):
    if not os.path.exists(gpx_path):
        print(f"Skipping {gpx_path}: File not found.")
        return

    print(f"\n>>> Running Real World Test on: {gpx_path}")
    loader = GpxLoader(gpx_path)
    loader.load()
    segments = loader.compress_segments()
    print(f"Loaded {len(segments)} segments.")

    # Re-implementation of loop for clarity
    v_curr_leg = 0.1
    v_curr_ode = 0.1
    
    t_total_leg = 0.0
    t_total_ode = 0.0
    
    fixed_power = 200.0
    
    max_diff = 0.0
    sum_diff = 0.0
    count = 0

    print(f"{'Seg#':<6} | {'Dist':<8} | {'Grade':<7} | {'Power':<7} | {'V_in':<8} | {'V_Leg':<8} | {'V_ODE':<8} | {'Diff':<8}")
    print("-" * 90)

    for i, seg in enumerate(segments):
        # 1. Legacy Kernel (Cascading)
        v_next_leg, t_leg, _, _ = engine._solve_segment_physics(seg, fixed_power, v_curr_leg, 0.0, 9999.0)
        t_total_leg += t_leg
        
        # 2. ODE Validator (Cascading)
        v_next_ode, t_ode = validator.get_exact_final_speed(v_curr_ode, seg.length, seg.grade, fixed_power)
        t_total_ode += t_ode
        
        # Compare Speed
        diff = abs(v_next_leg - v_next_ode) * 3.6
        max_diff = max(max_diff, diff)
        sum_diff += diff
        count += 1
        
        # Print large errors
        if diff > 1.5: # Tolerance up slightly
            print(f"{i:<6} | {seg.length:<8.1f} | {seg.grade*100:<7.1f} | {fixed_power:<7.1f} | {v_curr_leg*3.6:<8.1f} | {v_next_leg*3.6:<8.1f} | {v_next_ode*3.6:<8.1f} | {diff:<8.2f}")
        
        # Update v_curr for next step (Cascading Mode)
        v_curr_leg = v_next_leg
        v_curr_ode = v_next_ode 
        
    avg_diff = sum_diff / count if count > 0 else 0
    
    # Calculate Time Difference
    time_diff_sec = t_total_leg - t_total_ode
    time_diff_fmt = f"{int(time_diff_sec//60)}m {int(abs(time_diff_sec)%60)}s"
    
    print("-" * 90)
    print(f"Total Segments: {count}")
    print(f"Max Speed Diff: {max_diff:.2f} km/h")
    print(f"Avg Speed Diff: {avg_diff:.2f} km/h")
    print(f"Total Time: Legacy {int(t_total_leg//60)}m {int(t_total_leg%60)}s vs ODE {int(t_total_ode//60)}m {int(t_total_ode%60)}s")
    print(f"Time Diff: {time_diff_fmt} ({time_diff_sec:.2f}s)")
    
    if abs(time_diff_sec) < 60.0: # 1 minute tolerance for long course
        print("RESULT: PASS (Real World Consistency Verified)")
    else:
        print("RESULT: WARNING (Time Divergence > 1 min)")


if __name__ == "__main__":
    # Setup Engine & Validator
    rider = Rider(weight=81.0, cp=300, w_prime_max=20000)
    params = PhysicsParams(bike_weight=10.0, cda=0.314, crr=0.003, drivetrain_loss=0.03)
    engine = PhysicsEngine(rider, params)
    validator = PyfunValidator(rider.weight, params.bike_weight, params.cda, params.crr, params.drivetrain_loss)

    run_check()
    
    # Run Real World Tests
    run_real_world_test("분원리뺑.gpx", engine, validator)
    run_real_world_test("20seorak.gpx", engine, validator)
