
import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams

def run_seorak_test():
    gpx_path = "20seorak.gpx"
    loader = GpxLoader(gpx_path)
    loader.load()
    segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)
    
    # Rider A (User - 85kg)
    rider = Rider(weight=85, cp=281, w_prime_max=52000)
    # 실제 PDC 데이터 반영
    rider.pdc = {
        "5": 978, "15": 836, "30": 658, "60": 519, "120": 461, 
        "180": 442, "300": 424, "480": 390, "600": 370, "1200": 314, "3600": 296
    }
    
    params = PhysicsParams(bike_weight=8.5)
    engine = PhysicsEngine(rider, params)
    
    print(f"--- Simulating Seorak Granfondo ---")
    result = engine.find_optimal_pacing(segments)
    
    h = int(result.total_time_sec // 3600)
    m = int((result.total_time_sec % 3600) // 60)
    s = int(result.total_time_sec % 60)
    
    print(f"\n[Final Result]")
    print(f"Total Time : {h}h {m}m {s}s")
    print(f"Avg Speed  : {result.average_speed_kmh:.2f} km/h")
    print(f"Avg Power  : {result.average_power:.1f} W")
    print(f"NP         : {result.normalized_power:.1f} W")
    print(f"Total Work : {result.work_kj:.1f} kJ")
    print(f"Success    : {result.is_success}")

if __name__ == "__main__":
    run_seorak_test()
