from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math

# Import internal modules (Ensure PYTHONPATH covers root directory)
from src.gpx_loader import GpxLoader, TrackPoint, Segment
from src.rider import Rider
from src.physics_engine import PhysicsEngine, PhysicsParams

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Input ---
class PointInput(BaseModel):
    lat: float
    lon: float
    ele: float
    dist_m: float # Cumulative distance

class SegmentInput(BaseModel):
    id: int
    start_dist: float
    end_dist: float
    target_power: float

class RiderInput(BaseModel):
    weight_kg: float
    ftp: float
    bike_weight: float = 8.5
    w_prime: float = 20000.0 # Default 20kJ

class SimulationRequest(BaseModel):
    points: List[PointInput]
    segments: List[SegmentInput]
    rider: RiderInput

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"status": "Bike Course Simulator API is running"}

@app.post("/simulate")
def run_simulation(req: SimulationRequest):
    if not req.points:
        raise HTTPException(status_code=400, detail="No GPX points provided")

    # 1. Setup Rider & Physics
    rider = Rider(weight=req.rider.weight_kg, ftp=req.rider.ftp, w_prime=req.rider.w_prime)
    physics_params = PhysicsParams(bike_weight=req.rider.bike_weight)
    engine = PhysicsEngine(rider, physics_params)

    # 2. Convert Points to Internal Format & Compress
    # We use GpxLoader's logic but manually inject points
    loader = GpxLoader("")
    loader.points = [
        TrackPoint(lat=p.lat, lon=p.lon, ele=p.ele, distance_from_start=p.dist_m)
        for p in req.points
    ]
    
    # Use internal segmentation for physics (High resolution)
    # grade_threshold=0.005 (0.5%), min_len=10m, max_len=500m
    physics_segments = loader.compress_segments(grade_threshold=0.005, max_length=500.0)

    # 3. Map User Target Power to Physics Segments
    # Each physics segment inherits power from the user segment it falls into
    mapped_segments = []
    
    for p_seg in physics_segments:
        # Find which user segment covers this physics segment's START
        # (Simple point query is usually enough)
        mid_dist = (p_seg.start_dist + p_seg.end_dist) / 2
        
        target_power = req.rider.ftp * 0.5 # Default fallback (50% FTP)
        
        for u_seg in req.segments:
            if u_seg.start_dist <= mid_dist < u_seg.end_dist:
                target_power = u_seg.target_power
                break
        
        # We need a way to pass this 'target_power' to the engine.
        # PhysicsEngine.simulate_course currently calculates power internally using 'p_base'.
        # We need to OVERRIDE this.
        # Let's attach it to the segment object dynamically or create a parallel list.
        p_seg.custom_power = target_power 
        mapped_segments.append(p_seg)

    # 4. Run Simulation with Custom Power Logic
    # We need to modify or extend simulate_course to use `custom_power` if present
    result = simulate_with_custom_power(engine, mapped_segments)

    return {
        "total_time_sec": result.total_time_sec,
        "avg_speed_kmh": result.average_speed_kmh,
        "avg_power": result.average_power,
        "work_kj": result.work_kj,
        "is_success": result.is_success
    }

def simulate_with_custom_power(engine: PhysicsEngine, segments: List[Segment]):
    """
    Custom wrapper around engine logic to respect segment-specific power targets.
    Instead of finding optimal pacing, it just executes the plan.
    """
    engine.rider.reset_state()
    total_time = 0.0
    total_work = 0.0
    weighted_power_sum = 0.0
    v_current = 20.0 / 3.6
    min_w_prime = engine.rider.w_prime_max
    
    # Initial Force Limit
    f_max_initial = engine.rider.weight * 9.81 * 1.5

    for seg in segments:
        # Use the power assigned from frontend
        p_target = getattr(seg, 'custom_power', 100.0)
        
        # Basic Physics (Simplified from engine.simulate_course)
        # We reuse solve_segment_physics but pass our fixed p_target
        
        # Cornering logic (Optional, reuse if possible or skip for speed)
        # ... (skipping cornering for MVP to ensure speed) ...
        
        # Wind (Zero for now)
        v_headwind = 0.0
        
        # Torque Decay
        decay = 1.0
        if total_time > 3600: decay = (3600.0 / total_time) ** 0.07
        f_limit = f_max_initial * decay

        v_next, time_sec = engine._solve_segment_physics(seg, p_target, v_current, v_headwind, f_limit)
        
        engine.rider.update_w_prime(p_target, time_sec)
        
        total_time += time_sec
        total_work += p_target * time_sec
        weighted_power_sum += (p_target ** 4) * time_sec
        min_w_prime = min(min_w_prime, engine.rider.w_prime_bal)
        v_current = v_next

    dist_km = sum(s.length for s in segments) / 1000.0
    avg_spd = (dist_km * 3600) / total_time if total_time > 0 else 0
    avg_p = total_work / total_time if total_time > 0 else 0
    np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0

    from src.physics_engine import SimulationResult
    return SimulationResult(total_time, 0, avg_spd, avg_p, np, total_work/1000, min_w_prime, True)
