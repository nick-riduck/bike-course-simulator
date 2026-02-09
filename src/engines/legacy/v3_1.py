from __future__ import annotations
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.core.rider import Rider
from src.core.gpx_loader import Segment
from src.weather_client import WeatherClient
from src.engines.v2 import PhysicsParams, SimulationResult

class PhysicsEngineV3_1:
    """
    Physics Engine V3.1: High-Resolution Lagrange Optimizer
    - Broadens Lambda search range to ensure full energy budget utilization.
    - Removes arbitrary power floors, allowing physics to dictate distribution.
    """
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client

    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        low_p, high_p = 50.0, self.rider.cp * 1.5 
        best_result: Optional[SimulationResult] = None
        
        for i in range(12):
            mid_p = (low_p + high_p) / 2.0
            
            # Baseline to get Energy Budget
            flat_profile = [mid_p] * len(segments)
            base_res = self.simulate_course(segments, flat_profile)
            
            if not base_res.is_success:
                high_p = mid_p
                continue

            total_energy_budget = base_res.work_kj * 1000.0
            
            # Solve optimization with BROAD lambda range
            power_profile = self.solve_lagrange_optimizer(segments, total_energy_budget, self.rider.cp * 3.0)
            res = self.simulate_course(segments, power_profile)
            
            is_feasible = res.is_success
            if is_feasible:
                limit_watts = self._get_fatigue_adjusted_limit(res.total_time_sec)
                if res.normalized_power > limit_watts * 1.01:
                    is_feasible = False
            
            if is_feasible:
                best_result = res
                low_p = mid_p
            else:
                high_p = mid_p
                
        return best_result if best_result else self.simulate_course(segments, [150.0]*len(segments))

    def solve_lagrange_optimizer(self, segments: List[Segment], target_joules: float, max_power_limit: float) -> List[float]:
        # [CRITICAL] Extremely broad lambda range to capture very high and very low efficiency segments.
        # low_lambda -1000.0 means we are willing to spend 1 Joule to save 1000 seconds (very cheap).
        # high_lambda -1e-12 means we barely save any time (very expensive).
        low_lambda, high_lambda = -1000.0, -1e-12
        best_powers = []
        
        for _ in range(30): # Increased precision
            mid_lambda = (low_lambda + high_lambda) / 2.0
            current_powers = []
            est_energy = 0.0
            
            for seg in segments:
                p = self._find_power_for_lambda(seg, mid_lambda, max_power_limit)
                current_powers.append(p)
                v = self._solve_equilibrium_speed(seg, p)
                est_energy += p * (seg.length / v if v > 0.1 else seg.length / 0.1)
                
            if est_energy > target_joules:
                # Used too much energy -> need more negative lambda (more efficient watts only)
                high_lambda = mid_lambda
            else:
                # Energy left -> can afford less efficient watts -> higher (closer to 0) lambda
                low_lambda = mid_lambda
                best_powers = current_powers
        return best_powers

    def _find_power_for_lambda(self, seg: Segment, target_lambda: float, max_limit: float) -> float:
        # Minimal power just to keep moving, no arbitrary 150W floor.
        p_min = self._calculate_min_power_for_speed(seg, 4.0)
        low_p, high_p = p_min, max_limit
        
        for _ in range(15):
            mid_p = (low_p + high_p) / 2.0
            v1 = self._solve_equilibrium_speed(seg, mid_p)
            v2 = self._solve_equilibrium_speed(seg, mid_p + 0.1)
            
            t1, t2 = seg.length / v1, seg.length / v2
            w1 = mid_p * (seg.length / v1)
            w2 = (mid_p + 0.1) * (seg.length / v2)
            
            # Use dt/dW (Time saved per Joule) as the true economic gradient
            grad = (t2 - t1) / (w2 - w1) if (w2 - w1) != 0 else 0
            
            if grad < target_lambda: 
                low_p = mid_p
            else:
                high_p = mid_p
        return (low_p + high_p) / 2.0

    def _calculate_min_power_for_speed(self, seg: Segment, speed_kmh: float) -> float:
        v = speed_kmh / 3.6
        total_mass = self.rider.weight + self.params.bike_weight
        theta = math.atan(seg.grade)
        f_resist = total_mass * 9.81 * (math.sin(theta) + self.params.crr * math.cos(theta)) + 0.5 * 1.225 * self.params.cda * v**2
        return max(5.0, f_resist * v / (1 - self.params.drivetrain_loss))

    def _solve_equilibrium_speed(self, seg: Segment, power: float) -> float:
        p_wheel = power * (1 - self.params.drivetrain_loss)
        total_mass, g = self.rider.weight + self.params.bike_weight, 9.81
        theta = math.atan(seg.grade)
        f_static = total_mass * g * (math.sin(theta) + self.params.crr * math.cos(theta))
        low_v, high_v = 0.1, 45.0
        for _ in range(15):
            mid_v = (low_v + high_v) / 2.0
            if (0.5 * 1.225 * self.params.cda * mid_v**2 + f_static) * mid_v < p_wheel:
                low_v = mid_v
            else:
                high_v = mid_v
        return (low_v + high_v) / 2.0

    def simulate_course(self, segments: List[Segment], power_profile: List[float]) -> SimulationResult:
        self.rider.reset_state()
        total_time, total_work, weighted_power_sum = 0.0, 0.0, 0.0
        v_current = 0.1
        track_data = []
        for i, seg in enumerate(segments):
            p_target = power_profile[i] if i < len(power_profile) else 150.0
            v_next, time_sec, _, p_actual = self._solve_segment_physics(seg, p_target, v_current, 0)
            self.rider.update_w_prime(p_actual, time_sec)
            if self.rider.is_bonked(): return SimulationResult(total_time, 0, 0, 0, 0, 0, -1, False, "BONK")
            total_time += time_sec
            total_work += p_actual * time_sec
            weighted_power_sum += (p_actual ** 4) * time_sec
            track_data.append({"dist_km": seg.end_dist/1000, "ele": seg.end_ele, "grade_pct": seg.grade*100, "speed_kmh": v_next*3.6, "power": p_actual, "time_sec": total_time})
            v_current = v_next
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        avg_spd = (sum(s.length for s in segments)/1000 * 3600) / total_time if total_time > 0 else 0
        return SimulationResult(total_time, 0, avg_spd, avg_p, np, total_work/1000, 0, True, track_data=track_data)

    def _solve_segment_physics(self, seg: Segment, p_target: float, v_entry: float, v_wind: float) -> Tuple[float, float, bool, float]:
        g, total_mass = 9.81, self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        d = max(0.1, seg.length)
        f_gravity = total_mass * g * seg.grade
        f_roll = total_mass * g * self.params.crr
        p_wheel = p_target * (1 - self.params.drivetrain_loss)
        v_curr = v_entry
        low, high = 0.01, 45.0
        for _ in range(15):
            mid_v = (low + high) / 2.0
            v_avg = max(0.1, (v_curr + mid_v) / 2.0)
            f_aero = 0.5 * 1.225 * eff_cda * (v_avg + v_wind) * abs(v_avg + v_wind)
            work_net = (p_wheel/v_avg - f_aero - f_gravity - f_roll) * d
            if 0.5 * total_mass * (v_curr**2) + work_net > 0.5 * total_mass * (mid_v**2): low = mid_v
            else: high = mid_v
        v_final = max(0.5, (low + high) / 2.0)
        return v_final, d/((v_curr+v_final)/2), False, p_target

    def _get_fatigue_adjusted_limit(self, duration_sec: float) -> float:
        sorted_pdc = sorted([(int(k), v) for k, v in self.rider.pdc.items()])
        if not sorted_pdc: return self.rider.cp
        max_pdc_time, max_pdc_watts = sorted_pdc[-1]
        if duration_sec > max_pdc_time: return max_pdc_watts * (duration_sec / max_pdc_time) ** -0.10
        return self.rider.get_pdc_power(duration_sec)
