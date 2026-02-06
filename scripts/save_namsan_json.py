import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.valhalla_client import ValhallaClient

def save_namsan_json():
    gpx_path = "data/gpx/Namsan1_7.gpx"
    print(f"Loading: {gpx_path}")
    loader = GpxLoader(gpx_path)
    loader.load()
    input_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    
    client = ValhallaClient()
    print("Requesting Valhalla...")
    data = client.get_standard_course(input_points)
    
    out_path = "data/output/namsan_result.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    save_namsan_json()
