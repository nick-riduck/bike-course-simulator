from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class TrackPoint:
    lat: float
    lon: float
    ele: float
    distance_from_start: float = 0.0  # meters

@dataclass
class Segment:
    index: int
    start_dist: float  # meters
    end_dist: float    # meters
    length: float      # meters
    grade: float       # decimal (0.05 = 5%)
    heading: float     # degrees (0=North, 90=East)
    start_ele: float   # meters
    end_ele: float     # meters
    lat: float = 0.0   # End latitude
    lon: float = 0.0   # End longitude
    start_lat: float = 0.0
    start_lon: float = 0.0

class GpxLoader:
    def __init__(self, gpx_path: str):
        self.gpx_path = gpx_path
        self.points: List[TrackPoint] = []
        self.segments: List[Segment] = []

    def load_from_json_data(self, data: List[dict]):
        """Load segments directly from a list of dictionaries (Simulation Result format)."""
        self.segments = []
        prev_dist = 0.0
        prev_ele = data[0]['ele'] if data else 0.0
        
        # Check if first point is at dist 0, otherwise assume start at 0
        if data and data[0]['dist_km'] == 0:
            prev_ele = data[0]['ele']
            start_k = 1
        else:
            start_k = 0
            if data:
                prev_ele = data[0]['ele'] 

        for i in range(start_k, len(data)):
            d = data[i]
            dist_km = d['dist_km']
            curr_dist = dist_km * 1000.0
            length = curr_dist - prev_dist
            
            if length <= 0:
                continue
                
            grade = d.get('grade_pct', 0.0) / 100.0
            curr_ele = d['ele']
            heading = d.get('heading', 0.0)
            lat = d.get('lat', 0.0)
            lon = d.get('lon', 0.0)
            
            seg = Segment(
                index=len(self.segments),
                start_dist=prev_dist,
                end_dist=curr_dist,
                length=length,
                grade=grade,
                heading=heading,
                start_ele=prev_ele,
                end_ele=curr_ele,
                lat=lat,
                lon=lon,
                start_lat=data[i-1].get('lat', lat) if i > 0 else lat,
                start_lon=data[i-1].get('lon', lon) if i > 0 else lon
            )
            self.segments.append(seg)
            
            prev_dist = curr_dist
            prev_ele = curr_ele

    def load_from_json_data(self, data: List[dict]):
        """Load segments directly from a list of dictionaries (Simulation Result format)."""
        self.segments = []
        if not data:
            return

        # Determine start values
        prev_dist = 0.0
        prev_ele = data[0]['ele']
        
        # If data starts with a segment at dist > 0, we treat it as starting from prev_dist=0
        # If the first point in JSON has dist_km=0, that's just a start point (not a segment usually), 
        # but simulation_result.json segments list usually contains the END points of segments.
        # e.g. [{dist_km: 0.01, ...}, ...]
        
        start_k = 0
        if data[0]['dist_km'] == 0:
             # If first point is 0km, it's likely the start point (not a segment end)
             # But our list should be segment ends.
             # If it exists, skip it as a segment but use it for ele
             prev_ele = data[0]['ele']
             start_k = 1

        for i in range(start_k, len(data)):
            d = data[i]
            dist_km = d['dist_km']
            curr_dist = dist_km * 1000.0
            length = curr_dist - prev_dist
            
            if length <= 0:
                continue
                
            grade = d.get('grade_pct', 0.0) / 100.0
            curr_ele = d['ele']
            heading = d.get('heading', 0.0)
            lat = d.get('lat', 0.0)
            lon = d.get('lon', 0.0)
            
            seg = Segment(
                index=len(self.segments),
                start_dist=prev_dist,
                end_dist=curr_dist,
                length=length,
                grade=grade,
                heading=heading,
                start_ele=prev_ele,
                end_ele=curr_ele,
                lat=lat,
                lon=lon,
                start_lat=data[i-1].get('lat', lat) if i > 0 else lat,
                start_lon=data[i-1].get('lon', lon) if i > 0 else lon
            )
            self.segments.append(seg)
            
            prev_dist = curr_dist
            prev_ele = curr_ele

    def load(self):
        """Parse GPX and calculate basic distances."""
        tree = ET.parse(self.gpx_path)
        root = tree.getroot()
        
        # XML Namespace handling usually needed for GPX
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        
        # Find all trkpt (track points)
        # Try with namespace first, fall back to simple tag search if needed
        trkpts = root.findall(".//gpx:trkpt", ns)
        if not trkpts:
             trkpts = root.findall(".//trkpt")

        self.points = []
        total_dist = 0.0
        prev_pt = None

        for pt in trkpts:
            lat = float(pt.attrib['lat'])
            lon = float(pt.attrib['lon'])
            ele = float(pt.find('gpx:ele', ns).text) if pt.find('gpx:ele', ns) is not None else 0.0
            if ele == 0.0 and pt.find('ele') is not None:
                ele = float(pt.find('ele').text)

            current_pt = TrackPoint(lat, lon, ele)

            if prev_pt:
                # 2D Distance (Haversine approximation for short distances)
                d = self._haversine_distance(prev_pt, current_pt)
                
                # [Data Cleaning] Min Distance Filter (5m)
                # Skip tiny movements that cause grade spikes
                if d < 5.0:
                    continue
                    
                total_dist += d
            
            current_pt.distance_from_start = total_dist
            self.points.append(current_pt)
            prev_pt = current_pt

    def smooth_elevation(self, window_size: int = 10):
        """Apply Moving Average smoothing to elevation."""
        if not self.points:
            return

        elevations = [p.ele for p in self.points]
        smoothed = []
        
        for i in range(len(elevations)):
            start = max(0, i - window_size // 2)
            end = min(len(elevations), i + window_size // 2 + 1)
            window = elevations[start:end]
            smoothed.append(sum(window) / len(window))
            
        for i, p in enumerate(self.points):
            p.ele = smoothed[i]

    def compress_segments(self, grade_threshold: float = 0.005, heading_threshold: float = 15.0, max_length: float = 1000.0) -> List[Segment]:
        """
        Adaptive Segmentation Algorithm.
        
        Args:
            grade_threshold: 0.005 = 0.5% grade change triggers new segment
            heading_threshold: degrees change triggers new segment
            max_length: meters, force cut if segment gets too long
        """
        if not self.points:
            return []

        segments = []
        start_idx = 0
        
        # Initial reference values
        ref_grade = 0.0
        ref_heading = 0.0
        
        # Calculate initial small segment to set references if possible
        if len(self.points) > 1:
            ref_grade = self._calculate_grade(self.points[0], self.points[1])
            ref_heading = self._calculate_bearing(self.points[0], self.points[1])

        for i in range(1, len(self.points)):
            curr_pt = self.points[i]
            start_pt = self.points[start_idx]
            
            # Current segment properties (cumulative from start_idx)
            dist = curr_pt.distance_from_start - start_pt.distance_from_start
            
            if dist == 0: continue

            # Current "Instant" properties (between prev and curr) for checking sudden changes
            # Or "Average" properties of the candidate segment?
            # Strategy: Compare "Average Grade of Candidate Segment" vs "Last Recorded Grade"
            
            curr_grade = (curr_pt.ele - start_pt.ele) / dist
            curr_heading = self._calculate_bearing(start_pt, curr_pt)
            
            # [Data Cleaning] Clamp Grade to realistic range (-25% to +25%)
            if curr_grade > 0.25: curr_grade = 0.25
            if curr_grade < -0.25: curr_grade = -0.25

            # Check Triggers
            is_grade_change = abs(curr_grade - ref_grade) > grade_threshold
            is_heading_change = abs(curr_heading - ref_heading) > heading_threshold
            is_too_long = dist > max_length
            is_last_point = (i == len(self.points) - 1)

            if (is_grade_change or is_heading_change or is_too_long) and dist > 10: # Min 10m length
                # Cut Segment
                seg = Segment(
                    index=len(segments),
                    start_dist=start_pt.distance_from_start,
                    end_dist=curr_pt.distance_from_start,
                    length=dist,
                    grade=curr_grade,
                    heading=curr_heading,
                    start_ele=start_pt.ele,
                    end_ele=curr_pt.ele,
                    lat=curr_pt.lat,
                    lon=curr_pt.lon,
                    start_lat=start_pt.lat,
                    start_lon=start_lon if 'start_lon' in locals() else start_pt.lon # safety check
                )
                # Correction: use start_pt.lon directly
                seg.start_lon = start_pt.lon
                segments.append(seg)
                
                # Reset references
                start_idx = i
                ref_grade = 0.0 # Will be updated in next calculation if needed, but actually we need next instant grade
                # Accurate reference update:
                if i < len(self.points) - 1:
                    ref_grade = self._calculate_grade(self.points[i], self.points[i+1])
                    ref_heading = self._calculate_bearing(self.points[i], self.points[i+1])
            
            elif is_last_point:
                # Add final segment
                seg = Segment(
                    index=len(segments),
                    start_dist=start_pt.distance_from_start,
                    end_dist=curr_pt.distance_from_start,
                    length=dist,
                    grade=curr_grade,
                    heading=curr_heading,
                    start_ele=start_pt.ele,
                    end_ele=curr_pt.ele,
                    lat=curr_pt.lat,
                    lon=curr_pt.lon,
                    start_lat=start_pt.lat,
                    start_lon=start_pt.lon
                )
                segments.append(seg)

        self.segments = segments
        return segments

    def _haversine_distance(self, p1: TrackPoint, p2: TrackPoint) -> float:
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(p1.lat), math.radians(p2.lat)
        dphi = math.radians(p2.lat - p1.lat)
        dlambda = math.radians(p2.lon - p1.lon)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    def _calculate_grade(self, p1: TrackPoint, p2: TrackPoint) -> float:
        dist = self._haversine_distance(p1, p2)
        if dist == 0: return 0.0
        return (p2.ele - p1.ele) / dist

    def _calculate_bearing(self, p1: TrackPoint, p2: TrackPoint) -> float:
        """Calculate initial bearing from p1 to p2 in degrees."""
        lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
        lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
        
        y = math.sin(lon2 - lon1) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360
