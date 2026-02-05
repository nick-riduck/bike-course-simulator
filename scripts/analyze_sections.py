import json

def analyze_segments():
    try:
        with open("simulation_result.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: 'simulation_result.json' not found. Please run simulate.py first.")
        return

    segments = data["segments"]
    if not segments:
        print("No segment data found.")
        return

    # Extract data arrays (using standard lists instead of numpy)
    dists = [s["dist_km"] for s in segments]
    eles = [s["ele"] for s in segments]
    speeds = [s["speed_kmh"] for s in segments]
    powers = [s["power"] for s in segments]
    grades = [s["grade_pct"] for s in segments]
    
    def get_avg(lst):
        return sum(lst) / len(lst) if lst else 0

    analyzed_sections = []
    
    start_idx = 0
    current_type = "FLAT" # FLAT, UP, DOWN
    
    def get_type(grade):
        if grade > 2.0: return "UP"
        elif grade < -2.0: return "DOWN"
        else: return "FLAT"

    for i in range(1, len(segments)):
        window_end = min(len(segments), i + 20)
        window_grades = grades[i:window_end]
        avg_window_grade = get_avg(window_grades)
        
        next_type = get_type(avg_window_grade)
        section_dist = dists[i] - dists[start_idx]
        
        min_len = 1.0 # km
        
        if next_type != current_type and section_dist > min_len:
            end_idx = i
            
            s_dist = dists[end_idx] - dists[start_idx]
            s_gain = eles[end_idx] - eles[start_idx]
            s_avg_grad = get_avg(grades[start_idx:end_idx])
            s_avg_spd = get_avg(speeds[start_idx:end_idx])
            s_avg_pwr = get_avg(powers[start_idx:end_idx])
            
            s_time_h = s_dist / s_avg_spd if s_avg_spd > 0 else 0
            
            analyzed_sections.append({
                "type": current_type,
                "start_km": dists[start_idx],
                "end_km": dists[end_idx],
                "dist_km": s_dist,
                "gain_m": s_gain,
                "avg_grade": s_avg_grad,
                "avg_spd": s_avg_spd,
                "avg_pwr": s_avg_pwr,
                "time_min": s_time_h * 60
            })
            
            start_idx = i
            current_type = next_type

    end_idx = len(segments) - 1
    s_dist = dists[end_idx] - dists[start_idx]
    if s_dist > 0:
        avg_spd = get_avg(speeds[start_idx:end_idx])
        s_time_h = s_dist / avg_spd if avg_spd > 0 else 0
        analyzed_sections.append({
            "type": current_type,
            "start_km": dists[start_idx],
            "end_km": dists[end_idx],
            "dist_km": s_dist,
            "gain_m": eles[end_idx] - eles[start_idx],
            "avg_grade": get_avg(grades[start_idx:end_idx]),
            "avg_spd": avg_spd,
            "avg_pwr": get_avg(powers[start_idx:end_idx]),
            "time_min": s_time_h * 60
        })

    print(f"{'TYPE':<6} | {'RANGE (km)':<14} | {'DIST':<6} | {'GAIN':<6} | {'GRADE':<6} | {'PWR':<5} | {'SPD':<5} | {'TIME'}")
    print("-" * 85)
    
    total_time_min = 0
    for s in analyzed_sections:
        if s['dist_km'] < 0.5: continue 
        print(f"{s['type']:<6} | {s['start_km']:5.1f}-{s['end_km']:5.1f} km | {s['dist_km']:4.1f}km | {s['gain_m']:+5.0f}m | {s['avg_grade']:5.1f}% | {s['avg_pwr']:3.0f}W | {s['avg_spd']:4.1f} | {int(s['time_min'])}m {int((s['time_min']%1)*60)}s")
        total_time_min += s['time_min']

    print("-" * 85)
    h = int(total_time_min // 60)
    m = int(total_time_min % 60)
    print(f"Total Analysis Time: {h}h {m}m")

if __name__ == "__main__":
    analyze_segments()
