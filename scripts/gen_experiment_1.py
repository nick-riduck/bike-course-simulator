import sys
import os
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.ode_validator import PyfunValidator
from src.core.rider import Rider
from src.engines.base import PhysicsEngine, PhysicsParams
from src.core.gpx_loader import Segment

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

def calculate_legacy_air_density(temp_c, alt_m):
    # (1.293 - 0.00426 * T) * exp(...)
    return (1.293 - 0.00426 * temp_c) * math.exp(-(alt_m * 0.709) / 7000.0)

def calculate_legacy_drivetrain_loss(dt_name, power):
    # 1. Base Efficiency
    dt_map = { "105": 0.961, "ultegra": 0.962, "duraAce": 0.963 }
    base_eff = dt_map.get(dt_name, 0.961) # Default to 105 if not found
    
    # 2. Power Factor
    pm = max(50.0, min(400.0, float(power)))
    r = 2.1246 * math.log(pm) - 11.5
    
    # 3. Total Efficiency
    efficiency = (r + base_eff * 100.0) / 100.0
    return 1.0 - efficiency

def run_experiment_1():
    print("=== Experiment 1: Algorithm Precision & Segmentation Logic Validation ===")
    
    # 1. Calculate Exact Params from Legacy Logic
    temp_c = 15.0
    alt_m = 0.0
    power = 200.0
    
    air_density = calculate_legacy_air_density(temp_c, alt_m)
    dt_loss = calculate_legacy_drivetrain_loss("105", power)
    
    print(f"DEBUG: Air Density={air_density:.4f}, DT Loss={dt_loss:.4f} (Eff={1-dt_loss:.4f})")

    # Rider: 80kg, Bike: 10kg + 1.0kg(Legacy Extra), CdA: 0.314288, Crr: 0.003085
    rider = Rider(weight=80.0, cp=300, w_prime_max=20000)
    params = PhysicsParams(
        bike_weight=11.0, # 10.0 + 1.0 (Legacy adjustment)
        cda=0.314288, 
        crr=0.003085, 
        drivetrain_loss=dt_loss,
        air_density=air_density
    )
    
    engine = PhysicsEngine(rider, params)
    # Disable Pacing Strategy for ISO-POWER comparison
    engine.alpha_climb = 0.0
    engine.alpha_descent = 0.0
    
    # Match all params for Validator
    validator = PyfunValidator(
        rider_mass=rider.weight, 
        bike_mass=params.bike_weight, 
        cda=params.cda, 
        crr=params.crr, 
        loss=params.drivetrain_loss,
        rho=air_density
    )
    
    # 2. Define Cases
    cases = [
        {
            "name": "Case 1 (Flat)", 
            "dist_km": 100.0, "grade_pct": 0.0, "power": 200.0, 
            "legacy_time": "2h 55m 27s", "legacy_spd": 34.2
        },
        {
            "name": "Case 2 (Hill)", 
            "dist_km": 30.0, "grade_pct": 3.33, "power": 200.0, 
            "legacy_time": "1h 37m 51s", "legacy_spd": 18.4
        },
        {
            "name": "Case 3 (Mountain)", 
            "dist_km": 10.0, "grade_pct": 8.0, "power": 200.0, 
            "legacy_time": "1h 05m 29s", "legacy_spd": 9.16
        }
    ]
    
    print(f"| Case | Model | V_avg (km/h) | V_final (km/h) | Time | Note |")
    print(f"| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for case in cases:
        dist_m = case["dist_km"] * 1000.0
        grade = case["grade_pct"] / 100.0
        power = case["power"]
        
        # --- A. Legacy (Baseline) ---
        print(f"| **{case['name']}** | Legacy | {case['legacy_spd']} | - | {case['legacy_time']} | Baseline |")
        
        # --- B. Proposed (Single Step) ---
        # Force single step by creating one long segment and running kernel once
        # Note: _solve_segment_physics normally chunks internally.
        # We need to simulate "What if we didn't chunk?"
        # To do this, we can call the kernel with a huge chunk_size logic modification
        # OR just use a simplified energy calculation here.
        # Let's use a modified call to the internal logic if possible, or replicate the error.
        
        # Replicating Single Step Logic:
        # 0.5*m*(v^2 - 0) = (F_pedal - F_drag_avg - ...) * d
        # F_drag_avg calculated at V_avg = (0 + v)/2
        # Note: Legacy adds 1.0kg for gear/shoes etc.
        
        v_final_single = simulate_single_step_flawed(rider.weight+params.bike_weight+1.0, params, dist_m, grade, power)
        v_avg_single = v_final_single / 2.0 # Assuming linear accel from 0
        time_single = dist_m / v_avg_single if v_avg_single > 0 else 0
        print(f"| | Proposed (Single) | {v_avg_single*3.6:.2f} | {v_final_single*3.6:.2f} | {format_time(time_single)} | **Final Speed Error** |")
        
        # --- C. Proposed (20m Split) ---
        # Run kernel directly to get exact v_final and time
        # This uses the internal chunking logic (20m split)
        seg = Segment(0, 0, dist_m, dist_m, grade, 0, 0, 0)
        v_next_split, time_split, _, _ = engine._solve_segment_physics(seg, power, 0.1, 0.0, 9999.0)
        
        v_avg_split_kmh = (dist_m / time_split) * 3.6
        v_final_split_kmh = v_next_split * 3.6
        
        print(f"| | Proposed (20m Split) | {v_avg_split_kmh:.2f} | {v_final_split_kmh:.2f} | {format_time(time_split)} | Validated |")
        
        # --- D. Validator (Exact) ---
        v_final_ode, t_ode = validator.get_exact_final_speed(0.1, dist_m, grade, power)
        v_avg_ode = (dist_m / t_ode) * 3.6
        print(f"| | Validator (Exact) | {v_avg_ode:.2f} | {v_final_ode*3.6:.2f} | {format_time(t_ode)} | Ground Truth |")

def simulate_single_step_flawed(total_mass, params, dist, grade, power):
    # This simulates the error of using one big step with average speed assumption
    # Work-Energy: 0.5*m*v^2 = (P/v_avg - 0.5*rho*CdA*v_avg^2 - ...)*d
    # where v_avg = v/2
    
    g = 9.81
    eff_cda = params.cda
    p_wheel = power * (1 - params.drivetrain_loss)
    f_const = total_mass * g * (grade + params.crr)
    # Use params.air_density if available, else standard
    rho = getattr(params, 'air_density', 1.225)
    
    # Bisection to find v_final
    low, high = 0.1, 100.0
    for _ in range(50):
        v = (low + high) / 2
        v_avg = v / 2.0
        
        f_pedal = p_wheel / v_avg
        f_drag = 0.5 * rho * eff_cda * (v_avg ** 2)
        f_net = f_pedal - f_drag - f_const
        
        work_net = f_net * dist
        ke_final = 0.5 * total_mass * v**2
        
        if work_net > ke_final:
            low = v
        else:
            high = v
            
    return (low + high) / 2

if __name__ == "__main__":
    run_experiment_1()
