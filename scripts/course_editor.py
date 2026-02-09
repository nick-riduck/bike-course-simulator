import streamlit as st
import json
import pandas as pd
import numpy as np
import pydeck as pdk
import plotly.graph_objects as go
import os
import copy
import glob
import subprocess
import sys

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from src.core.gpx_loader import GpxLoader
except ImportError:
    st.error("Could not import src.gpx_loader. Please run this tool from the project root or ensure python path is correct.")
    st.stop()

# Page Config
st.set_page_config(layout="wide", page_title="Bike Course Segment Editor")

# --- Constants ---
JSON_PATH = "simulation_result.json"
DEFINITION_PATH = "course_definition.json"
RIDER_DATA_PATH = "rider_data.json"

# --- Helper Functions ---
def load_course_preview(file_path):
    loader = GpxLoader(file_path)
    if file_path.lower().endswith(".json"):
        with open(file_path, 'r') as f:
            data = json.load(f)
            seg_list = data.get('segments', data) if isinstance(data, dict) else data
            loader.load_from_json_data(seg_list)
            segments = loader.segments
    else:
        loader.load()
        loader.smooth_elevation()
        segments = loader.compress_segments()
    
    preview_data = []
    cum_dist = 0.0
    total_gain = sum(max(0, s.end_ele - s.start_ele) for s in segments)
    
    for s in segments:
        cum_dist += s.length
        preview_data.append({
            "dist_km": cum_dist / 1000.0,
            "ele": s.end_ele,
            "start_ele": s.start_ele,
            "grade_pct": s.grade * 100,
            "lat": s.lat,
            "lon": s.lon,
            "start_lat": getattr(s, 'start_lat', s.lat),
            "start_lon": getattr(s, 'start_lon', s.lon),
            "heading": s.heading,
            "speed_kmh": None,
            "power": None,
            "w_prime": None,
            "time_sec": None 
        })
    
    summary = {"dist_km": cum_dist / 1000.0, "gain_m": total_gain}
    return preview_data, summary

def calculate_stats_for_section(sim_df, start_km, end_km):
    mask = (sim_df['dist_km'] >= start_km) & (sim_df['dist_km'] <= end_km)
    sub_df = sim_df[mask]
    if sub_df.empty:
        return {"dist_len": 0, "gain_m": 0, "avg_pwr": 0, "avg_grad": 0, "time_sec": 0}
    dist_len = end_km - start_km
    ele_gain = sub_df.iloc[-1]['ele'] - sub_df.iloc[0]['ele']
    time_diff = 0
    if 'time_sec' in sub_df.columns:
        t_start = sub_df.iloc[0]['time_sec']
        t_end = sub_df.iloc[-1]['time_sec']
        if pd.notna(t_start) and pd.notna(t_end):
            time_diff = t_end - t_start
    avg_pwr = sub_df['power'].mean() if 'power' in sub_df and not sub_df['power'].isnull().all() else None
    avg_grad = sub_df['grade_pct'].mean() if 'grade_pct' in sub_df else 0
    
    return {
        "dist_len": dist_len, "gain_m": ele_gain,
        "avg_pwr": avg_pwr,
        "avg_grad": avg_grad, 
        "time_sec": time_diff if time_diff > 0 else None
    }

def load_or_create_sections(sim_data):
    sim_df = pd.DataFrame(sim_data)
    definitions = calculate_auto_definitions(sim_df)
    sections = []
    for definition in definitions:
        stats = calculate_stats_for_section(sim_df, definition['start_km'], definition['end_km'])
        section = definition.copy()
        section.update(stats)
        sections.append(section)
    return sections

def calculate_auto_definitions(df):
    df['grade_smooth'] = df['grade_pct'].rolling(window=10, center=True).mean().fillna(0)
    definitions = []
    start_idx = 0
    def get_type(g):
        if g > 2.0: return "UP"
        elif g < -2.0: return "DOWN"
        else: return "FLAT"
    current_type = get_type(df.iloc[0]['grade_smooth'])
    for i in range(1, len(df)):
        curr_dist, start_dist = df.iloc[i]['dist_km'], df.iloc[start_idx]['dist_km']
        avg_grade = df.iloc[i:i+20]['grade_smooth'].mean() if i + 20 < len(df) else df.iloc[i]['grade_smooth']
        next_type = get_type(avg_grade)
        if next_type != current_type and (curr_dist - start_dist) > 0.5:
            definitions.append({"id": len(definitions), "type": current_type, "start_km": start_dist, "end_km": curr_dist, "name": f"Segment {len(definitions)}"})
            current_type, start_idx = next_type, i
    definitions.append({"id": len(definitions), "type": current_type, "start_km": df.iloc[start_idx]['dist_km'], "end_km": df.iloc[-1]['dist_km'], "name": f"Segment {len(definitions)}"})
    return definitions

