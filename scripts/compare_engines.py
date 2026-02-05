
import math
import sys
import os
import csv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.rider import Rider
from src.gpx_loader import GpxLoader
from src.physics_engine import PhysicsEngine, PhysicsParams as ParamsV1
from src.physics_engine_v2 import PhysicsEngineV2, PhysicsParams
from src.physics_engine_v3 import PhysicsEngineV3
from src.physics_engine_v3_1 import PhysicsEngineV3_1
from src.physics_engine_v4 import PhysicsEngineV4
from src.physics_engine_v5 import PhysicsEngineV5
from src.physics_engine_gordon import GordonTheoryEngine

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"

def save_track_data(engine_name, result):
    if not result or not result.track_data:
        return
    
    filename = f"track_data_{engine_name}.csv"
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['dist_km', 'grade_pct', 'speed_kmh', 'power_watts', 'time_sec']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for p in result.track_data:
            writer.writerow({
                'dist_km': f"{p['dist_km']:.3f}",
                'grade_pct': f"{p['grade_pct']:.1f}",
                'speed_kmh': f"{p['speed_kmh']:.1f}",
                'power_watts': f"{p['power']:.1f}",
                'time_sec': f"{p['time_sec']:.1f}"
            })
    print(f"Saved {filename}")

def print_stats(name, res):
    vi = res.normalized_power / res.average_power if res.average_power > 0 else 0
    print(f"\n--- {name} ---")
    print(f"Time: {format_time(res.total_time_sec)}")
    print(f"Power: NP {res.normalized_power:.1f}W (Avg {res.average_power:.1f}W)")
    print(f"Stats: Work {res.work_kj:.1f} kJ, VI {vi:.2f}")
    save_track_data(name.split()[2].lower().replace("(", "").replace(")", ""), res)

def run_comparison():
    possible_files = ["분원리뺑.gpx", "삼막사경인교대.gpx", "tools/course_plan.gpx", "Namsan1_7.gpx"]
    gpx_file = None
    for f in possible_files:
        if os.path.exists(f):
            gpx_file = f
            break
            
    if not gpx_file:
        print("No GPX file found.")
        return

    print(f"Loading GPX: {gpx_file}")
    loader = GpxLoader(gpx_file)
    loader.load()
    segments = loader.compress_segments()
    
    rider = Rider(weight=70, cp=280, w_prime_max=20000)
    params = PhysicsParams(cda=0.32, crr=0.004, bike_weight=8.0, drivetrain_loss=0.03)

    # V2
    engine_v2 = PhysicsEngineV2(rider, params)
    res_v2 = engine_v2.find_optimal_pacing(segments)
    print_stats("Physics Engine V2 (Heuristic)", res_v2)

    # V5
    engine_v5 = PhysicsEngineV5(rider, params)
    res_v5 = engine_v5.find_optimal_pacing(segments)
    print_stats("Physics Engine V5 (Iterative Gradient)", res_v5)

if __name__ == "__main__":
    run_comparison()
