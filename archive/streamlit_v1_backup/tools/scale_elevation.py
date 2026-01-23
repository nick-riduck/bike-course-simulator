import sys
import os
import xml.etree.ElementTree as ET

def scale_gpx_elevation(input_path, output_path, target_gain):
    tree = ET.parse(input_path)
    root = tree.getroot()
    
    # Namespaces
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    ET.register_namespace('', ns['gpx'])
    
    trkpts = root.findall(".//gpx:trkpt", ns)
    if not trkpts:
        trkpts = root.findall(".//trkpt") # Fallback without NS

    if not trkpts:
        print("No track points found.")
        return

    # 1. Calculate Current Raw Gain
    elevations = []
    for pt in trkpts:
        ele_node = pt.find("gpx:ele", ns)
        if ele_node is None: ele_node = pt.find("ele")
        
        if ele_node is not None:
            elevations.append(float(ele_node.text))
        else:
            elevations.append(0.0)

    current_gain = 0.0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i-1]
        if diff > 0:
            current_gain += diff
            
    print(f"Current Raw Gain: {current_gain:.1f}m")
    
    if current_gain == 0:
        print("Error: Current gain is 0, cannot scale.")
        return

    # 2. Calculate Scale Factor
    # We want to scale the 'climbs' to match target.
    # Simple linear scaling relative to start elevation usually works best for preserving profile shape.
    
    start_ele = elevations[0]
    # However, if we just scale (ele - start), we scale the net elevation change.
    # If the course is up-down-up, scaling relative to start might distort the 'down' parts incorrectly if not careful.
    # But for a hill climb (mostly up), scaling relative to start is safe.
    
    # Let's try to estimate the new total gain if we scale relative to start.
    # New Gain = Sum( max(0, (start + (e_i - start)*k) - (start + (e_{i-1} - start)*k)) )
    #          = Sum( max(0, k * (e_i - e_{i-1})) )
    #          = k * Sum( max(0, e_i - e_{i-1}) )
    #          = k * Current_Gain
    
    scale_factor = target_gain / current_gain
    print(f"Scaling Factor: {scale_factor:.4f}")

    # 3. Apply Scaling
    new_elevations = []
    for ele in elevations:
        new_ele = start_ele + (ele - start_ele) * scale_factor
        new_elevations.append(new_ele)
        
    # 4. Update XML
    for i, pt in enumerate(trkpts):
        ele_node = pt.find("gpx:ele", ns)
        if ele_node is None: ele_node = pt.find("ele")
        
        if ele_node is not None:
            ele_node.text = f"{new_elevations[i]:.2f}"

    tree.write(output_path, encoding='UTF-8', xml_declaration=True)
    print(f"Saved scaled GPX to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scale_elevation.py <input_gpx> <target_gain_m>")
    else:
        scale_gpx_elevation(sys.argv[1], "Namsan1_7_120m.gpx", float(sys.argv[2]))
