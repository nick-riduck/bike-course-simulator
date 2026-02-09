import sys
import os
import json
import csv
import re

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.gpx_loader import GpxLoader
from src.core.rider import Rider
from src.engines.v2 import PhysicsEngineV2, PhysicsParams
from src.engines.base_gordon import GordonTheoryEngine

def load_rider():
    with open('rider_data.json', 'r') as f:
        data = json.load(f)
        r = data['rider_a']
        rider = Rider(weight=r['weight_kg'], cp=r['cp'], w_prime_max=1e9)
        rider.pdc = {int(k): float(v) for k, v in r['pdc'].items()}
        return rider

def load_plan_clusters(gpx_path):
    """
    Extracts clusters from <desc> JSON in course_plan.gpx
    """
    with open(gpx_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Regex to find JSON in <desc>
    match = re.search(r'<desc>(.*?)</desc>', content, re.DOTALL)
    if not match:
        print("Error: Could not find <desc> tag with JSON in course_plan.gpx")
        return []
        
    json_str = match.group(1)
    try:
        data = json.loads(json_str)
        return data['segments']
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from <desc>: {e}")
        return []

def run_export_comparison():
    # 1. Load Raw Physics Segments -> For Simulation
    sim_loader = GpxLoader("20seorak.gpx")
    sim_loader.load()
    sim_segments = sim_loader.compress_segments(grade_threshold=0.005, max_length=200.0)
    
    # 2. Load User's Cluster Plan
    plan_clusters = load_plan_clusters("tools/course_plan.gpx")
    if not plan_clusters:
        return

    rider = load_rider()
    params = PhysicsParams(bike_weight=8.5, cda=0.30, crr=0.0045, drivetrain_loss=0.05, air_density=1.225, drafting_factor=0.0)
    
    print(">>> Running Simulations...")
    # [Sim 1] Asymmetric
    engine_asym = PhysicsEngineV2(rider, params)
    engine_asym.set_tuning('asymmetric', slow=0.6, fast=1.5)
    res_asym = engine_asym.simulate_course(sim_segments, p_base=225.0, max_power_limit=1000.0)
    
    # [Sim 2] Gordon (Matched Work)
    engine_gordon = GordonTheoryEngine(rider, params)
    res_gordon = engine_gordon.find_pbase_for_work(sim_segments, res_asym.work_kj)
    
    print(">>> Exporting Full Data (pacing_full.csv)...")
    with open('pacing_full.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['dist_km', 'ele', 'grade_pct', 'asym_power', 'asym_speed', 'gordon_power', 'gordon_speed'])
        for i, d_asym in enumerate(res_asym.track_data):
            d_gordon = res_gordon.track_data[i]
            writer.writerow([
                f"{d_asym['dist_km']:.3f}",
                f"{d_asym['ele']:.1f}",
                f"{sim_segments[i].grade * 100:.1f}", 
                f"{d_asym['power']:.1f}",
                f"{d_asym['speed_kmh']:.1f}",
                f"{d_gordon['power']:.1f}",
                f"{d_gordon['speed_kmh']:.1f}"
            ])

    print(">>> Exporting Cluster Summary (pacing_summary.csv)...")
    
    with open('pacing_summary.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'start_km', 'end_km', 'len_km', 'avg_grade', 'type', 
                         'asym_avg_w', 'asym_avg_v', 'asym_time',
                         'gordon_avg_w', 'gordon_avg_v', 'gordon_time', 'time_diff'])
        
        sim_idx = 0
        for cluster in plan_clusters:
            p_start = cluster['start_dist']
            p_end = cluster['end_dist']
            p_len = p_end - p_start
            
            sub_asym_p = []
            sub_asym_t = 0
            sub_gordon_p = []
            sub_gordon_t = 0
            
            # Aggregate sim segments within this cluster
            while sim_idx < len(sim_segments):
                s_seg = sim_segments[sim_idx]
                s_center = (s_seg.start_dist + s_seg.end_dist) / 2
                
                if s_center > p_end:
                    break 
                
                # Accumulate Data
                d_asym = res_asym.track_data[sim_idx]
                d_gordon = res_gordon.track_data[sim_idx]
                
                # Time delta
                t_asym_prev = res_asym.track_data[sim_idx-1]['time_sec'] if sim_idx > 0 else 0
                t_asym_delta = d_asym['time_sec'] - t_asym_prev
                
                t_gordon_prev = res_gordon.track_data[sim_idx-1]['time_sec'] if sim_idx > 0 else 0
                t_gordon_delta = d_gordon['time_sec'] - t_gordon_prev
                
                sub_asym_t += t_asym_delta
                sub_gordon_t += t_gordon_delta
                
                sub_asym_p.append(d_asym['power'] * t_asym_delta)
                sub_gordon_p.append(d_gordon['power'] * t_gordon_delta)
                
                sim_idx += 1
            
            # Avoid div by zero
            avg_asym_w = sum(sub_asym_p) / sub_asym_t if sub_asym_t > 0 else 0
            avg_gordon_w = sum(sub_gordon_p) / sub_gordon_t if sub_gordon_t > 0 else 0
            
            avg_asym_v = (p_len / 1000) / (sub_asym_t / 3600) if sub_asym_t > 0 else 0
            avg_gordon_v = (p_len / 1000) / (sub_gordon_t / 3600) if sub_gordon_t > 0 else 0
            
            writer.writerow([
                cluster['id'],
                f"{p_start/1000:.1f}",
                f"{p_end/1000:.1f}",
                f"{p_len/1000:.2f}",
                f"{cluster['avg_grade']:.1f}",
                cluster['type'],
                f"{avg_asym_w:.0f}",
                f"{avg_asym_v:.1f}",
                f"{int(sub_asym_t)}",
                f"{avg_gordon_w:.0f}",
                f"{avg_gordon_v:.1f}",
                f"{int(sub_gordon_t)}",
                f"{int(sub_gordon_t - sub_asym_t)}"
            ])

    print(f"Done. Processed {len(plan_clusters)} clusters from JSON.")

if __name__ == "__main__":
    run_export_comparison()