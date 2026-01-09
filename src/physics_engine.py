from __future__ import annotations

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.rider import Rider
from src.gpx_loader import Segment
from src.weather_client import WeatherClient

@dataclass
class PhysicsParams:
    cda: float = 0.32
    crr: float = 0.004
    bike_weight: float = 8.0  # kg
    drivetrain_loss: float = 0.03  # 3% loss
    air_density: float = 1.225
    drafting_factor: float = 0.0 # 0.0 ~ 0.5 (30% = 0.3)

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
        
        # Pacing Config
        self.alpha_climb = 2.0  # Aggressiveness on climbs
        self.alpha_descent = 5.0 # Conservativeness on descents
    
    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        """
        Solver: Find the fastest feasible pacing strategy (P_base) using Binary Search.
        """
        # Determine Safety Cap based on rough duration estimation
        total_dist_km = sum(s.length for s in segments) / 1000.0
        est_hours = total_dist_km / 25.0 # Slightly more conservative
        max_cap_factor = self.rider.get_dynamic_max_cap(est_hours)
        
        # 1. Riegel's Fatigue Model Calculation
        # Limit average power based on duration.
        # P_limit = CP * (1 / T_hours)^0.07 (Fatigue Factor k=0.07 for cycling)
        fatigue_exponent = 0.07
        if est_hours > 1.0:
            power_decay_factor = (1.0 / est_hours) ** fatigue_exponent
        else:
            power_decay_factor = 1.0
            
        riegel_limit = self.rider.cp * power_decay_factor
        
        print(f"[Solver] Est. Duration: {est_hours:.1f}h")
        print(f"[Solver] Riegel Limit: {riegel_limit:.0f}W (Factor: {power_decay_factor:.2f})")
        print(f"[Solver] Safety Cap: {max_cap_factor:.2f}x CP (Peak Power Limit)")

        # Search Range: 0 to Riegel Limit (Realistic Endurance Power)
        # We search for the highest sustainable BASE power within physiological limits.
        low = 0.0
        high = riegel_limit
        
        best_result: Optional[SimulationResult] = None

        # Binary Search (Max Iterations: 15)
        for i in range(15):
            mid = (low + high) / 2
            
            # Run Simulation
            res = self.simulate_course(segments, p_base=mid, max_cap_factor=max_cap_factor)
            
            if res.is_success:
                best_result = res
                low = mid
            else:
                high = mid
            
            # Tolerance Check
            if high - low < 1.0: # 1 Watt precision
                break
                
        if best_result:
            return best_result
        else:
            # If even 0W fails (impossible), return the lowest attempt
            return self.simulate_course(segments, p_base=0.0, max_cap_factor=1.0)

    def simulate_course(self, segments: List[Segment], p_base: float, max_cap_factor: float) -> SimulationResult:
        """
        Run a single simulation pass with a specific Base Power.
        """
        self.rider.reset_state()
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        
        v_current = 0.0 # Initial velocity (m/s)
        min_w_prime = self.rider.w_prime_max
        
        max_power_limit = self.rider.cp * max_cap_factor

        # Pre-fetch weather if possible (using first point for now)
        # Ideally this should be per-segment if weather varies spatially
        # For Phase 1, we assume global constant weather vector from input
        # or fetched once. We'll use a placeholder for now.
        wind_speed_global = 0.0
        wind_deg_global = 0.0
        
        # If WeatherClient is available and has scenario data or last fetch
        if self.weather and self.weather.use_scenario_mode:
             d = self.weather._get_scenario_weather()
             wind_speed_global = d['wind_speed']
             wind_deg_global = d['wind_deg']

        for seg in segments:
            # 1. Determine Target Power (Pacing Strategy)
            p_target = self._calculate_target_power(p_base, seg.grade, max_power_limit)
            
            # 2. Vector Wind Calculation
            # Effective Wind = V_wind * cos(WindDir - RoadHeading)
            # Be careful with angle units (Degrees to Radians)
            # Wind Direction: From where it blows (Meteorological) -> Need to convert to vector direction
            # Actually: Wind Vector is pointing TO (WindDeg + 180)
            # Simply: Relative Angle = |WindDeg - RoadHeading|
            # Headwind Component = V_wind * cos(RelativeAngle) -> If wind is from front (0 deg diff), cos(0)=1 (Headwind)
            # Wait, Wind Direction 0 means North Wind (Blows FROM North to South).
            # If I ride North (Heading 0), I face the wind.
            # So if |Wind - Heading| = 0, it is Headwind.
            
            rel_angle_rad = math.radians(wind_deg_global - seg.heading)
            # If wind from North (0), Heading North (0) -> cos(0) = 1 (Positive Headwind) -> Correct.
            v_headwind_env = wind_speed_global * math.cos(rel_angle_rad)

            # 3. Calculate Velocity (Physics)
            # v_current is passed as v_entry (Inertia)
            v_next, time_sec = self._solve_segment_physics(seg, p_target, v_current, v_headwind_env)
            
            # 4. Physiology Update (Skiba)
            self.rider.update_w_prime(p_target, time_sec)
            
            # 5. Check Bonk
            if self.rider.is_bonked():
                return SimulationResult(
                    total_time_sec=0, base_power=p_base, average_speed_kmh=0,
                    average_power=0, normalized_power=0, work_kj=0,
                    w_prime_min=-1, is_success=False, fail_reason="BONK"
                )

            # Accumulate Stats
            total_time += time_sec
            total_work += p_target * time_sec
            weighted_power_sum += (p_target ** 4) * time_sec
            
            min_w_prime = min(min_w_prime, self.rider.w_prime_bal)
            v_current = v_next # Carry over velocity
            
        # Success
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        dist_km = sum(s.length for s in segments) / 1000.0
        avg_spd = (dist_km * 3600) / total_time if total_time > 0 else 0
        
        return SimulationResult(
            total_time_sec=total_time,
            base_power=p_base,
            average_speed_kmh=avg_spd,
            average_power=avg_p,
            normalized_power=np,
            work_kj=total_work/1000,
            w_prime_min=min_w_prime,
            is_success=True
        )

    def _calculate_target_power(self, p_base: float, grade: float, max_limit: float) -> float:
        """Apply Pacing Strategy."""
        if grade > 0:
            # Uphill: Aggressive
            p = p_base * (1 + self.alpha_climb * grade)
            return min(p, max_limit) # Safety Cap
        
        elif grade > -0.02: # -2% to 0% (Flat/False Flat)
            # Aerodynamic efficiency is still okay, keep pushing
            return p_base * 0.9
            
        elif grade > -0.04: # -4% to -2% (Moderate descent)
            # Light pedaling for speed maintenance and active recovery
            return p_base * 0.4
            
        else: # Steep Downhill (< -4%)
            # Recovery / Coasting
            return 0.0

    def _solve_segment_physics(self, seg: Segment, power: float, v_entry: float, v_wind: float) -> Tuple[float, float]:
        """
        Calculate velocity using Work-Energy Principle (Predictor-Corrector).
        Correctly handles Gravity Assist on downhills and Inertia on climbs.
        """
        # 1. Constants & Forces Setup
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight + 1.0
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        p_avail = power * (1 - self.params.drivetrain_loss)
        
        f_gravity = total_mass * g * seg.grade
        f_roll = total_mass * g * self.params.crr
        
        # Work-Energy: 0.5*m*v_f^2 = 0.5*m*v_i^2 + (F_net * d)
        # F_net = F_pedal - F_drag - F_gravity - F_roll
        # F_pedal * d = Work_pedal = P * t = P * (d / v_avg)
        
        # Iteration to solve for v_final
        v_curr = max(0.5, v_entry) # Avoid zero
        
        for _ in range(3): # 3 iterations is usually enough for convergence
            # Average Velocity Guess
            v_avg = (v_entry + v_curr) / 2
            
            # Aero Drag at Average Velocity
            v_air = v_avg + v_wind
            f_drag = 0.5 * self.params.air_density * eff_cda * (v_air ** 2) * (1 if v_air > 0 else -1)
            
            # Pedal Force (Effective)
            # Power = Force * Velocity => Force = Power / Velocity
            if v_avg > 0.1:
                f_pedal = p_avail / v_avg
            else:
                f_pedal = p_avail / 0.1 # Cap force at low speed
                
            f_net = f_pedal - f_drag - f_gravity - f_roll
            
            # Calculate new velocity from Kinetic Energy change
            # v_f^2 = v_i^2 + 2 * (F/m) * d
            energy_term = v_entry**2 + 2 * (f_net / total_mass) * seg.length
            
            if energy_term < 0:
                v_next = 0.5 # Stopped
            else:
                v_next = math.sqrt(energy_term)
                
            # Convergence check
            if abs(v_next - v_curr) < 0.05:
                v_curr = v_next
                break
            v_curr = v_next
            
        v_final = v_curr
        v_avg = (v_entry + v_final) / 2
        
        # Min speed clamp (3 km/h) to prevent infinite time on steep uphill bonks
        if v_avg < 0.8: v_avg = 0.8
        
        time_sec = seg.length / v_avg
        
        return v_final, time_sec

    def _solve_steady_state(self, seg: Segment, power: float, v_wind: float) -> Tuple[float, float]:
        """Fallback Newton-Raphson solver for low speeds."""
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        slope_force = total_mass * g * seg.grade
        roll_force = total_mass * g * self.params.crr
        p_avail = power * (1 - self.params.drivetrain_loss)
        
        v_target = 3.0 # Guess
        for _ in range(5):
            v_air = v_target + v_wind
            f_aero = 0.5 * self.params.air_density * eff_cda * (v_air ** 2) * (1 if v_air > 0 else -1)
            f_resist = slope_force + roll_force + f_aero
            val = f_resist * v_target - p_avail
            f_deriv = (f_resist) + v_target * (self.params.air_density * eff_cda * abs(v_air))
            
            if abs(f_deriv) < 1e-5: break
            v_next = v_target - val / f_deriv
            if abs(v_next - v_target) < 0.1:
                v_target = v_next
                break
            v_target = v_next
            
        v_final = max(0.1, v_target)
        time_sec = seg.length / v_final
        return v_final, time_sec
