import sys
import os
import json
import math

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.rider import Rider
from src.physics_engine_v2 import PhysicsEngineV2, PhysicsParams
from src.physics_engine_theory import TheoryEngine

def load_rider():
    with open('rider_data.json', 'r') as f:
        data = json.load(f)
        r = data['rider_a']
        # W'를 무한대로 설정하여 페이싱 전략 자체의 효율성만 비교 (Bonk 방지)
        rider = Rider(weight=r['weight_kg'], cp=r['cp'], w_prime_max=1e9) 
        rider.pdc = {int(k): float(v) for k, v in r['pdc'].items()}
        return rider

def find_pbase_for_work(engine, segments, target_work_kj):
    """이분 탐색으로 목표 에너지(kJ)에 맞는 P_base를 찾음"""
    low, high = 10.0, 600.0
    best_res = None
    
    for i in range(20): # 더 정밀하게 20회 반복
        mid = (low + high) / 2
        res = engine.simulate_course(segments, p_base=mid, max_power_limit=1500.0)
        
        if res.work_kj < target_work_kj:
            low = mid
        else:
            high = mid
            best_res = res
            
    return best_res

def run_iso_work_test(gpx_path):
    loader = GpxLoader(gpx_path)
    loader.load()
    segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)
    
    rider = load_rider()
    params = PhysicsParams(bike_weight=8.5, cda=0.30, crr=0.0045, drivetrain_loss=0.05, air_density=1.225, drafting_factor=0.0)
    
    # 1. Asymmetric 모델 실행 (기준 에너지 획득)
    engine_asym = PhysicsEngineV2(rider, params)
    engine_asym.set_tuning('asymmetric', slow=0.6, fast=1.5)
    # Asymmetric 주행 (NP 258W 한계 근처에서의 에너지 소모량 확인)
    res_asym_ref = engine_asym.simulate_course(segments, p_base=225.0, max_power_limit=1000.0)
    target_work = res_asym_ref.work_kj
    
    print(f"\n[Step 1] Asymmetric Reference")
    print(f"Time: {int(res_asym_ref.total_time_sec//3600)}h {int((res_asym_ref.total_time_sec%3600)//60)}m {int(res_asym_ref.total_time_sec%60)}s")
    print(f"Work: {target_work:.1f} kJ, NP: {res_asym_ref.normalized_power:.1f}W")

    # 2. Theory 모델 실행 (이분 탐색으로 에너지 일치)
    print(f"\n[Step 2] Matching Theory Engine to {target_work:.1f} kJ...")
    engine_theory = TheoryEngine(rider, params)
    res_theory = find_pbase_for_work(engine_theory, segments, target_work)
    
    print(f"Time: {int(res_theory.total_time_sec//3600)}h {int((res_theory.total_time_sec%3600)//60)}m {int(res_theory.total_time_sec%60)}s")
    print(f"Work: {res_theory.work_kj:.1f} kJ, NP: {res_theory.normalized_power:.1f}W")

    # 3. 결과 비교
    diff_sec = res_theory.total_time_sec - res_asym_ref.total_time_sec
    print(f"\n[Conclusion]")
    if diff_sec > 0:
        print(f"Asymmetric is FASTER than Theory by {abs(diff_sec):.1f} seconds.")
    else:
        print(f"Theory is FASTER than Asymmetric by {abs(diff_sec):.1f} seconds.")

if __name__ == "__main__":
    run_iso_work_test("20seorak.gpx")
