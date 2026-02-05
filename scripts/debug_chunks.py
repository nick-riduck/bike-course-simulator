import sys
import os
import json
import folium
import polyline
import httpx

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gpx_loader import GpxLoader
from src.valhalla_client import ValhallaClient, VALHALLA_URL

def debug_chunks(gpx_path):
    print(f"Loading GPX: {gpx_path}")
    loader = GpxLoader(gpx_path)
    loader.load()
    
    # 1. Pre-process (Smart Gap Fill + Upsample)
    v_client = ValhallaClient()
    print("Pre-processing input points (Smart Fill + Upsample)...")
    shape_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    processed_input = v_client._fill_gaps_with_routing(shape_points, gap_threshold=500.0)
    processed_input = v_client._upsample_points(processed_input, max_interval=30.0)
    
    total_points = len(processed_input)
    CHUNK_SIZE = 2000 # Same as ValhallaClient
    OVERLAP = 200     # Same as ValhallaClient
    
    print(f"Total Points: {total_points}. Chunk Size: {CHUNK_SIZE}, Overlap: {OVERLAP}")
    
    chunks_data = [] # List of list of coords
    
    current_idx = 0
    chunk_count = 0
    
    while current_idx < total_points:
        end_idx = min(current_idx + CHUNK_SIZE, total_points)
        req_start = max(0, current_idx - OVERLAP)
        req_end = end_idx
        
        chunk_input = processed_input[req_start : req_end]
        print(f"  > Processing Chunk {chunk_count}: Input idx {req_start} ~ {req_end} ({len(chunk_input)} pts)")
        
        # Call Valhalla directly (raw trace)
        try:
            result = v_client._request_raw_data_no_ele(chunk_input)
            shape = result["shape_points"] # List of [lat, lon]
            chunks_data.append(shape)
        except Exception as e:
            print(f"    [Error] Chunk {chunk_count} failed: {e}")
            chunks_data.append([]) # Empty placeholder
            
        current_idx += CHUNK_SIZE - OVERLAP
        chunk_count += 1
        
        if req_end == total_points: break

    # 2. Draw Map
    if not processed_input:
        print("No input data.")
        return

    start_coords = [processed_input[0]['lat'], processed_input[0]['lon']]
    m = folium.Map(location=start_coords, zoom_start=13)
    
    # Draw Original Input (Grey line, thin)
    orig_coords = [[p['lat'], p['lon']] for p in processed_input]
    folium.PolyLine(orig_coords, color="gray", weight=2, opacity=0.5, label="Processed Input").add_to(m)
    
    # Draw Chunks
    colors = ['blue', 'orange']
    
    for i, shape in enumerate(chunks_data):
        if not shape: continue
        color = colors[i % 2]
        folium.PolyLine(
            shape, 
            color=color, 
            weight=5, 
            opacity=0.8, 
            popup=f"Chunk {i} ({len(shape)} pts)"
        ).add_to(m)
        
        # Mark Start/End of each chunk to see overlap
        folium.CircleMarker(shape[0], radius=3, color=color, fill=True).add_to(m)
        folium.CircleMarker(shape[-1], radius=3, color=color, fill=True).add_to(m)

    output_html = "data/output/debug_chunks.html"
    m.save(output_html)
    print(f"\n[DONE] Chunk debug map saved to {output_html}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_chunks.py <gpx_file>")
    else:
        debug_chunks(sys.argv[1])
