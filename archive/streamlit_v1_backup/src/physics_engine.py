from __future__ import annotations

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.rider import Rider
from src.gpx_loader import Segment
from src.weather_client import WeatherClient

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

class PhysicsEngine:
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client
        self.alpha_climb = 2.0  
        self.alpha_descent = 5.0 
    
    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        total_dist_km = sum(s.length for s in segments) / 1000.0
        # Initial rough estimate for blending/fatigue
        est_hours = total_dist_km / 25.0 
        est_sec = est_hours * 3600

        # --- Dynamic Power Limit (PDC Blending) ---
        pdc_limit = self.rider.get_pdc_power(est_sec)
        
        fatigue_exponent = 0.07
        power_decay_factor = (1.0 / max(1.0, est_hours)) ** fatigue_exponent
        riegel_limit = self.rider.cp * power_decay_factor

        # Blending Factor alpha: 1.0 (Short) -> 0.0 (Long)
        if est_sec <= 1200: # 20 min
            alpha = 1.0
        elif est_sec >= 7200: # 2 hours
            alpha = 0.0
        else:
            # Linear transition between 20min and 2hours
            alpha = 1.0 - (est_sec - 1200) / (7200 - 1200)
            # Apply steeper curve for faster drop near 1 hour
            alpha = alpha ** 1.5 

        # Final Cap used for P_target calculations
        max_power_limit = alpha * pdc_limit + (1.0 - alpha) * riegel_limit * 1.2
        
        print(f"[Solver] Est. Duration: {est_hours:.1f}h (Alpha: {alpha:.2f})")
        print(f"[Solver] PDC Limit: {pdc_limit:.0f}W, Riegel: {riegel_limit:.0f}W")
        print(f"[Solver] Final P_limit: {max_power_limit:.0f}W")
        
        low = 0.0
        # Dynamic Search Range: Blend PDC (Short) and Riegel (Long)
        high = alpha * pdc_limit + (1.0 - alpha) * riegel_limit
        
        print(f"[Solver] Search Range High: {high:.0f}W")
        
        best_result: Optional[SimulationResult] = None

        for i in range(15):
            mid = (low + high) / 2
            res = self.simulate_course(segments, p_base=mid, max_power_limit=max_power_limit)
            if res.is_success:
                best_result = res
                low = mid
            else:
                high = mid
            if high - low < 1.0: break
                
        return best_result if best_result else self.simulate_course(segments, 0, 100.0) # Fallback

    def simulate_course(self, segments: List[Segment], p_base: float, max_power_limit: float) -> SimulationResult:
        self.rider.reset_state()
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 20.0 / 3.6 # Rolling start at 20km/h
        min_w_prime = self.rider.w_prime_max
        # No longer using internal rider.max_cap, using solver-provided limit

    def simulate_course(self, segments: List[Segment], p_base: float, max_power_limit: float) -> SimulationResult:
        self.rider.reset_state()
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 20.0 / 3.6 # Rolling start at 20km/h
        min_w_prime = self.rider.w_prime_max

        wind_speed_global = 0.0
        wind_deg_global = 0.0
        if self.weather and self.weather.use_scenario_mode:
             d = self.weather._get_scenario_weather()
             wind_speed_global = d['wind_speed']
             wind_deg_global = d['wind_deg']

        # Pre-calc Initial Max Force (Biomechanical Limit: 1.5G)
        f_max_initial = self.rider.weight * 9.81 * 1.5
        prev_heading = segments[0].heading

        for seg in segments:
            # --- Cornering Speed Limit Logic ---
            heading_change = abs(seg.heading - prev_heading)
            if heading_change > 180: heading_change = 360 - heading_change
            
            # Physics-based Cornering Limit: V = sqrt(mu * g * R)
            if seg.length > 0 and heading_change > 1.0: # Ignore micro-jitters (< 1 deg)
                # 1. Calculate Radius (R)
                # curvature (rad/m) = delta_theta (rad) / arc_length (m)
                # R = 1 / curvature
                theta_rad = math.radians(heading_change)
                curvature_rad = theta_rad / seg.length
                
                if curvature_rad > 0.0001:
                    radius = 1.0 / curvature_rad
                    
                    # 2. Limit Speed
                    # mu = 0.8 (Tire Grip + Banking), g = 9.81
                    # V_max = sqrt(0.8 * 9.81 * R)
                    # Safety Clamp: Min Radius 5m (Switchback) -> V ~ 22km/h
                    mu = 0.8
                    g = 9.81
                    v_corner_limit = math.sqrt(mu * g * radius)
                    
                    v_current = min(v_current, v_corner_limit) # SAFEGUARD ENABLED
            
            prev_heading = seg.heading
            # ----------------------------------
            p_target = self._calculate_target_power(p_base, seg.grade, max_power_limit)
            rel_angle_rad = math.radians(wind_deg_global - seg.heading)
            v_headwind_env = wind_speed_global * math.cos(rel_angle_rad)
            
            # Dynamic Torque Decay (Fatigue)
            decay_factor = 1.0
            if total_time > 3600: # After 1 hour
                decay_factor = (3600.0 / total_time) ** 0.07
            
            current_f_limit = f_max_initial * decay_factor
            
            v_next, time_sec = self._solve_segment_physics(seg, p_target, v_current, v_headwind_env, f_limit=current_f_limit)
            self.rider.update_w_prime(p_target, time_sec)
            
            if self.rider.is_bonked():
                return SimulationResult(0, p_base, 0, 0, 0, 0, -1, False, "BONK")

            total_time += time_sec
            total_work += p_target * time_sec
            weighted_power_sum += (p_target ** 4) * time_sec
            min_w_prime = min(min_w_prime, self.rider.w_prime_bal)
            v_current = v_next 
            
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        dist_km = sum(s.length for s in segments) / 1000.0
        avg_spd = (dist_km * 3600) / total_time if total_time > 0 else 0
        
        return SimulationResult(total_time, p_base, avg_spd, avg_p, np, total_work/1000, min_w_prime, True)

    def _calculate_target_power(self, p_base: float, grade: float, max_limit: float) -> float:
        if grade > 0:
            return min(p_base * (1 + self.alpha_climb * grade), max_limit)
        elif grade > -0.02: 
            return p_base * 0.9
        elif grade > -0.04: 
            return p_base * 0.4
        else: 
            return 0.0

    def _solve_segment_physics(self, seg: Segment, power: float, v_entry: float, v_wind: float, f_limit: float) -> Tuple[float, float]:
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight + 1.0
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        p_avail = power * (1 - self.params.drivetrain_loss)
        
        f_gravity = total_mass * g * seg.grade
        f_roll = total_mass * g * self.params.crr
        
        chunk_size = 20.0
        num_chunks = max(1, math.ceil(seg.length / chunk_size))
        d_sub = seg.length / num_chunks
        
        v_current = v_entry
        t_total = 0.0
        
        for _ in range(num_chunks):
            # Bisection Method: Solve for v_next using energy balance
            # Range: 0.01 m/s (~0.04 km/h) to 50.0 m/s (180 km/h)
            # Precision: 20 iterations provide < 0.0002 km/h error margin
            # [CRITICAL: DO NOT MODIFY RANGE OR ITERATIONS WITHOUT USER CONSENT]
            low = 0.01
            high = 50.0
            v_next = v_current # Default fallback
            
            for _i in range(20):
                if (high - low) < 0.001: break # Early exit at 0.0036 km/h precision
                
                mid = (low + high) / 2
                v_avg = (v_current + mid) / 2
                
                # Forces at v_avg
                # Note: No artificial clamps here, pure physics
                # f_pedal = P / v, f_drag = C * v^2
                if v_avg < 0.1: v_avg = 0.1 # Avoid div by zero
                
                f_pedal = p_avail / v_avg # Apply drivetrain loss (p_avail)
                # Air drag direction matches velocity (always positive here as we assume forward motion)
                f_drag = 0.5 * self.params.air_density * eff_cda * (v_avg ** 2)
                
                f_net = f_pedal - f_drag - f_gravity - f_roll
                
                # Energy Balance: E_final - E_initial = Work_net
                # 0.5*m*v_next^2 - 0.5*m*v_curr^2 = F_net * d
                
                # We want to check if 'mid' is feasible as v_next.
                # Work Done by Net Force
                work_net = f_net * d_sub
                
                # Required Final Kinetic Energy
                ke_final_required = 0.5 * total_mass * (mid ** 2)
                ke_initial = 0.5 * total_mass * (v_current ** 2)
                
                # Balance Error
                # If (Initial KE + Work) > Required KE, we have excess energy -> Speed up
                energy_available = ke_initial + work_net
                
                if energy_available > ke_final_required:
                    low = mid # Can go faster
                else:
                    high = mid # Need to slow down
            
            v_next = (low + high) / 2
            v_avg_final = (v_current + v_next) / 2
            if v_avg_final < 0.1: v_avg_final = 0.1
            
            t_total += d_sub / v_avg_final
            v_current = v_next
            
        return v_current, t_total