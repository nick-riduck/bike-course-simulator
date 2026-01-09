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

class GpxLoader:
    def __init__(self, gpx_path: str):
        self.gpx_path = gpx_path
        self.points: List[TrackPoint] = []
        self.segments: List[Segment] = []

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
                total_dist += d
            
            current_pt.distance_from_start = total_dist
            self.points.append(current_pt)
            prev_pt = current_pt

    def smooth_elevation(self, window_size: int = 5):
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
                    end_ele=curr_pt.ele
                )
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
                    end_ele=curr_pt.ele
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
