from __future__ import annotations
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.core.rider import Rider
from src.core.gpx_loader import Segment
from src.weather_client import WeatherClient
from src.engines.v2 import PhysicsParams, SimulationResult

class PhysicsEngineV4:
    """
    Physics Engine V4: Gravity Ratio Heuristic
    - Replaces explicit If/Else gradient logic with a continuous physical ratio.
    - Ratio = P_gravity / (P_gravity_abs + P_aero + P_roll)
    - Automatically handles Uphill (Invest) vs Flat/Downhill (Save).
    """
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client
        
        # Sensitivity: How strongly to react to the ratio.
        # Ratio is roughly -1.0 to 1.0.
        # If Ratio = 1.0 (Steep Climb), we want e.g. 2.5x power. So K = 1.5?
        # V2 uses 2.5 * grade. 10% grade -> 1.25x.
        # Here, 10% grade -> Ratio ~ 0.8 -> 1 + K*0.8 = 1.25 -> K ~ 0.3?
        # Let's tune K to match V2's aggressiveness.
        self.sensitivity = 1.5 

    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        """
        Standard Binary Search for Average Power (Same as V2)
        """
        low = 10.0
        high = 1500.0
        best_result: Optional[SimulationResult] = None
        
        for i in range(15):
            mid = (low + high) / 2.0
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
            # Riegel Exponent -0.10 (General Cyclist Fatigue)
            riegel_exponent = -0.10 
            return max_pdc_watts * (duration_sec / max_pdc_time) ** riegel_exponent
            
        return self.rider.get_pdc_power(duration_sec)

    def _calculate_target_power(self, seg: Segment, p_base: float, max_limit: float, current_v: float) -> float:
        """
        [Gravity Ratio Heuristic - Dynamic]
        Uses CURRENT speed (v_curr) to capture inertia effects.
        Ignores wind strategy (v_wind = 0).
        """
        # 0. Kickstart if stopped
        if current_v < 0.1:
            return min(p_base * 1.5, max_limit)
            
        # 1. Physics Components based on CURRENT state
        total_mass = self.rider.weight + self.params.bike_weight
        g = 9.81
        theta = math.atan(seg.grade)
        
        # P = F * v_curr
        p_grav = total_mass * g * math.sin(theta) * current_v
        p_roll = total_mass * g * self.params.crr * math.cos(theta) * current_v
        
        # Aero power (Wind = 0)
        v_air = current_v 
        p_aero = 0.5 * self.params.air_density * self.params.cda * (v_air ** 3)
        
        # 2. Gravity Ratio
        # R = P_grav / (|P_grav| + P_aero + P_roll)
        denominator = abs(p_grav) + p_aero + p_roll + 1.0 # +1 for stability
        ratio = p_grav / denominator
        
        # 3. Apply Strategy
        # Factor = 1 + Sensitivity * Ratio
        factor = 1.0 + (self.sensitivity * ratio)
        target = p_base * factor
        
        return max(0.0, min(target, max_limit))

    def simulate_course(self, segments: List[Segment], p_base: float, max_power_limit: float) -> SimulationResult:
        self.rider.reset_state()
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 0.1
        min_w_prime = self.rider.w_prime_max
        track_data = []
        f_max_initial = self.rider.weight * 9.81 * 1.5

        wind_speed = 0.0 
        
        for seg in segments:
            # Pass v_current to the calculation
            p_target = self._calculate_target_power(seg, p_base, max_power_limit, v_current)
            
            # Physics Simulation
            v_next, time_sec, is_walking, p_calc = self._solve_segment_physics(seg, p_target, v_current, 0.0, f_max_initial)
            
            # Rider State Update
            p_actual = p_target 
            if is_walking: p_actual = 30.0 
            
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
                "time_sec": total_time
            })
            v_current = v_next
            
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        avg_spd = (sum(s.length for s in segments)/1000.0 * 3600) / total_time if total_time > 0 else 0
        
        return SimulationResult(total_time, p_base, avg_spd, avg_p, np, total_work/1000, min_w_prime, True, track_data=track_data)

    def _solve_segment_physics(self, seg: Segment, power: float, v_entry: float, v_wind: float, f_limit: float) -> Tuple[float, float, bool, float]:
        # Reusing V2 Core Physics
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        p_avail = power * (1 - self.params.drivetrain_loss)
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

        for _ in range(num_chunks):
            low, high = 0.01, 45.0
            for _i in range(10): # Faster approx
                mid = (low + high) / 2
                v_avg = (v_current + mid) / 2
                if v_avg < 0.1: v_avg = 0.1
                
                f_pedal = min(p_avail / v_avg, f_limit)
                f_drag = 0.5 * self.params.air_density * eff_cda * v_avg**2
                f_net = f_pedal - f_drag - f_gravity - f_roll
                
                if (0.5 * total_mass * v_current**2 + f_net * d_sub) > 0.5 * total_mass * mid**2:
                    low = mid
                else:
                    high = mid
            
            v_next = (low + high) / 2
            if v_next < min_speed_ms:
                v_next = min_speed_ms
                is_walking = True
            
            v_current = v_next
            t_total += d_sub / ((v_current + v_next)/2 + 1e-6)
            
        return v_current, t_total, is_walking, power

    def _get_fatigue_adjusted_limit(self, duration_sec: float) -> float:
        sorted_pdc = sorted([(int(k), v) for k, v in self.rider.pdc.items()])
        if not sorted_pdc: return self.rider.cp
        max_pdc_time, max_pdc_watts = sorted_pdc[-1]
        if duration_sec > max_pdc_time:
            return max_pdc_watts * (duration_sec / max_pdc_time) ** -0.10
        return self.rider.get_pdc_power(duration_sec)