def merge_segments_logic(sections, min_id, max_id):
    new_segs = [s for s in sections if s['id'] < min_id]
    block = [s for s in sections if min_id <= s['id'] <= max_id]
    s_start, s_end = block[0], block[-1]
    total_dist = s_end['end_km'] - s_start['start_km']
    total_time = sum(s['time_sec'] for s in block)
    weighted_pwr = sum(s['avg_pwr'] * s['time_sec'] for s in block) / total_time if total_time > 0 else 0
    weighted_grad = sum(s['avg_grad'] * (s['end_km'] - s['start_km']) for s in block) / total_dist if total_dist > 0 else 0
    new_type = "FLAT"
    if weighted_grad > 2.0: new_type = "UP"
    elif weighted_grad < -2.0: new_type = "DOWN"
    merged_sec = {
        "id": len(new_segs), "type": new_type, "start_km": s_start['start_km'], "end_km": s_end['end_km'],
        "name": s_start.get('name', f"Segment {len(new_segs)}"), "dist_len": total_dist,
        "gain_m": sum(s['gain_m'] for s in block), "avg_pwr": weighted_pwr, "avg_grad": weighted_grad, "time_sec": total_time
    }
    new_segs.append(merged_sec)
    for s in sections:
        if s['id'] > max_id:
            s_copy = s.copy()
            s_copy['id'] = len(new_segs)
            new_segs.append(s_copy)
    return new_segs

def save_definitions(sections):
    definitions = []
    for s in sections:
        definitions.append({
            "id": s['id'],
            "type": s['type'],
            "start_km": s['start_km'],
            "end_km": s['end_km'],
            "name": s.get('name', f"Segment {s['id']}")
        })
    with open(DEFINITION_PATH, 'w') as f:
        json.dump(definitions, f, indent=2)

def save_state_to_history():
    if 'history' not in st.session_state:
        st.session_state['history'] = []
    st.session_state['history'].append(copy.deepcopy(st.session_state['sections']))
    st.session_state['redo_stack'] = []

# --- Main App ---
st.title("🚵‍♂️ 3D Bike Course Segment Editor")

# Initialize Session State
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'redo_stack' not in st.session_state:
    st.session_state['redo_stack'] = []
if 'merge_confirm' not in st.session_state:
    st.session_state['merge_confirm'] = None
if 'selected_ids' not in st.session_state:
    st.session_state['selected_ids'] = []

# --- Sidebar ---
st.sidebar.title("🚴‍♂️ Simulator Control")

# 1. Course Selection
gpx_files = glob.glob("*.gpx")
json_files = glob.glob("*.json")
system_files = {JSON_PATH, DEFINITION_PATH, RIDER_DATA_PATH, "package.json", "tsconfig.json"}
course_files = sorted(gpx_files + [f for f in json_files if f not in system_files])

if not course_files:
    st.error("No course files found.")
    st.stop()

selected_course = st.sidebar.selectbox("Select Course", course_files, index=0)

# Load Data Immediately on Selection Change
if 'last_loaded_course' not in st.session_state or st.session_state['last_loaded_course'] != selected_course:
    with st.spinner(f"Loading {selected_course}..."):
        sim_segments, summary = load_course_preview(selected_course)
        st.session_state['sim_segments'] = sim_segments
        st.session_state['sim_summary'] = summary
        st.session_state['sections'] = load_or_create_sections(sim_segments)
        st.session_state['last_loaded_course'] = selected_course
        # Clear history on new course load
        st.session_state['history'] = [] 
        st.session_state['redo_stack'] = []
        st.session_state['selected_ids'] = []
        st.rerun() # Force rerun to refresh the map immediately

# Access data from session state
sim_segments = st.session_state.get('sim_segments', [])
summary = st.session_state.get('sim_summary', {})

# 2. Rider Selection
riders = {}
if os.path.exists(RIDER_DATA_PATH):
    with open(RIDER_DATA_PATH, 'r') as f:
        riders = json.load(f)

