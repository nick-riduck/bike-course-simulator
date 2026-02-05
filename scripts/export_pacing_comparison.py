import sys
import os
import json
import csv

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.rider import Rider
from src.physics_engine_v2 import PhysicsEngineV2, PhysicsParams
from src.physics_engine_gordon import GordonTheoryEngine

def load_rider():
    with open('rider_data.json', 'r') as f:
        data = json.load(f)
        r = data['rider_a']
        # 공정한 비교를 위해 W' 제한 해제
        rider = Rider(weight=r['weight_kg'], cp=r['cp'], w_prime_max=1e9)
        rider.pdc = {int(k): float(v) for k, v in r['pdc'].items()}
        return rider

def save_to_csv(filename, track_data):
    keys = ["dist_km", "power", "speed_kmh", "time_sec"]
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for d in track_data:
            # 필요한 필드만 필터링하여 저장
            row = {k: d[k] for k in keys if k in d}
            writer.writerow(row)

def run_export():
    loader = GpxLoader("20seorak.gpx")
    loader.load()
    segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)
    
    rider = load_rider()
    params = PhysicsParams(bike_weight=8.5, cda=0.30, crr=0.0045, drivetrain_loss=0.05, air_density=1.225, drafting_factor=0.0)
    
    # 1. Asymmetric 모델 실행 및 저장
    print("Running Asymmetric simulation...")
    engine_asym = PhysicsEngineV2(rider, params)
    engine_asym.set_tuning('asymmetric', slow=0.6, fast=1.5)
    res_asym = engine_asym.simulate_course(segments, p_base=225.0, max_power_limit=1000.0)
    save_to_csv('asymmetric_pacing.csv', res_asym.track_data)
    target_work = res_asym.work_kj
    
    # 2. Gordon 모델 실행 및 저장 (Matched Work)
    print(f"Running Gordon Theory simulation (Target: {target_work:.1f} kJ)...")
    engine_gordon = GordonTheoryEngine(rider, params)
    res_gordon = engine_gordon.find_pbase_for_work(segments, target_work)
    save_to_csv('gordon_pacing.csv', res_gordon.track_data)
    
    print("\n>>> Export Complete!")
    print(f"- Asymmetric: asymmetric_pacing.csv ({len(res_asym.track_data)} rows)")
    print(f"- Gordon: gordon_pacing.csv ({len(res_gordon.track_data)} rows)")

if __name__ == "__main__":
    run_export()
