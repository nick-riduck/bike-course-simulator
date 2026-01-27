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
    distance_from_start: float = 0.0
    # Shifted coordinates for visualization (right side)
    shifted_lat: float = 0.0
    shifted_lon: float = 0.0

@dataclass
class Segment:
    index: int
    start_dist: float
    end_dist: float
    length: float
    grade: float
    heading: float
    start_ele: float
    end_ele: float
    lat: float = 0.0
    lon: float = 0.0
    start_lat: float = 0.0
    start_lon: float = 0.0
    # Shifted coordinates for 3D curtain
    shifted_start_lat: float = 0.0
    shifted_start_lon: float = 0.0
    shifted_end_lat: float = 0.0
    shifted_end_lon: float = 0.0

class GpxLoader:
    def __init__(self, gpx_path: str):
        self.gpx_path = gpx_path
        self.points: List[TrackPoint] = []
        self.segments: List[Segment] = []

    def load(self):
        tree = ET.parse(self.gpx_path)
        root = tree.getroot()
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        trkpts = root.findall(".//gpx:trkpt", ns) or root.findall(".//trkpt")

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
                d = self._haversine_distance(prev_pt, current_pt)
                if d < 2.0: continue # Filter noise
                total_dist += d
            
            current_pt.distance_from_start = total_dist
            self.points.append(current_pt)
            prev_pt = current_pt
            
        # Calculate Shifted Path immediately after loading
        self._calculate_shifted_path(offset_meters=15.0)

    def _calculate_shifted_path(self, offset_meters: float):
        if len(self.points) < 2: return

        # Helper: Calculate bearing
        def get_bearing(lat1, lon1, lat2, lon2):
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            y = math.sin(lon2 - lon1) * math.cos(lat2)
            x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
            return (math.degrees(math.atan2(y, x)) + 360) % 360

        # Helper: Shift point
        def shift(lat, lon, bearing, dist):
            R = 6378137
            lat, lon, bearing = map(math.radians, [lat, lon, bearing])
            lat2 = math.asin(math.sin(lat) * math.cos(dist/R) + math.cos(lat) * math.sin(dist/R) * math.cos(bearing))
            lon2 = lon + math.atan2(math.sin(bearing) * math.sin(dist/R) * math.cos(lat), math.cos(dist/R) - math.sin(lat) * math.sin(lat2))
            return math.degrees(lat2), math.degrees(lon2)

        for i in range(len(self.points)):
            curr = self.points[i]
            bearing = 0.0
            
            if i == 0:
                next_pt = self.points[i+1]
                bearing = get_bearing(curr.lat, curr.lon, next_pt.lat, next_pt.lon) + 90
            elif i == len(self.points) - 1:
                prev_pt = self.points[i-1]
                bearing = get_bearing(prev_pt.lat, prev_pt.lon, curr.lat, curr.lon) + 90
            else:
                prev_pt = self.points[i-1]
                next_pt = self.points[i+1]
                b1 = get_bearing(prev_pt.lat, prev_pt.lon, curr.lat, curr.lon)
                b2 = get_bearing(curr.lat, curr.lon, next_pt.lat, next_pt.lon)
                
                # Angle Bisector logic
                avg_bearing = (b1 + b2) / 2
                if abs(b1 - b2) > 180: avg_bearing += 180
                bearing = avg_bearing + 90

            shifted_lat, shifted_lon = shift(curr.lat, curr.lon, bearing, offset_meters)
            curr.shifted_lat = shifted_lat
            curr.shifted_lon = shifted_lon

    def compress_segments(self, grade_threshold: float = 0.005, heading_threshold: float = 15.0, max_length: float = 1000.0) -> List[Segment]:
        if not self.points: return []

        segments = []
        start_idx = 0
        ref_grade = 0.0
        ref_heading = 0.0

        if len(self.points) > 1:
            ref_grade = self._calculate_grade(self.points[0], self.points[1])
            ref_heading = self._calculate_bearing(self.points[0], self.points[1])

        for i in range(1, len(self.points)):
            curr_pt = self.points[i]
            start_pt = self.points[start_idx]
            
            dist = curr_pt.distance_from_start - start_pt.distance_from_start
            if dist == 0: continue

            curr_grade = (curr_pt.ele - start_pt.ele) / dist
            curr_heading = self._calculate_bearing(start_pt, curr_pt)
            
            if curr_grade > 0.25: curr_grade = 0.25
            if curr_grade < -0.25: curr_grade = -0.25

            is_grade_change = abs(curr_grade - ref_grade) > grade_threshold
            is_heading_change = abs(curr_heading - ref_heading) > heading_threshold
            is_too_long = dist > max_length
            is_last_point = (i == len(self.points) - 1)

            if (is_grade_change or is_heading_change or is_too_long) and dist > 10:
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
                    start_lon=start_pt.lon,
                    # Populate Shifted Coordinates from points
                    shifted_start_lat=start_pt.shifted_lat,
                    shifted_start_lon=start_pt.shifted_lon,
                    shifted_end_lat=curr_pt.shifted_lat,
                    shifted_end_lon=curr_pt.shifted_lon
                )
                segments.append(seg)
                
                start_idx = i
                ref_grade = 0.0
                if i < len(self.points) - 1:
                    ref_grade = self._calculate_grade(self.points[i], self.points[i+1])
                    ref_heading = self._calculate_bearing(self.points[i], self.points[i+1])
            
            elif is_last_point:
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
                    start_lon=start_pt.lon,
                    shifted_start_lat=start_pt.shifted_lat,
                    shifted_start_lon=start_pt.shifted_lon,
                    shifted_end_lat=curr_pt.shifted_lat,
                    shifted_end_lon=curr_pt.shifted_lon
                )
                segments.append(seg)

        self.segments = segments
        return segments

    def _haversine_distance(self, p1: TrackPoint, p2: TrackPoint) -> float:
        R = 6371000 
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
        lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
        lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
        y = math.sin(lon2 - lon1) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360