if riders:
    rider_options = list(riders.keys())
    def format_rider(r_id):
        r = riders[r_id]
        return f"{r.get('name', r_id)}"
    selected_rider_id = st.sidebar.selectbox("Select Rider", rider_options, format_func=format_rider)
    selected_rider = riders[selected_rider_id]
    
    col_r1, col_r2 = st.sidebar.columns(2)
    col_r1.metric("FTP (CP)", f"{selected_rider.get('cp', 0)} W")
    col_r2.metric("Weight", f"{selected_rider.get('weight_kg', 0)} kg")
    
    pdc_data = selected_rider.get('pdc', {})
    if pdc_data:
        sorted_pdc = sorted([(int(k), v) for k, v in pdc_data.items()])
        times = [x[0] for x in sorted_pdc]
        powers = [x[1] for x in sorted_pdc]
        fig_pdc = go.Figure(data=go.Scatter(x=times, y=powers, mode='lines+markers'))
        fig_pdc.update_layout(title="Power Profile", margin=dict(l=20, r=20, t=30, b=20), height=150, xaxis_title="Sec", xaxis_type="log")
        st.sidebar.plotly_chart(fig_pdc, use_container_width=True)

# 3. Run Simulation
if st.sidebar.button("🚀 Run Simulation", type="primary"):
    with st.spinner(f"Simulating {selected_course}..."):
        try:
            cmd = [sys.executable, "simulate.py", selected_course, "--rider", selected_rider_id]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                st.success("Simulation Complete!")
                # Load the FULL result (with physics) from the generated file
                with open(JSON_PATH, 'r') as f:
                    data = json.load(f)
                    st.session_state['sim_segments'] = data['segments']
                    st.session_state['sim_summary'] = data['summary']
                    # Re-calc sections with new power data
                    st.session_state['sections'] = load_or_create_sections(data['segments'])
                st.rerun()
            else:
                st.error("Simulation Failed")
                st.code(result.stderr)
        except Exception as e:
            st.error(f"Error: {e}")

st.sidebar.divider()
st.sidebar.header("Export Data")
export_name = st.sidebar.text_input("Export Filename", value="refined_course.json")
if st.sidebar.button("💾 Save as Course JSON"):
    if not export_name.endswith(".json"):
        export_name += ".json"
    export_data = {"segments": sim_segments}
    try:
        with open(export_name, "w") as f:
            json.dump(export_data, f, indent=2)
        st.sidebar.success(f"Saved to {export_name}")
    except Exception as e:
        st.sidebar.error(f"Failed to save: {e}")

st.sidebar.divider()

# --- Segment Controls ---
st.sidebar.header("Segment Controls")

# Undo / Redo Buttons
c1, c2 = st.sidebar.columns(2)
with c1:
    if st.button("↩️ Undo", disabled=len(st.session_state['history']) == 0):
        st.session_state['redo_stack'].append(copy.deepcopy(st.session_state['sections']))
        st.session_state['sections'] = st.session_state['history'].pop()
        st.rerun()
with c2:
    if st.button("↪️ Redo", disabled=len(st.session_state['redo_stack']) == 0):
        st.session_state['history'].append(copy.deepcopy(st.session_state['sections']))
        st.session_state['sections'] = st.session_state['redo_stack'].pop()
        st.rerun()

st.sidebar.divider()

sec_df = pd.DataFrame(st.session_state['sections'])

# Format time and power for display
def format_time(x):
    if pd.isna(x) or x is None or x <= 0: return "N/A"
    return f"{int(x//60)}m {int(x%60)}s"

sec_df['Time'] = sec_df['time_sec'].apply(format_time)

# Segment Selection
new_selection = st.sidebar.multiselect(
    "Select Segments (Range Cluster)",
    options=sec_df['id'].tolist(),
    default=st.session_state['selected_ids'],
    format_func=lambda x: f"{x}: {sec_df.loc[sec_df['id']==x, 'type'].values[0]} ({sec_df.loc[sec_df['id']==x, 'dist_len'].values[0]:.1f}km)"
)

if new_selection != st.session_state['selected_ids']:
    st.session_state['selected_ids'] = new_selection
    st.rerun()

selected_ids = st.session_state['selected_ids']

