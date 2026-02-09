from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import math
import json
import os
import logging
import hashlib

# Import internal modules
from src.core.gpx_loader import GpxLoader, TrackPoint, Segment
from src.services.valhalla import ValhallaClient
from src.core.rider import Rider
from src.core.storage import get_storage
# Upgrade to PhysicsEngineV2
from src.engines.v2 import PhysicsEngineV2 as PhysicsEngine, PhysicsParams

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class RiderInput(BaseModel):
    weight_kg: float
    cp: float
    bike_weight: float = 8.5
    w_prime: float = 20000.0 
    pdc: Dict[str, float] = {}

class SimulationRequest(BaseModel):
    points: List[PointInput]
    segments: List[SegmentInput]
    rider: RiderInput

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"status": "Bike Course Simulator API (Engine V2) is running"}

@app.post("/api/upload_gpx")
async def upload_gpx(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # [Caching Strategy] Hash-based Deduplication
        file_hash = hashlib.sha256(content).hexdigest()
        storage_filename = f"course_{file_hash}.json"
        
        storage = get_storage()
        
        # 1. Check Cache
        if storage.exists(storage_filename):
            logger.info(f"Cache Hit! Loading {storage_filename} from storage.")
            return storage.load(storage_filename)
            
        logger.info(f"Cache Miss. Processing GPX via Valhalla...")
        gpx_str = content.decode("utf-8")
        
        temp_filename = f"temp_{file.filename}"
        with open(temp_filename, "w") as f:
            f.write(gpx_str)
            
        # 2. Load Raw GPX
        loader = GpxLoader(temp_filename)
        loader.load()
        os.remove(temp_filename)
        
        # 3. Convert to Valhalla Input Format
        shape_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points] # 'ele' is optional for Valhalla request, it fills it.
        
        # 4. Process via ValhallaClient
        v_client = ValhallaClient()
        standard_course = v_client.get_standard_course(shape_points)
        
        # 5. Save to Storage (Cache)
        storage.save(standard_course, storage_filename)
        
        return standard_course
        
    except Exception as e:
        logger.error(f"Error processing GPX: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate")
def run_simulation(req: SimulationRequest):
    if not req.points:
        raise HTTPException(status_code=400, detail="No GPX points provided")

    # 1. Setup Rider & Physics
    rider = Rider(weight=req.rider.weight_kg, cp=req.rider.cp, w_prime_max=req.rider.w_prime)
    rider.pdc = {str(k): float(v) for k, v in req.rider.pdc.items()}
    
    physics_params = PhysicsParams(bike_weight=req.rider.bike_weight)
    engine = PhysicsEngine(rider, physics_params)
    
    # [ENGINE V2 CONFIG] 
    # Use Asymmetric Mode as it proved to be the most efficient in sensitivity tests.
    # slow=0.6 (Climbing), fast=1.5 (Descending)
    engine.set_tuning(mode='asymmetric', slow=0.6, fast=1.5)

    # 2. Convert Points to Internal Format
    loader = GpxLoader("")
    loader.points = [
        TrackPoint(lat=p.lat, lon=p.lon, ele=p.ele, distance_from_start=p.dist_m)
        for p in req.points
    ]
    
    # 3. Compress points into physical segments
    physics_segments = loader.compress_segments(grade_threshold=0.005, max_length=200.0)

    # 4. Run Optimal Pacing Solver (Binary Search with Adaptive V_ref)
    logger.info(f"Starting V2 Optimal Pacing Simulation for rider {req.rider.cp}W CP")
    result_obj = engine.find_optimal_pacing(physics_segments)
    
    # 5. Prepare response data
    result = {
        "total_time_sec": result_obj.total_time_sec,
        "avg_speed_kmh": result_obj.average_speed_kmh,
        "avg_power": result_obj.average_power,
        "normalized_power": result_obj.normalized_power,
        "work_kj": result_obj.work_kj,
        "w_prime_min": result_obj.w_prime_min,
        "is_success": result_obj.is_success,
        "fail_reason": result_obj.fail_reason,
        "track_data": result_obj.track_data
    }
    
    try:
        with open("simulation_result.json", "w") as f:
            json.dump(result, f, indent=2)
        logger.info("Successfully updated simulation_result.json")
    except Exception as e:
        logger.error(f"Failed to write simulation_result.json: {e}")

    return result