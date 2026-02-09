import sys
import os
import json
import folium
import polyline

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.gpx_loader import GpxLoader
from src.services.valhalla import ValhallaClient

def visualize_comparison(gpx_path):
    # 1. Load Original GPX
    print(f"Loading GPX: {gpx_path}")
    loader = GpxLoader(gpx_path)
    loader.load()
    original_coords = [[p.lat, p.lon] for p in loader.points]
    
    # 2. Get Valhalla Matched Path
    print("Requesting Valhalla Map Matching via ValhallaClient (with Chunking)...")
    v_client = ValhallaClient()
    
    # [Up-sampling] 30m
    raw_points = [{"lat": p.lat, "lon": p.lon} for p in loader.points]
    input_points = []
    if raw_points:
        input_points.append(raw_points[0])
        for i in range(1, len(raw_points)):
            prev = input_points[-1]
            curr = raw_points[i]
            d = v_client._haversine(prev['lat'], prev['lon'], curr['lat'], curr['lon'])
            if d > 30.0:
                count = int(d / 30.0)
                for k in range(1, count + 1):
                    frac = k / (count + 1)
                    input_points.append({
                        "lat": prev['lat'] + (curr['lat'] - prev['lat']) * frac,
                        "lon": prev['lon'] + (curr['lon'] - prev['lon']) * frac
                    })
            input_points.append(curr)

    # Use the robust client method
    result = v_client.get_standard_course(input_points)
    v_coords = list(zip(result['points']['lat'], result['points']['lon']))

    # 3. Create Map
    if not original_coords:
        print("Error: No coordinates found in GPX.")
        return

    m = folium.Map(location=original_coords[0], zoom_start=15)
    
    # Draw Original (Red)
    folium.PolyLine(original_coords, color="red", weight=5, opacity=0.7, label="Original GPX").add_to(m)
    # Draw Valhalla Matched (Blue)
    folium.PolyLine(v_coords, color="blue", weight=3, opacity=0.8, label="Valhalla Matched").add_to(m)
    
    # Add Markers for Start/End
    folium.Marker(original_coords[0], popup="Start (GPX)", icon=folium.Icon(color='red')).add_to(m)
    folium.Marker(original_coords[-1], popup="End (GPX)", icon=folium.Icon(color='red')).add_to(m)
    if v_coords:
        folium.Marker(v_coords[0], popup="Start (Valhalla)", icon=folium.Icon(color='blue')).add_to(m)
        folium.Marker(v_coords[-1], popup="End (Valhalla)", icon=folium.Icon(color='blue')).add_to(m)

    # 4. Save
    output_html = "data/output/comparison_map.html"
    m.save(output_html)
    print(f"\n[DONE] Comparison map saved to {output_html}")
    print(f"Original Points: {len(original_coords)}")
    print(f"Valhalla Points: {len(v_coords)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/visualize_comparison.py <gpx_file>")
    else:
        visualize_comparison(sys.argv[1])
