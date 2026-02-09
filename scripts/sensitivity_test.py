import sys
import os
import json
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.gpx_loader import GpxLoader
from src.core.rider import Rider
# Import V2 Engine directly
from src.engines.v2 import PhysicsEngineV2, PhysicsParams, SimulationResult
from src.engines.base_theory import TheoryEngine

# Custom Engine Class for Testing
class SensitivityEngine(PhysicsEngineV2):
    def __init__(self, rider, params):
        super().__init__(rider, params)
        # Default Settings
        self.alpha_climb = 0.0
        self.alpha_descent = 10.0
        self.beta_aero = 1.0

def load_real_rider(rider_key='rider_a'):
    """Load Rider Data from JSON"""
    try:
        with open('rider_data.json', 'r') as f:
            data = json.load(f)
            r_data = data[rider_key]
            
            # Convert keys to int for PDC
            pdc = {int(k): float(v) for k, v in r_data['pdc'].items()}
            
            rider = Rider(
                weight=r_data['weight_kg'],
                cp=r_data['cp'],
                w_prime_max=r_data['w_prime']
            )
            rider.pdc = pdc
            return rider
    except Exception as e:
        print(f"Error loading rider data: {e}")
        return None

def print_results(results):
    header = f"{ 'Mode':<12} | { 'Time':<10} | { 'Base':<4} | { 'NP':<4} | { 'Limit':<5} | { 'MinWp':<6} | { 'MaxP':<5} | { 'P99':<4} | { 'P50':<4} | { 'Status':<4}"
    print("-" * 105)
    print(header)
    print("-" * 105)
    for r in results:
        status = "OK" if r['Status'] else "FAIL"
        print(f"{r['Mode']:<12} | {r['Time']:<10} | {r['Base']:<4.0f} | {r['NP']:<4.0f} | {r['Limit']:<5.0f} | {r['MinWp']:<6.0f} | {r['Max P']:<5.0f} | {r['P99']:<4.0f} | {r['P50']:<4.0f} | {status:<4}")

def format_time(seconds):
    if isinstance(seconds, str): return seconds
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m {s}s"

def run_test(gpx_path, course_name, rider_key='rider_a'):
    print(f"\n=========================================================================================================")
    print(f" >>> Course: {course_name}")
    print(f" >>> Rider: {rider_key} (Real Data)")
    print(f"=========================================================================================================")
    
    loader = GpxLoader(gpx_path)
    loader.load()
    segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)
    
    rider = load_real_rider(rider_key)
    if not rider: return

    params = PhysicsParams(bike_weight=8.5, cda=0.30, crr=0.0045, drivetrain_loss=0.05, air_density=1.225, drafting_factor=0.0)
    
    results = []
    
    # Test Cases: Verify Physics V2 Tuning
    cases = [
        {"mode": "linear", "beta": 1.0, "args": {}, "engine_cls": SensitivityEngine},
        {"mode": "asymmetric", "beta": 1.0, "args": {"slow": 0.6, "fast": 1.5}, "engine_cls": SensitivityEngine}, # Recommended
        {"mode": "logarithmic", "beta": 0.6, "args": {}, "engine_cls": SensitivityEngine},
        {"mode": "theory_old", "beta": 1.0, "args": {}, "engine_cls": SensitivityEngine}, # Pure Inverse (V2)
        {"mode": "REAL_THEORY", "beta": 1.0, "args": {}, "engine_cls": TheoryEngine}, # New Engine
    ]
    
    for c in cases:
        # Instantiate Engine
        engine_class = c["engine_cls"]
        engine = engine_class(rider, params)
        
        engine.beta_aero = c["beta"]
        engine.set_tuning(c["mode"].replace("_old", "").replace("REAL_", ""), **c["args"]) # Strip prefix for internal mode check
        
        # Use Solver
        res_obj = engine.find_optimal_pacing(segments)
        
        # Get Limit for this duration
        limit = engine._get_dynamic_pdc_limit(res_obj.total_time_sec)
        
        # Power Stats
        powers = [p['power'] for p in res_obj.track_data] if res_obj.track_data else []
        powers.sort()
        n = len(powers)
        
        results.append({
            "Mode": c["mode"],
            "Time": format_time(res_obj.total_time_sec) if res_obj.is_success else "BONK",
            "Base": res_obj.base_power,
            "NP": res_obj.normalized_power,
            "Limit": limit,
            "MinWp": res_obj.w_prime_min,
            "Max P": powers[-1] if powers else 0,
            "P99": powers[int(n*0.99)] if n > 0 else 0,
            "P50": powers[int(n*0.50)] if n > 0 else 0,
            "Status": res_obj.is_success
        })
            
    print_results(results)

if __name__ == "__main__":
    # 1. Bukak (Short Uphill)
    run_test("북악공인구간.gpx", "Bukak Climb (2.5km)")
    
    # 2. Seorak (Long Granfondo)
    run_test("20seorak.gpx", "Seorak Granfondo (200km)")