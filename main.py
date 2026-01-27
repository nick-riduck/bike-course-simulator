from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math
import json
import os

# Import internal modules
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
    dist_m: float 

class SegmentInput(BaseModel):
    id: int
    start_dist: float
    end_dist: float
    target_power: float

class RiderInput(BaseModel):
    weight_kg: float
    cp: float
    bike_weight: float = 8.5
    w_prime: float = 20000.0 

class SimulationRequest(BaseModel):
    points: List[PointInput]
    segments: List[SegmentInput]
    rider: RiderInput

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"status": "Bike Course Simulator API is running"}

@app.post("/upload_gpx")
async def upload_gpx(file: UploadFile = File(...)):
    """
    Parse GPX file and perform initial segmentation (Atomic Segments).
    Source of Truth for segmentation logic.
    """
    try:
        content = await file.read()
        gpx_str = content.decode("utf-8")
        
        temp_filename = f"temp_{file.filename}"
        with open(temp_filename, "w") as f:
            f.write(gpx_str)
            
        loader = GpxLoader(temp_filename)
        loader.load()
        
        # Generate Atomic Segments (Physics Resolution)
        # grade 0.5%, 200m max length
        atomic_segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)
        
        os.remove(temp_filename)
        
        return {
            "points": [
                {"lat": p.lat, "lon": p.lon, "ele": p.ele, "dist_m": p.distance_from_start}
                for p in loader.points
            ],
            "atomic_segments": [
                {
                    "start_dist": s.start_dist,
                    "end_dist": s.end_dist,
                    "avg_grade": s.grade * 100, 
                    "start_ele": s.start_ele,
                    "end_ele": s.end_ele,
                    "start_lat": s.start_lat,
                    "start_lon": s.start_lon,
                    "end_lat": s.lat,
                    "end_lon": s.lon,
                    "shifted_start_lat": s.shifted_start_lat,
                    "shifted_start_lon": s.shifted_start_lon,
                    "shifted_end_lat": s.shifted_end_lat,
                    "shifted_end_lon": s.shifted_end_lon
                }
                for s in atomic_segments
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulate")
def run_simulation(req: SimulationRequest):
    if not req.points:
        raise HTTPException(status_code=400, detail="No GPX points provided")

    # 1. Setup Rider & Physics
    rider = Rider(weight=req.rider.weight_kg, cp=req.rider.cp, w_prime_max=req.rider.w_prime)
    physics_params = PhysicsParams(bike_weight=req.rider.bike_weight)
    engine = PhysicsEngine(rider, physics_params)

    # 2. Convert Points to Internal Format
    loader = GpxLoader("")
    loader.points = [
        TrackPoint(lat=p.lat, lon=p.lon, ele=p.ele, distance_from_start=p.dist_m)
        for p in req.points
    ]
    
    # 3. Use User Segments directly?
    physics_segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)

    for p_seg in physics_segments:
        mid_dist = (p_seg.start_dist + p_seg.end_dist) / 2
        target_power = req.rider.cp * 0.7 # Default fallback
        for u_seg in req.segments:
            if u_seg.start_dist <= mid_dist < u_seg.end_dist:
                target_power = u_seg.target_power
                break
        p_seg.custom_power = target_power 

    # 4. Run Simulation
    result = simulate_with_custom_power(engine, physics_segments)
    
    try:
        with open("simulation_result.json", "w") as f:
            json.dump(result, f, indent=2)
        print("Successfully updated simulation_result.json")
    except Exception as e:
        print(f"Failed to write simulation_result.json: {e}")

    return result

def simulate_with_custom_power(engine: PhysicsEngine, segments: List[Segment]):
    engine.rider.reset_state()
    total_time = 0.0
    total_work = 0.0
    weighted_power_sum = 0.0
    v_current = 20.0 / 3.6
    min_w_prime = engine.rider.w_prime_max
    
    output_segments = [] 
    f_max_initial = engine.rider.weight * 9.81 * 1.5
    prev_heading = segments[0].heading if segments else 0

    for seg in segments:
        heading_change = abs(seg.heading - prev_heading)
        if heading_change > 180: heading_change = 360 - heading_change
        if seg.length > 0 and heading_change > 1.0:
            theta_rad = math.radians(heading_change)
            curvature = theta_rad / seg.length
            if curvature > 0.0001:
                radius = 1.0 / curvature
                mu, g = 0.8, 9.81
                v_corner_limit = math.sqrt(mu * g * radius)
                v_current = min(v_current, v_corner_limit)
        prev_heading = seg.heading
        
        p_target = getattr(seg, 'custom_power', 100.0)
        decay = (3600.0 / max(3600.0, total_time)) ** 0.07
        f_limit = f_max_initial * decay

        v_next, time_sec = engine._solve_segment_physics(seg, p_target, v_current, 0.0, f_limit)
        engine.rider.update_w_prime(p_target, time_sec)
        
        total_time += time_sec
        total_work += p_target * time_sec
        weighted_power_sum += (p_target ** 4) * time_sec
        min_w_prime = min(min_w_prime, engine.rider.w_prime_bal)

        output_segments.append({
            "dist_km": seg.end_dist / 1000.0,
            "ele": seg.end_ele,
            "grade_pct": seg.grade * 100,
            "speed_kmh": (v_next + v_current)/2 * 3.6,
            "power": p_target,
            "time_sec": total_time,
            "w_prime_bal": engine.rider.w_prime_bal,
            "lat": seg.lat,
            "lon": seg.lon
        })
        v_current = v_next

    avg_spd = (segments[-1].end_dist / 1000.0 * 3600) / total_time if total_time > 0 else 0
    avg_p = total_work / total_time if total_time > 0 else 0
    np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0

    return {
        "total_time_sec": total_time,
        "avg_speed_kmh": avg_spd,
        "avg_power": avg_p,
        "normalized_power": np,
        "work_kj": total_work / 1000.0,
        "w_prime_min": min_w_prime,
        "is_success": True,
        "track_data": output_segments
    }