if st.sidebar.button("Prepare Cluster"):
    if len(selected_ids) < 2:
        st.sidebar.warning("Select 2+ segments")
    else:
        min_id = min(selected_ids)
        max_id = max(selected_ids)
        st.session_state['merge_confirm'] = (min_id, max_id)
        st.rerun()

if st.session_state['merge_confirm']:
    min_id, max_id = st.session_state['merge_confirm']
    count = max_id - min_id + 1
    st.sidebar.warning(f"⚠️ **Confirm Cluster**\n\nSegments **{min_id}** to **{max_id}**\n(Total {count} segments) will be merged into ONE.")
    col_conf1, col_conf2 = st.sidebar.columns(2)
    if col_conf1.button("✅ Yes"):
        save_state_to_history()
        st.session_state['sections'] = merge_segments_logic(st.session_state['sections'], min_id, max_id)
        st.session_state['merge_confirm'] = None
        st.session_state['selected_ids'] = []
        st.rerun()
    if col_conf2.button("❌ No"):
        st.session_state['merge_confirm'] = None
        st.rerun()

st.sidebar.divider()

if st.sidebar.button("Reset All"):
    save_state_to_history()
    # To reset, we reload the preview data
    sim_segments, summary = load_course_preview(selected_course)
    st.session_state['sim_segments'] = sim_segments
    st.session_state['sections'] = load_or_create_sections(sim_segments)
    st.session_state['selected_ids'] = []
    st.rerun()

# --- Visualization ---
col1, col2 = st.columns([2, 1])

