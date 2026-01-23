import json
import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
import numpy as np

def parse_gpx(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Namespaces
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    
    points = []
    
    for trkpt in root.findall('.//gpx:trkpt', ns):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))
        ele = float(trkpt.find('gpx:ele', ns).text)
        time_str = trkpt.find('gpx:time', ns).text
        
        # Parse Power (Strava format usually inside extensions without namespace prefix issues sometimes, but let's be careful)
        power = 0
        extensions = trkpt.find('gpx:extensions', ns)
        if extensions is not None:
            # Try finding 'power' directly (Strava)
            p_tag = extensions.find('power')
            if p_tag is not None:
                power = float(p_tag.text)
            else:
                # Try Garmin extension
                for child in extensions:
                    if 'power' in child.tag:
                        power = float(child.text)
                        
        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
        points.append({
            "lat": lat, "lon": lon, "ele": ele, "time": dt, "power": power
        })
        
    return points

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def convert_to_simulation_format(gpx_path, output_path="simulation_result.json"):
    print(f"Parsing {gpx_path}...")
    points = parse_gpx(gpx_path)
    
    segments = []
    cum_dist = 0.0
    cum_time = 0.0
    start_time = points[0]['time']
    
    # Estimate W' (Simple CP model)
    # Let's calculate NP first to guess a CP
    raw_powers = [p['power'] for p in points]
    
    # Simple NP calc (30s rolling avg)
    rolling_powers = np.convolve(raw_powers, np.ones(30)/30, mode='valid')
    np_val = np.mean(rolling_powers ** 4) ** 0.25
    avg_pwr = np.mean(raw_powers)
    
    print(f"Ride Stats: Avg Power {avg_pwr:.0f}W, NP {np_val:.0f}W")
    
    # Assume CP is around 95% of NP for a hard ride, or just use NP if it's a race
    cp_est = np_val * 0.95 
    w_prime_cap = 20000.0 # Standard 20kJ
    w_prime_bal = w_prime_cap
    
    min_w_prime = w_prime_cap
    total_work = 0.0
    
    print(f"Using Estimated CP: {cp_est:.0f}W for W' calculation")

    for i in range(1, len(points)):
        p1 = points[i-1]
        p2 = points[i]
        
        dist = haversine(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
        time_diff = (p2['time'] - p1['time']).total_seconds()
        
        if time_diff <= 0: continue
        
        ele_diff = p2['ele'] - p1['ele']
        
        # Speed km/h
        speed_ms = dist / time_diff
        speed_kmh = speed_ms * 3.6
        
        # Grade
        grade = 0.0
        if dist > 0:
            grade = ele_diff / dist
            
        # Power
        power = p2['power'] # Use current point power
        
        # W' Balance
        if power > cp_est:
            w_prime_bal -= (power - cp_est) * time_diff
        else:
            # Recovery (Tau model simplified or linear)
            # Linear recovery for simplicity in visualization
            w_prime_bal += (cp_est - power) * time_diff
            if w_prime_bal > w_prime_cap: w_prime_bal = w_prime_cap
            
        min_w_prime = min(min_w_prime, w_prime_bal)
        total_work += power * time_diff
        
        cum_dist += dist
        cum_time += time_diff
        
        segments.append({
            "dist_km": cum_dist / 1000.0,
            "lat": p2['lat'],
            "lon": p2['lon'],
            "ele": p2['ele'],
            "grade_pct": grade * 100,
            "speed_kmh": speed_kmh,
            "power": power,
            "w_prime": w_prime_bal,
            "time_sec": cum_time
        })
        
    # Summary
    summary = {
        "time_str": f"{int(cum_time//3600)}h {int((cum_time%3600)//60)}m",
        "avg_speed": (cum_dist/cum_time)*3.6 if cum_time > 0 else 0,
        "norm_power": np_val,
        "work_kj": total_work / 1000.0
    }
    
    output_data = {
        "summary": summary,
        "segments": segments
    }
    
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
        
    print(f"Converted data saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/convert_real_ride.py <gpx_file>")
        sys.exit(1)
        
    convert_to_simulation_format(sys.argv[1])
