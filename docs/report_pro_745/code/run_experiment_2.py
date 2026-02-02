import time
import os
import sys
from common import Rider, PhysicsParams, Segment, GpxLoader
from engine_core import PhysicsEngine
from validator import PyfunValidator

def run_experiment_2():
    print("=== Experiment 2: Field Test (Real World GPX) ===")
    
    rider = Rider(weight=81.0, cp=300)
    params = PhysicsParams(bike_weight=10.0, cda=0.314, crr=0.003, drivetrain_loss=0.03)
    engine = PhysicsEngine(rider, params)
    # Disable Pacing for ISO-POWER comparison
    engine.alpha_climb = 0.0
    engine.alpha_descent = 0.0
    
    validator = PyfunValidator(rider.weight, params.bike_weight, params.cda, params.crr, params.drivetrain_loss)
    
    # Warm-up Numba (Run dummy once to compile)
    dummy_seg = Segment(0, 0, 100.0, 100.0, 0.0, 0, 0, 0)
    engine._solve_segment_physics(dummy_seg, 200.0, 10.0, 0.0, 1000.0)

    # Files must be in the same directory
    gpx_files = [
        {"path": "분원리뺑.gpx", "name": "Bunwon (22km)"},
        {"path": "20seorak.gpx", "name": "Seorak (208km)"}
    ]
    
    print(f"| 코스 (Course) | Proposed (Time) | Validator (Time) | 시간 오차 | 오차율 | 연산 시간 (Prop vs Valid) |")
    print(f"| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for f in gpx_files:
        if not os.path.exists(f['path']):
            print(f"| {f['name']} | File Not Found | - | - | - | - |")
            continue
            
        loader = GpxLoader(f['path'])
        loader.load()
        segments = loader.compress_segments()
        
        if not segments:
            print(f"| {f['name']} | No Segments Loaded | - | - | - | - |")
            continue

        # 1. Proposed (Numba Optimized)
        start_t = time.time()
        sim_res = engine.simulate_course(segments, p_base=200.0, max_power_limit=500.0)
        prop_calc_time = time.time() - start_t
        prop_finish_time = sim_res.total_time_sec
        
        # 2. Validator (Scipy Adaptive)
        start_t = time.time()
        valid_finish_time = 0.0
        v_curr = 0.1
        for seg in segments:
            v_next, t_seg = validator.get_exact_final_speed(v_curr, seg.length, seg.grade, 200.0)
            valid_finish_time += t_seg
            v_curr = v_next
        valid_calc_time = time.time() - start_t
        
        # Result formatting
        diff = prop_finish_time - valid_finish_time
        diff_pct = (diff / valid_finish_time) * 100 if valid_finish_time > 0 else 0.0
        
        def fmt_hms(sec):
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            return f"{h}h {m}m {s}s"

        print(f"| **{f['name']}** | {fmt_hms(prop_finish_time)} | {fmt_hms(valid_finish_time)} | {diff:+.1f}s | {diff_pct:+.2f}% | **{prop_calc_time:.4f}s** vs {valid_calc_time:.4f}s |")

if __name__ == "__main__":
    run_experiment_2()