with col1:
    # Debug: Check data loading status
    if not sim_segments:
        st.warning("No segments loaded. Please select a valid GPX/JSON file.")
    
    df_points = pd.DataFrame(sim_segments)
    if not df_points.empty:
        # Default colors and section assignment
        df_points['color_r'] = 128
        df_points['color_g'] = 128
        df_points['color_b'] = 128
        df_points['section_id'] = -1
        
        COLORS = {"UP": [255, 0, 0], "DOWN": [0, 0, 255], "FLAT": [0, 255, 0]}
        HIGHLIGHT = [255, 255, 0]
        
        sections = st.session_state['sections']
        
        for sec in sections:
            mask = (df_points['dist_km'] >= sec['start_km']) & (df_points['dist_km'] <= sec['end_km'])
            c = COLORS.get(sec['type'], [128, 128, 128])
            if sec['id'] in selected_ids:
                c = HIGHLIGHT
            
            df_points.loc[mask, 'color_r'] = c[0]
            df_points.loc[mask, 'color_g'] = c[1]
            df_points.loc[mask, 'color_b'] = c[2]
            df_points.loc[mask, 'section_id'] = sec['id']
            
            # Tooltip text
            ele_sign = "+" if sec['gain_m'] >= 0 else "-"
            # Safe time formatting
            t_val = sec['time_sec']
            t_str = f"{int(t_val // 60)}m" if t_val is not None and t_val > 0 else "-"
            tooltip = f"Sec {sec['id']} ({sec['type']})\n{sec['start_km']:.1f}~{sec['end_km']:.1f}km\n{ele_sign}{abs(sec['gain_m']):.0f}m\n{t_str}"
            df_points.loc[mask, 'info'] = tooltip

        # --- TRUE SLOPED CURTAIN WALL (PolygonLayer + Extruded + Z-Coords) ---
        Z_SCALE = 5.0
        
        # Ensure start coordinates exist
        if 'start_lon' not in df_points.columns:
            df_points['start_lon'] = df_points['lon'].shift(1).fillna(df_points['lon'])
            df_points['start_lat'] = df_points['lat'].shift(1).fillna(df_points['lat'])
        if 'start_ele' not in df_points.columns:
            df_points['start_ele'] = df_points['ele'].shift(1).fillna(df_points['ele'])
            
        cleaned_polygons = []
        # Tiny offset (approx 1 meter) to force non-zero area on XY plane for vertical walls
        epsilon = 0.00001 
        for _, row in df_points.iterrows():
            s_lon, s_lat = float(row['start_lon']), float(row['start_lat'])
            e_lon, e_lat = float(row['lon']), float(row['lat'])
            
            # Skip if zero length
            if s_lon == e_lon and s_lat == e_lat: continue

            s_ele = float(row['start_ele']) * Z_SCALE
            e_ele = float(row['ele']) * Z_SCALE

            # Quad as Polygon (Bottom-Start -> Bottom-End -> Top-End -> Top-Start)
            # We slightly offset the top vertices to ensure the polygon has an area when projected to 2D
            poly = [
                [s_lon, s_lat, 0.0],
                [e_lon, e_lat, 0.0],
                [e_lon + epsilon, e_lat + epsilon, e_ele],
                [s_lon + epsilon, s_lat + epsilon, s_ele]
            ]
            
            cleaned_polygons.append({
                "polygon": poly,
                "color": [int(row['color_r']), int(row['color_g']), int(row['color_b']), 200],
                "info": str(row['info']) if pd.notna(row['info']) else "",
                "section_id": int(row['section_id'])
            })
        
        wall_layer = pdk.Layer(
            "PolygonLayer",
            data=cleaned_polygons,
            id="course_walls_sloped", 
            get_polygon="polygon",
            get_fill_color="color",
            get_line_color=[255, 255, 255, 80],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
            extruded=True,      # Mandatory for 3D in many pydeck versions
            get_elevation=0.1,  # Tiny elevation to ensure volume
        )
        
        view_state = pdk.ViewState(
            latitude=df_points['lat'].mean() if not df_points.empty else 37.5,
            longitude=df_points['lon'].mean() if not df_points.empty else 127.0,
            zoom=11, pitch=60, bearing=30
        )

        deck_event = st.pydeck_chart(pdk.Deck(
            layers=[wall_layer], 
            initial_view_state=view_state, 
            tooltip={"text": "{info}"},
            map_style="mapbox://styles/mapbox/dark-v10",
            parameters={"pickingRadius": 10}
        ), on_select="rerun", selection_mode="multi-object", key="deck_map_final_v2")

        if deck_event.selection:
            clicked_ids = set()
            
            # Robust selection parsing
            objects = deck_event.selection.get("objects", {})
            layer_objects = objects.get("course_walls_sloped", [])
            
            if not layer_objects and isinstance(objects, list):
                layer_objects = objects
            elif isinstance(objects, dict) and not layer_objects:
                 for v in objects.values():
                     if isinstance(v, list) and v:
                         layer_objects = v
                         break

            for obj in layer_objects:
                sec_id = obj.get('section_id')
                if sec_id is not None and sec_id != -1:
                    clicked_ids.add(int(sec_id))
            
            # Fallback to indices
            if not clicked_ids:
                indices = deck_event.selection.get("indices", {})
                layer_indices = indices.get("course_walls_sloped", [])
                if not layer_indices and isinstance(indices, list):
                    layer_indices = indices
                
                for idx in layer_indices:
                    try:
                        sec_id = cleaned_polygons[int(idx)]['section_id']
                        if sec_id != -1:
                            clicked_ids.add(sec_id)
                    except (IndexError, ValueError):
                        pass

            clicked_ids_list = sorted(list(clicked_ids))
            current_selection = set(st.session_state['selected_ids'])
            
            if clicked_ids_list:
                if len(clicked_ids_list) == 1:
                    target_id = clicked_ids_list[0]
                    if target_id in current_selection:
                        st.session_state['selected_ids'].remove(target_id)
                    else:
                        st.session_state['selected_ids'].append(target_id)
                else:
                    st.session_state['selected_ids'] = clicked_ids_list
                
                st.session_state['selected_ids'].sort()
                st.rerun()

    # --- Interactive Elevation Profile (Restored Clickable Logic) ---
    st.subheader("Interactive Elevation Profile")
    fig = go.Figure()
    
    max_ele = df_points['ele'].max() * 1.05 if not df_points.empty else 500
    sections = st.session_state['sections']
    
    # 1. Background Bars (The Click Targets) & Shapes (Colors)
    x_centers = [(s['start_km'] + s['end_km']) / 2 for s in sections]
    widths = [s['end_km'] - s['start_km'] for s in sections]
    ids = [s['id'] for s in sections]
    
    # Bar Colors (Highlighting Logic)
    bar_colors = []
    for s in sections:
        if s['id'] in selected_ids:
            bar_colors.append('rgba(255, 255, 0, 0.5)') # Yellow
        else:
            bar_colors.append('rgba(0, 0, 0, 0.001)') # Transparent (but clickable)
            
    # Hover text for bars
    hover_texts = []
    for s in sections:
        ele_sign = "+" if s['gain_m'] >= 0 else "-"
        text = (
            f"<b>Cluster {s['id']} ({s['type']})</b><br>"
            f"Range: {s['start_km']:.1f}km - {s['end_km']:.1f}km<br>"
            f"Gain: {ele_sign}{abs(s['gain_m']):.0f}m"
        )
        hover_texts.append(text)
    
    # Restore Elevation Line with MARKERS (Crucial for clicking)
    fig.add_trace(go.Scatter(
        x=df_points['dist_km'], y=df_points['ele'], 
        mode='lines+markers', # <--- RESTORED: This makes points clickable
        name='Elevation',
        line=dict(color='gray', width=1), 
        marker=dict(size=8, color='rgba(0,0,0,0)'), # Invisible but clickable markers
        hovertemplate="Elevation: %{y:.1f}m<extra></extra>"
    ))
    
    fig.add_trace(go.Bar(
        x=x_centers, y=[max_ele] * len(sections), width=widths,
        marker=dict(color=bar_colors, line=dict(width=0)),
        customdata=ids, # Pass IDs
        hovertext=hover_texts, hoverinfo='text',
        name='Segment'
    ))
    
    # Background Colors
    PLOTLY_COLORS = {"UP": "rgba(255, 0, 0, 0.3)", "DOWN": "rgba(0, 0, 255, 0.3)", "FLAT": "rgba(0, 255, 0, 0.3)"}
    shapes = []
    for sec in sections:
        fill_color = PLOTLY_COLORS.get(sec['type'], "rgba(128, 128, 128, 0.3)")
        shapes.append(dict(
            type="rect", xref="x", yref="paper", 
            x0=sec['start_km'], x1=sec['end_km'], y0=0, y1=1,
            fillcolor=fill_color, opacity=0.4, layer="below", line_width=0,
        ))
        
    fig.update_layout(
        shapes=shapes, xaxis_title="Distance (km)", yaxis_title="Elevation (m)",
        margin=dict(l=0, r=0, t=30, b=0), height=300, 
        hovermode="x unified", 
        clickmode='event+select', 
        dragmode='zoom', # Restored original dragmode
        showlegend=False
    )
    
    # Dynamic Key Logic (Original Working Version)
    chart_key = f"elevation_chart_{len(selected_ids)}_{selected_ids[0] if selected_ids else 'none'}"
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=chart_key)
    
    if event and "selection" in event:
        points = event["selection"].get("points", [])
        
        if points:
            clicked_ids = set()
            for p in points:
                # Prioritize customdata (Segment ID from Bar)
                if "customdata" in p:
                     clicked_ids.add(p["customdata"])
                else:
                    # Fallback to x-coordinate matching (if clicked on line)
                    x = p.get('x')
                    if x is not None:
                        for sec in st.session_state['sections']:
                            if sec['start_km'] <= x <= sec['end_km']:
                                clicked_ids.add(sec['id'])
            
            clicked_ids_list = list(clicked_ids)
            current_selection = set(st.session_state['selected_ids'])
            
            if len(clicked_ids_list) > 1:
                # Drag select (if any)
                if current_selection != clicked_ids:
                    st.session_state['selected_ids'] = sorted(clicked_ids_list)
                    st.rerun()
            elif len(clicked_ids_list) == 1:
                # Single click toggle
                target_id = clicked_ids_list[0]
                if target_id in current_selection:
                    st.session_state['selected_ids'].remove(target_id)
                else:
                    st.session_state['selected_ids'].append(target_id)
                
                st.session_state['selected_ids'].sort()
                st.rerun()

with col2:
    st.subheader("Segment Details")
    details_display = sec_df.rename(columns=    {
        "id": "ID", "type": "Type", "start_km": "Start", "end_km": "End", 
        "dist_len": "Dist", "gain_m": "Gain", "avg_grad": "Grade", "avg_pwr": "Power"
    })
    # Format Power column for display (N/A if None)
    details_display['Power'] = details_display['Power'].apply(lambda x: f"{int(x)}W" if pd.notna(x) and x is not None else "N/A")
    
    st.dataframe(details_display[['ID', 'Type', 'Start', 'End', 'Dist', 'Gain', 'Grade', 'Power', 'Time']].style.format({
        "Start": "{:.1f}", "End": "{:.1f}", "Dist": "{:.1f}", "Gain": "{:+.0f}", "Grade": "{:.1f}%"
    }), height=700)
