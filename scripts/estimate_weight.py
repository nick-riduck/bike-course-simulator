import json
import math
import numpy as np

def estimate_weight(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    segments = data['segments']
    
    # Physics Constants
    g = 9.81
    crr = 0.006 # Rolling resistance estimate (mixed tarmac)
    drivetrain_loss = 0.05 # 5% loss
    
    # Filtering for Climbing Segments
    # Grade > 6% (sin theta dominates)
    # Speed > 3 km/h (moving)
    # Power > 100 W (pedaling)
    
    valid_points = []
    
    print(f"Analyzing {len(segments)} data points...")
    
    for s in segments:
        grade_pct = s['grade_pct']
        speed_kmh = s['speed_kmh']
        power = s['power']
        
        if grade_pct > 6.0 and speed_kmh > 3.0 and power > 100.0:
            valid_points.append(s)
            
    if not valid_points:
        print("No suitable steep climbing segments found for estimation.")
        return

    print(f"Found {len(valid_points)} valid climbing points for estimation.")
    
    estimated_masses = []
    
    for p in valid_points:
        v = p['speed_kmh'] / 3.6
        grade = p['grade_pct'] / 100.0
        power_input = p['power']
        
        theta = math.atan(grade)
        
        # P_wheel = P_input * (1 - loss)
        p_wheel = power_input * (1 - drivetrain_loss)
        
        # P_gravity = m * g * sin(theta) * v
        # P_rolling = m * g * cos(theta) * Crr * v
        # P_aero = 0.5 * rho * CdA * v^3 (Negligible at slow climbing speeds, but lets include small term)
        
        # Assume CdA = 0.35, Rho = 1.15 (elevation adjusted approx)
        cda = 0.30
        rho = 1.15
        p_aero = 0.5 * rho * cda * (v**3)
        
        # P_wheel = P_climb + P_aero
        # P_climb = P_wheel - P_aero
        p_climb = p_wheel - p_aero
        
        if p_climb <= 0: continue
        
        # P_climb = m * g * v * (sin(theta) + Crr * cos(theta))
        # m = P_climb / (g * v * (sin(theta) + Crr * cos(theta)))
        
        denom = g * v * (math.sin(theta) + crr * math.cos(theta))
        
        if denom > 0:
            m = p_climb / denom
            if 50 < m < 150: # Filter outliers
                estimated_masses.append(m)
                
    if not estimated_masses:
        print("Calculation failed (all points filtered out).")
        return
        
    avg_mass = np.mean(estimated_masses)
    median_mass = np.median(estimated_masses)
    std_dev = np.std(estimated_masses)
    
    print("-" * 40)
    print(f"Estimated Total System Weight (Rider+Bike+Kit)")
    print(f"Mean   : {avg_mass:.2f} kg")
    print(f"Median : {median_mass:.2f} kg")
    print(f"Std Dev: {std_dev:.2f} kg")
    print("-" * 40)
    
    # Assumptions
    bike_weight = 8.5 # kg
    kit_weight = 1.5 # kg (shoes, helmet, bottles)
    est_rider_weight = avg_mass - bike_weight - kit_weight
    
    print(f"Assuming Bike {bike_weight}kg + Kit {kit_weight}kg:")
    print(f"-> Estimated Rider Weight: {est_rider_weight:.2f} kg")
    print("-" * 40)

if __name__ == "__main__":
    estimate_weight("simulation_result.json")
