"""
[Common Modules for Physics Verification]
실제 프로젝트의 src/ 디렉토리에서 실험에 필요한 핵심 데이터 클래스 및 로더를 발췌하였습니다.
"""
from dataclasses import dataclass
from typing import List, Dict, Any
import math
import xml.etree.ElementTree as ET

@dataclass
class PhysicsParams:
    cda: float = 0.30 
    crr: float = 0.0045 
    bike_weight: float = 8.0  
    drivetrain_loss: float = 0.05 
    air_density: float = 1.225
    drafting_factor: float = 0.0 

class Rider:
    def __init__(self, weight: float, cp: float, w_prime_max: float = 20000.0):
        self.weight = weight
        self.cp = cp
        self.w_prime_max = w_prime_max
        self.w_prime_bal = w_prime_max
        self.pdc: Dict[str, float] = {}
    
    def reset_state(self):
        self.w_prime_bal = self.w_prime_max

    def update_w_prime(self, power: float, duration: float):
        if power > self.cp:
            self.w_prime_bal -= (power - self.cp) * duration
        elif power < self.cp:
            tau = 546.0 
            self.w_prime_bal += (self.w_prime_max - self.w_prime_bal) * (1 - math.exp(-duration / tau))
        
        if self.w_prime_bal > self.w_prime_max:
            self.w_prime_bal = self.w_prime_max

    def is_bonked(self) -> bool:
        return self.w_prime_bal < 0

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

@dataclass
class SimulationResult:
    total_time_sec: float
    base_power: float
    average_speed_kmh: float
    average_power: float
    normalized_power: float
    work_kj: float
    w_prime_min: float
    is_success: bool
    fail_reason: str = ""
    track_data: List[Dict[str, Any]] = None

@dataclass
class TrackPoint:
    lat: float
    lon: float
    ele: float
    distance_from_start: float = 0.0

class GpxLoader:
    def __init__(self, gpx_path: str):
        self.gpx_path = gpx_path
        self.points: List[TrackPoint] = []
        self.segments: List[Segment] = []

    def load(self):
        try:
            tree = ET.parse(self.gpx_path)
            root = tree.getroot()
            ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
            trkpts = root.findall(".//gpx:trkpt", ns) or root.findall(".//trkpt")
        except:
            print(f"Error parsing GPX: {self.gpx_path}")
            return

        self.points = []
        total_dist = 0.0
        prev_pt = None

        for pt in trkpts:
            lat = float(pt.attrib['lat'])
            lon = float(pt.attrib['lon'])
            ele = 0.0
            
            # Simple fallback for ele tag
            ele_tag = pt.find('gpx:ele', ns)
            if ele_tag is not None:
                ele = float(ele_tag.text)
            elif pt.find('ele') is not None:
                ele = float(pt.find('ele').text)

            current_pt = TrackPoint(lat, lon, ele)

            if prev_pt:
                d = self._haversine_distance(prev_pt, current_pt)
                if d < 2.0: continue # Filter noise
                total_dist += d
            
            current_pt.distance_from_start = total_dist
            self.points.append(current_pt)
            prev_pt = current_pt

    def compress_segments(self, grade_threshold=0.005, max_length=200.0) -> List[Segment]:
        if not self.points: return []
        
        segments = []
        start_idx = 0
        seg_idx = 0
        
        for i in range(1, len(self.points)):
            p_start = self.points[start_idx]
            p_curr = self.points[i]
            
            dist = p_curr.distance_from_start - p_start.distance_from_start
            
            if dist < 10.0: continue
            
            ele_diff = p_curr.ele - p_start.ele
            grade = ele_diff / dist if dist > 0 else 0
            
            # Flush conditions
            if dist >= max_length:
                self._add_segment(segments, seg_idx, p_start, p_curr, dist, grade)
                seg_idx += 1
                start_idx = i
                
        # Last segment
        if start_idx < len(self.points) - 1:
            p_start = self.points[start_idx]
            p_end = self.points[-1]
            dist = p_end.distance_from_start - p_start.distance_from_start
            grade = (p_end.ele - p_start.ele) / dist if dist > 0 else 0
            self._add_segment(segments, seg_idx, p_start, p_end, dist, grade)
            
        return segments

    def _add_segment(self, segments, idx, p1, p2, length, grade):
        segments.append(Segment(
            index=idx,
            start_dist=p1.distance_from_start,
            end_dist=p2.distance_from_start,
            length=length,
            grade=grade,
            heading=0.0, # Simplified
            start_ele=p1.ele,
            end_ele=p2.ele,
            lat=p2.lat,
            lon=p2.lon
        ))

    def _haversine_distance(self, p1: TrackPoint, p2: TrackPoint) -> float:
        R = 6378137 
        dLat = math.radians(p2.lat - p1.lat)
        dLon = math.radians(p2.lon - p1.lon)
        a = math.sin(dLat/2) * math.sin(dLat/2) + \
            math.cos(math.radians(p1.lat)) * math.cos(math.radians(p2.lat)) * \
            math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c