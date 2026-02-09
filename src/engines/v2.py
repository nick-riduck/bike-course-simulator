from __future__ import annotations

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.core.rider import Rider
from src.core.gpx_loader import Segment
from src.services.weather import WeatherClient

@dataclass
class PhysicsParams:
    cda: float = 0.30 
    crr: float = 0.0045 
    bike_weight: float = 8.0  
    drivetrain_loss: float = 0.05 
    air_density: float = 1.225
    drafting_factor: float = 0.0 

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

class PhysicsEngineV2:
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client
        
        # [Pacing Strategy Parameters]
        self.alpha_climb = 0.0   
        self.alpha_descent = 10.0 
        
        # Beta: 속도 비례 가중치
        self.beta_aero = 1.0
        self.v_ref = 30.0 / 3.6 
        
        # [Tuning Options]
        # mode: 'linear', 'deadzone', 'asymmetric', 'logarithmic'
        self.tuning_mode = 'linear' 
        self.deadzone_kmh = 5.0
        self.beta_slow = 0.6  
        self.beta_fast = 1.5  

    def set_tuning(self, mode: str, slow: float = 0.6, fast: float = 1.5, deadzone: float = 5.0):
        self.tuning_mode = mode
        self.beta_slow = slow
        self.beta_fast = fast
        self.deadzone_kmh = deadzone

    def _calculate_flat_speed(self, power_watts: float) -> float:
        """
        Calculates the steady-state speed on a flat road with no wind for a given power.
        Solves: P = 0.5*rho*CdA*v^3 + Crr*m*g*v
        """
        low = 0.0
        high = 200.0 / 3.6 
        
        total_mass = self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda
        g = 9.81
        p_avail = power_watts * (1 - self.params.drivetrain_loss)
        
        for _ in range(10):
            mid = (low + high) / 2
            if mid < 0.1: mid = 0.1
            f_aero = 0.5 * self.params.air_density * eff_cda * (mid ** 2)
            f_roll = total_mass * g * self.params.crr
            p_req = (f_aero + f_roll) * mid
            
            if p_req > p_avail: high = mid
            else: low = mid
                
        return (low + high) / 2

    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        low = 10.0
        high = 1500.0
        best_result: Optional[SimulationResult] = None
        
        for i in range(15):
            mid = (low + high) / 2.0
            
            # [Adaptive V_ref Update]
            self.v_ref = self._calculate_flat_speed(mid)
            
            res = self.simulate_course(segments, p_base=mid, max_power_limit=mid * 3.0)
            
            simulated_intensity = res.normalized_power if res.normalized_power > 0 else mid
            pdc_limit_watts = self._get_dynamic_pdc_limit(res.total_time_sec)
            
            if not res.is_success or simulated_intensity > pdc_limit_watts:
                high = mid 
            else:
                best_result = res
                low = mid 
        
        return best_result if best_result else self.simulate_course(segments, low, low * 3.0)

    def _get_dynamic_pdc_limit(self, duration_sec: float) -> float:
        sorted_pdc = sorted([(int(k), v) for k, v in self.rider.pdc.items()])
        if not sorted_pdc: return self.rider.cp
        max_pdc_time, max_pdc_watts = sorted_pdc[-1]
        
        if duration_sec > max_pdc_time:
            # [Riegel Fatigue Model]
            # 지수 -0.07은 엘리트 선수급, -0.10은 일반 동호인 수준의 피로 누적을 의미.
            # 5시간 이상의 초장거리 주행 시 파워 저하를 더 현실적으로 반영하기 위해 -0.10 채택.
            riegel_exponent = -0.10 
            return max_pdc_watts * (duration_sec / max_pdc_time) ** riegel_exponent
            
        return self.rider.get_pdc_power(duration_sec)

    def simulate_course(self, segments: List[Segment], p_base: float, max_power_limit: float) -> SimulationResult:
        self.rider.reset_state()
        
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 0.1 # Start from near-zero
        min_w_prime = self.rider.w_prime_max
        track_data = []

        wind_speed_global = 0.0
        wind_deg_global = 0.0
        if self.weather and self.weather.use_scenario_mode:
             d = self.weather._get_scenario_weather()
             wind_speed_global = d['wind_speed']
             wind_deg_global = d['wind_deg']

        f_max_initial = self.rider.weight * 9.81 * 1.5
        prev_heading = segments[0].heading

        for seg in segments:
            # --- Cornering Speed Limit Logic (Restored from Jan 23) ---
            heading_change = abs(seg.heading - prev_heading)
            if heading_change > 180: heading_change = 360 - heading_change
            
            if seg.length > 0 and heading_change > 1.0: 
                theta_rad = math.radians(heading_change)
                curvature_rad = theta_rad / seg.length
                
                if curvature_rad > 0.0001:
                    radius = 1.0 / curvature_rad
                    mu = 0.8
                    g = 9.81
                    v_corner_limit = math.sqrt(mu * g * radius)
                    v_current = min(v_current, v_corner_limit) 
            
            prev_heading = seg.heading
            # ---------------------------------------------

            rel_angle_rad = math.radians(wind_deg_global - seg.heading)
            v_headwind_env = wind_speed_global * math.cos(rel_angle_rad)
            
            decay_factor = 1.0
            if total_time > 3600:
                decay_factor = (3600.0 / total_time) ** 0.05
            current_f_limit = f_max_initial * decay_factor
            
            v_next, time_sec, is_walking, p_avg_segment = self._solve_segment_physics(
                seg, p_base, v_current, v_headwind_env, current_f_limit, max_power_limit
            )
            
            p_actual = 30.0 if is_walking else p_avg_segment
            
            self.rider.update_w_prime(p_actual, time_sec)
            
            if self.rider.is_bonked():
                return SimulationResult(total_time, p_base, 0, 0, 0, 0, -1, False, "BONK")

            total_time += time_sec
            total_work += p_actual * time_sec
            weighted_power_sum += (p_actual ** 4) * time_sec
            min_w_prime = min(min_w_prime, self.rider.w_prime_bal)

            track_data.append({
                "dist_km": seg.end_dist / 1000.0,
                "ele": seg.end_ele,
                "grade_pct": seg.grade * 100,
                "speed_kmh": (v_next + v_current) / 2 * 3.6,
                "power": p_actual,
                "time_sec": total_time,
                "w_prime_bal": self.rider.w_prime_bal
            })
            v_current = v_next
            
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        dist_km = sum(s.length for s in segments) / 1000.0
        avg_spd = (dist_km * 3600) / total_time if total_time > 0 else 0
        
        return SimulationResult(total_time, p_base, avg_spd, avg_p, np, total_work/1000, min_w_prime, True, track_data=track_data)

    def _calculate_target_power_dynamic(self, p_base: float, grade: float, max_limit: float, current_v: float) -> float:
        """
        [Dynamic Pacing Function with Tuning Modes]
        """
        # Safety: Disable pedaling on steep descents (Coasting)
        if grade < -0.05:
            return 0.0

        # Aero Factor (Velocity-based Pacing)
        aero_factor = 1.0
        
        # --- Mode Switching Logic ---
        if self.tuning_mode == 'deadzone':
            v_kmh = current_v * 3.6
            v_ref_kmh = self.v_ref * 3.6
            # Deadzone Check
            if abs(v_kmh - v_ref_kmh) > self.deadzone_kmh:
                ratio = 1.0 - (current_v / self.v_ref)
                aero_factor = 1.0 + (self.beta_aero * ratio)
                
        elif self.tuning_mode == 'asymmetric':
            ratio = 1.0 - (current_v / self.v_ref)
            # Positive ratio = Slower than ref (Climb)
            # Negative ratio = Faster than ref (Descent)
            beta = self.beta_slow if ratio > 0 else self.beta_fast 
            aero_factor = 1.0 + (beta * ratio)
            
        elif self.tuning_mode == 'logarithmic':
            safe_v = max(0.5, current_v) 
            aero_factor = 1.0 - (self.beta_aero * math.log(safe_v / self.v_ref))
            
        elif self.tuning_mode == 'theory':
            # [Pure Theoretical Optimum]
            safe_v = max(0.5, current_v)
            aero_factor = self.v_ref / safe_v
            
        else: # 'linear' (Original)
            ratio = 1.0 - (current_v / self.v_ref)
            aero_factor = 1.0 + (self.beta_aero * ratio)

        # Safety: Minimum 10% effort (unless coasting)
        aero_factor = max(0.1, aero_factor) 
        
        target = p_base * aero_factor
        
        if grade >= 0:
            return min(target, max_limit)
        return target

    def _solve_segment_physics(self, seg: Segment, p_base: float, v_entry: float, v_wind: float, f_limit: float, max_power_limit: float) -> Tuple[float, float, bool, float]:
        """
        [Nested Solver Implementation]
        """
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        f_gravity = total_mass * g * seg.grade
        f_roll = total_mass * g * self.params.crr
        
        chunk_size = 20.0
        num_chunks = max(1, math.ceil(seg.length / chunk_size))
        d_sub = seg.length / num_chunks
        
        v_current = v_entry
        t_total = 0.0
        is_walking = False
        min_speed_ms = 5.0 / 3.6
        accumulated_power = 0.0
        first_raw_speed = None

        for _ in range(num_chunks):
            low = 0.01
            high = 45.0 
            
            v_next = v_current
            p_final_chunk = p_base 
            
            for _i in range(15): 
                if (high - low) < 0.005: break
                mid_v = (low + high) / 2
                
                # Dynamic Power Calculation using Tuning Mode
                p_dynamic = self._calculate_target_power_dynamic(p_base, seg.grade, max_power_limit, current_v=mid_v)
                p_avail = p_dynamic * (1 - self.params.drivetrain_loss)
                
                v_avg = (v_current + mid_v) / 2
                if v_avg < 0.1: v_avg = 0.1
                
                f_pedal = min(p_avail / v_avg, f_limit)
                v_air = v_avg + v_wind
                f_drag = 0.5 * self.params.air_density * eff_cda * (v_air * abs(v_air))
                
                # --- Downhill Braking Logic (Soft Wall @ 80km/h) ---
                f_brake = 0.0
                if mid_v > 13.8889: # 50 km/h
                    v_avg_kmh = mid_v * 3.6
                    # Deceleration a = 0.22 * (V - 50)^1.2 (km/h per sec)
                    a_brake_ms2 = (0.22 * ((v_avg_kmh - 50.0) ** 1.2)) / 3.6
                    f_brake = total_mass * a_brake_ms2

                f_net = f_pedal - f_drag - f_gravity - f_roll - f_brake
                work_net = f_net * d_sub
                ke_initial = 0.5 * total_mass * (v_current ** 2)
                ke_final_target = 0.5 * total_mass * (mid_v ** 2)
                
                if (ke_initial + work_net) > ke_final_target:
                    low = mid_v
                    p_final_chunk = p_dynamic
                else:
                    high = mid_v
            
            v_next = (low + high) / 2
            raw_v_next = v_next
            
            if v_next < min_speed_ms:
                v_next = min_speed_ms
                is_walking = True
                if first_raw_speed is None: first_raw_speed = raw_v_next
            
            v_avg_chunk = (v_current + v_next) / 2
            if v_avg_chunk < 0.1: v_avg_chunk = 0.1
            t_total += d_sub / v_avg_chunk
            accumulated_power += p_final_chunk
            v_current = v_next
            
        final_raw_return = first_raw_speed if first_raw_speed is not None else v_next
        p_avg_total = accumulated_power / num_chunks
        
        return v_current, t_total, is_walking, p_avg_total
