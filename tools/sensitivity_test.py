import sys
import os
import math

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams, SimulationResult

# 테스트용 엔진 (f_max_factor를 외부에서 주입받을 수 있게 오버라이딩)
class SensitivityEngine(PhysicsEngine):
    def __init__(self, rider, params):
        super().__init__(rider, params)
        self.test_f_max_factor = 1.5

    def set_f_max_factor(self, factor):
        self.test_f_max_factor = factor

    def simulate_course(self, segments, p_base, max_power_limit):
        self.rider.reset_state()
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 20.0 / 3.6 
        
        f_max_initial = self.rider.weight * 9.81 * self.test_f_max_factor

        for seg in segments:
            p_target = self._calculate_target_power(p_base, seg.grade, max_power_limit)
            decay_factor = (3600.0 / max(3600.0, total_time)) ** 0.05
            current_f_limit = f_max_initial * decay_factor
            
            # Unpack 3 values (v_next, time_sec, is_walking)
            v_next, time_sec, is_walking = self._solve_segment_physics(seg, p_target, v_current, 0.0, f_limit=current_f_limit)
            
            if is_walking:
                p_actual = 30.0
            else:
                v_avg = (v_current + v_next) / 2
                if v_avg < 0.1: v_avg = 0.1
                
                p_avail_required = p_target * (1 - self.params.drivetrain_loss)
                f_required = p_avail_required / v_avg
                f_actual_wheel = min(f_required, current_f_limit)
                p_actual = (f_actual_wheel * v_avg) / (1 - self.params.drivetrain_loss)
            
            self.rider.update_w_prime(p_actual, time_sec)
            if self.rider.is_bonked():
                return SimulationResult(total_time, p_base, 0, 0, 0, 0, -1, False, "BONK")
            
            total_time += time_sec
            total_work += p_actual * time_sec
            weighted_power_sum += (p_actual ** 4) * time_sec
            v_current = v_next 
            
        avg_spd = (sum(s.length for s in segments) / 1000.0 * 3600) / total_time
        avg_p = total_work / total_time
        np = math.pow(weighted_power_sum / total_time, 0.25)
        
        return SimulationResult(total_time, p_base, avg_spd, avg_p, np, total_work/1000, 0, True)

def print_results(results):
    print(f"{ 'F_Factor':<10} | { 'Time (min)':<12} | { 'Avg Spd':<10} | { 'NP (W)':<10} | { 'Real Avg P':<10}")
    print("-" * 70)
    for r in results:
        print(f"{r['F_Factor']:<10} | {r['Time (min)']:<12} | {r['Avg Spd']:<10} | {r['NP (W)']:<10} | {r['Real Avg P']:<10}")

def run_test(gpx_path, course_name):
    print(f"\n>>> Course: {course_name} ({gpx_path})")
    loader = GpxLoader(gpx_path)
    loader.load()
    segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)
    
    # Rider Setup (Dummy for Short courses, overridden for Seorak)
    rider = Rider(weight=75, cp=280, w_prime_max=20000)
    rider.pdc = {5: 1000, 60: 500, 300: 400, 1200: 320, 3600: 280}
    
    # Seorak Override
    if "seorak" in gpx_path:
        rider = Rider(weight=85, cp=281, w_prime_max=52000)
        rider.pdc = {5: 978, 15: 836, 30: 658, 60: 519, 120: 461, 180: 442, 300: 424, 480: 390, 600: 370, 1200: 314, 3600: 296}

    params = PhysicsParams(bike_weight=8.5)
    engine = SensitivityEngine(rider, params)
    
    results = []
    factors = [1.0, 1.2, 1.5, 2.0]
    
    for f in factors:
        engine.set_f_max_factor(f)
        # Use Solver
        res_obj = engine.find_optimal_pacing(segments)
        
        if res_obj.is_success:
            results.append({
                "F_Factor": f,
                "Time (min)": round(res_obj.total_time_sec/60, 2),
                "Avg Spd": round(res_obj.average_speed_kmh, 2),
                "NP (W)": round(res_obj.normalized_power, 1),
                "Real Avg P": round(res_obj.average_power, 1)
            })
        else:
            results.append({"F_Factor": f, "Time (min)": "BONK", "Avg Spd": "-", "NP (W)": "-", "Real Avg P": "-"})
            
    print_results(results)

if __name__ == "__main__":
    run_test("북악공인구간.gpx", "Bukak Climb")
    bunwonri = "분원리뺑.gpx"
    run_test(bunwonri, "Bunwonri Rolling")
    
    print(f"\n>>> Course: Seorak Granfondo (20seorak.gpx) [Rider A: 85kg, CP 281]")
    # Run Seorak logic inside run_test to reuse code
    run_test("20seorak.gpx", "Seorak Granfondo")
