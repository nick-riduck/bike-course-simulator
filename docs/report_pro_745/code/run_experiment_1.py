import math
from common import Rider, PhysicsParams, Segment
from engine_core import PhysicsEngine
from validator import PyfunValidator

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

def simulate_single_step_flawed(total_mass, params, dist, grade, power, rho):
    # Flawed Logic: 0.5*m*(v^2 - 0) = (P/v_avg - Drag(v_avg) - ...) * d
    # V_avg = V / 2
    g = 9.81
    p_wheel = power * (1 - params.drivetrain_loss)
    f_const = total_mass * g * (grade + params.crr)
    eff_cda = params.cda
    
    low, high = 0.1, 150.0
    for _ in range(50):
        v = (low + high) / 2
        v_avg = v / 2.0
        f_pedal = p_wheel / v_avg
        f_drag = 0.5 * rho * eff_cda * (v_avg ** 2)
        f_net = f_pedal - f_drag - f_const
        
        work_net = f_net * dist
        ke_final = 0.5 * total_mass * v**2
        
        if work_net > ke_final: low = v
        else: high = v
    return (low + high) / 2

def run_experiment():
    print("=== Experiment 1: Algorithm Precision & Segmentation Logic Validation ===")
    
    # 1. Setup (Case 1 Settings)
    air_density = 1.2291
    dt_loss = 0.0414
    
    # Rider 80 + Bike 10 + Extra 1 (Legacy logic)
    rider = Rider(weight=80.0, cp=300)
    params = PhysicsParams(
        bike_weight=11.0, 
        cda=0.314288, 
        crr=0.003085, 
        drivetrain_loss=dt_loss,
        air_density=air_density
    )
    
    engine = PhysicsEngine(rider, params)
    # Disable Pacing for ISO-POWER comparison
    engine.alpha_climb = 0.0
    engine.alpha_descent = 0.0
    
    validator = PyfunValidator(rider.weight, params.bike_weight, params.cda, params.crr, params.drivetrain_loss, rho=air_density)
    
    cases = [
        {"name": "Case 1 (Flat)", "dist_km": 100.0, "grade_pct": 0.0, "power": 200.0, "legacy_time": "2h 55m 27s", "legacy_spd": 34.2},
        {"name": "Case 2 (Hill)", "dist_km": 30.0, "grade_pct": 3.33, "power": 200.0, "legacy_time": "1h 37m 51s", "legacy_spd": 18.4},
        {"name": "Case 3 (Mtn)", "dist_km": 10.0, "grade_pct": 8.0, "power": 200.0, "legacy_time": "1h 05m 29s", "legacy_spd": 9.16}
    ]
    
    print(f"| Case | Model | V_avg (km/h) | V_final (km/h) | Time | Note |")
    print(f"| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for case in cases:
        dist_m = case["dist_km"] * 1000.0
        grade = case["grade_pct"] / 100.0
        power = case["power"]
        
        # A. Legacy
        print(f"| **{case['name']}** | Legacy | {case['legacy_spd']} | - | {case['legacy_time']} | Baseline |")
        
        # B. Single (Flawed)
        v_final_single = simulate_single_step_flawed(rider.weight+params.bike_weight, params, dist_m, grade, power, air_density)
        v_avg_single = v_final_single / 2.0
        t_single = dist_m / v_avg_single if v_avg_single > 0 else 0
        print(f"| | Single | {v_avg_single*3.6:.2f} | {v_final_single*3.6:.2f} | {format_time(t_single)} | Error |")
        
        # C. 20m Split
        seg = Segment(0, 0, dist_m, dist_m, grade, 0, 0, 0)
        v_next, time_split, _, _ = engine._solve_segment_physics(seg, power, 0.1, 0.0, 9999.0)
        v_avg_split = (dist_m / time_split) * 3.6
        print(f"| | 20m Split | {v_avg_split:.2f} | {v_next*3.6:.2f} | {format_time(time_split)} | Valid |")
        
        # D. Validator
        v_next_ode, t_ode = validator.get_exact_final_speed(0.1, dist_m, grade, power)
        v_avg_ode = (dist_m / t_ode) * 3.6
        print(f"| | Validator | {v_avg_ode:.2f} | {v_next_ode*3.6:.2f} | {format_time(t_ode)} | Exact |")

if __name__ == "__main__":
    run_experiment()
