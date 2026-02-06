import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.valhalla_client import ValhallaClient

def test_large_sg():
    gpx_path = "data/gpx/sg.gpx"
    if not os.path.exists(gpx_path):
        print(f"File not found: {gpx_path}")
        return

    print(f"Loading large course: {gpx_path}")
    loader = GpxLoader(gpx_path)
    loader.load()
    input_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    
    print(f"Total Input Points: {len(input_points)}")
    
    client = ValhallaClient()
    # CHUNK_SIZE will be 4000 by default
    print("Starting Chunked Valhalla Request...")
    try:
        data = client.get_standard_course(input_points)
        
        out_path = "data/output/sg_result.json"
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
            
        print(f"\n[SUCCESS] Large course processed.")
        print(f"Distance: {data['stats']['distance']/1000:.1f} km")
        print(f"Ascent: {data['stats']['ascent']:.0f} m")
        print(f"Segments: {data['stats']['segments_count']}")
        print(f"Saved to {out_path}")
        
    except Exception as e:
        print(f"\n[FAILED] {str(e)}")

if __name__ == "__main__":
    test_large_sg()
