from __future__ import annotations
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.rider import Rider
from src.gpx_loader import Segment
from src.weather_client import WeatherClient
from src.physics_engine_v2 import PhysicsParams, SimulationResult

class PhysicsEngineV3:
    """
    Physics Engine V3: Optimal Control (Dahmen's Algorithm)
    - Implementation strictly following docs/todo/fix_strategy.txt
    """
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client

    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        """
        Finds the fastest pacing strategy.
        Outer Loop: Binary Search for maximum sustainable Average Power.
        """
        # Binary Search on POWER (Watts), not arbitrary Energy
        low_p = 50.0
        high_p = self.rider.cp * 1.5 
        
        best_result: Optional[SimulationResult] = None
        
        for i in range(12):
            mid_p = (low_p + high_p) / 2.0
            
            # 1. Determine Energy Budget for this Power Level
            flat_profile = [mid_p] * len(segments)
            base_res = self.simulate_course(segments, flat_profile)
            
            # [FIXED] If flat pacing already fails, this power is too high.
            if not base_res.is_success:
                high_p = mid_p
                # print(f"[DEBUG] Step {i}: mid_p={mid_p:.1f}W, feasible=False, reason=Baseline BONK")
                continue

            total_energy_budget = base_res.work_kj * 1000.0
            
            # 2. Run Dahmen Optimizer
            power_profile = self.solve_dahmen_optimizer(
                segments, 
                total_energy_budget=total_energy_budget,
                max_power_limit=self.rider.cp * 3.0
            )
            
            # 3. Simulate with optimized profile
            res = self.simulate_course(segments, power_profile)
            
            # 4. Feasibility Check
            is_feasible = res.is_success
            fail_reason = ""
            if not res.is_success:
                fail_reason = "BONK"
            
            if is_feasible:
                limit_watts = self._get_fatigue_adjusted_limit(res.total_time_sec)
                if res.normalized_power > limit_watts:
                    is_feasible = False
                    fail_reason = f"NP Too High ({res.normalized_power:.1f} > {limit_watts:.1f})"
            
            # print(f"[DEBUG] Step {i}: mid_p={mid_p:.1f}W, feasible={is_feasible}, reason={fail_reason}")
            
            if is_feasible:
                best_result = res
                low_p = mid_p
            else:
                high_p = mid_p
                
        return best_result if best_result else self.simulate_course(segments, [150.0]*len(segments))

    def solve_dahmen_optimizer(self, segments: List[Segment], total_energy_budget: float, max_power_limit: float) -> List[float]:
        """
        [Dahmen Optimal Control Solver]
        EXACTLY AS WRITTEN IN docs/todo/fix_strategy.txt (Step 3)
        with minor initialization stability fix.
        """
        # 1. 초기화: Warm Start based on Gradient
        # Flat initialization takes too long to converge to a polarized strategy.
        # We start with a rough guess: Power ~ Gradient
        est_time = sum(s.length for s in segments) / 8.33
        avg_power_target = total_energy_budget / est_time if est_time > 0 else 250.0
        
        powers = []
        for seg in segments:
            # Heuristic guess: P = P_avg * (1 + 2.0 * grade)
            # This mimics V2's logic to give the optimizer a head start.
            guess = avg_power_target * (1.0 + 2.0 * seg.grade)
            guess = max(50.0, min(guess, max_power_limit)) # Clip for safety
            powers.append(guess)
        
        # [TUNING] Convergence parameters
        # Learning Rate 30.0: Aggressive enough to pace, conservative enough to avoid instant Bonk.
        # Iterations 200: Give it time to settle.
        learning_rate = 30.0  
        iterations = 200
        
        for k in range(iterations):
            gradients = [] # 각 구간별 dt/dP (1W당 시간 단축량)
            current_total_energy = 0.0
            
            # 2. 기울기(Gradient) 계산 루프
            v_curr = 0.1
            for i, seg in enumerate(segments):
                p = powers[i]
                
                # 현재 파워일 때 시간 (T_base)
                v_next_base, t_base, _, _ = self._solve_segment_physics(seg, p, v_curr, 0)
                
                # 미세 파워 증가 시 시간 (T_delta) -> 수치 미분
                delta = 0.5 
                v_next_delta, t_delta, _, _ = self._solve_segment_physics(seg, p + delta, v_curr, 0)
                
                # 기울기 (음수 값)
                grad = (t_delta - t_base) / delta
                gradients.append(grad)
                
                current_total_energy += p * t_base
                v_curr = v_next_base 

            # 3. 파워 업데이트 (Greedy Update)
            avg_grad = sum(gradients) / len(gradients)
            
            total_mass = self.rider.weight + self.params.bike_weight
            g = 9.81
            min_v_ms = 5.0 / 3.6 # 최소 유지 속도 5km/h
            crr = self.params.crr
            loss = self.params.drivetrain_loss

            for i in range(len(powers)):
                diff = gradients[i] - avg_grad
                change = -diff * learning_rate 
                
                powers[i] += change
                
                # [PHYSICAL CONSTRAINT - REFINED] 
                # P_min = (F_gravity + F_roll) * v / efficiency
                # This ensures we actually have enough power to move at min_v_ms
                seg = segments[i]
                theta = math.atan(seg.grade)
                f_grav = total_mass * g * math.sin(theta)
                f_roll = total_mass * g * crr * math.cos(theta)
                
                # F_aero is negligible at 5km/h but let's be thorough
                # f_aero = 0.5 * rho * cda * v^2
                
                f_resist = f_grav + f_roll
                
                # If grade is negative, f_resist can be negative (gravity helps).
                # But we only constrain positive power.
                if f_resist > 0:
                    p_wheel_min = f_resist * min_v_ms
                    p_min_physical = p_wheel_min / (1 - loss)
                else:
                    p_min_physical = 0.0
                
                # Ensure we don't set a tiny power that causes stall
                p_min_physical = max(p_min_physical, 20.0)
                
                powers[i] = max(p_min_physical, min(powers[i], max_power_limit))
                
            # 5. 총 에너지 예산 맞추기 (Normalization)
            if current_total_energy > 0:
                scale = total_energy_budget / current_total_energy
                powers = [p * scale for p in powers]
                
        return powers

    def simulate_course(self, segments: List[Segment], power_profile: List[float]) -> SimulationResult:
        """
        Dahmen 알고리즘용 시뮬레이터:
        EXACTLY AS WRITTEN IN docs/todo/fix_strategy.txt (Step 2)
        """
        self.rider.reset_state()
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 0.1
        min_w_prime = self.rider.w_prime_max
        track_data = []

        for i, seg in enumerate(segments):
            p_target = power_profile[i] # 규칙 계산 대신, 할당된 파워 사용
            
            # 물리 연산 실행
            v_next, time_sec, is_walking, p_actual = self._solve_segment_physics(seg, p_target, v_current, 0)
            
            self.rider.update_w_prime(p_actual, time_sec)
            if self.rider.is_bonked():
                return SimulationResult(total_time, 0, 0, 0, 0, 0, -1, False, "BONK")

            total_time += time_sec
            total_work += p_actual * time_sec
            weighted_power_sum += (p_actual ** 4) * time_sec
            v_current = v_next
            
            track_data.append({
                "dist_km": seg.end_dist / 1000.0,
                "ele": seg.end_ele,
                "grade_pct": seg.grade * 100, # Added grade_pct
                "speed_kmh": v_current * 3.6,
                "power": p_actual,
                "time_sec": total_time
            })
            
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        avg_spd = (sum(s.length for s in segments)/1000.0 * 3600) / total_time if total_time > 0 else 0
        
        return SimulationResult(total_time, 0, avg_spd, avg_p, np, total_work/1000, 0, True, track_data=track_data)

    def _solve_segment_physics(self, seg: Segment, p_target: float, v_entry: float, v_wind: float) -> Tuple[float, float, bool, float]:
        """
        Reusing the core physics logic from V2 to perform the actual calculations.
        """
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        
        d = seg.length
        if d < 0.1: d = 0.1
        
        f_gravity = total_mass * g * seg.grade
        f_roll = total_mass * g * self.params.crr
        p_wheel = p_target * (1 - self.params.drivetrain_loss)
        
        v_curr = v_entry
        low = 0.01
        high = 40.0 
        
        for _ in range(10):
            mid_v = (low + high) / 2
            v_avg = (v_curr + mid_v) / 2
            if v_avg < 0.1: v_avg = 0.1
            
            t_est = d / v_avg
            v_air = v_avg + v_wind
            f_aero = 0.5 * self.params.air_density * eff_cda * (v_air * abs(v_air))
            
            w_pedal = p_wheel * t_est
            w_resist = (f_aero + f_gravity + f_roll) * d
            
            ke_initial = 0.5 * total_mass * (v_curr**2)
            ke_final_target = 0.5 * total_mass * (mid_v**2)
            
            if (ke_initial + w_pedal - w_resist) > ke_final_target:
                low = mid_v 
            else:
                high = mid_v 
                
        v_final = (low + high) / 2
        v_final = max(0.5, v_final)
        v_avg_final = (v_curr + v_final) / 2
        t_final = d / v_avg_final
        
        return v_final, t_final, False, p_target

    def _get_fatigue_adjusted_limit(self, duration_sec: float) -> float:
        sorted_pdc = sorted([(int(k), v) for k, v in self.rider.pdc.items()])
        if not sorted_pdc: return self.rider.cp
        max_pdc_time, max_pdc_watts = sorted_pdc[-1]
        if duration_sec > max_pdc_time:
            riegel_exponent = -0.10 
            return max_pdc_watts * (duration_sec / max_pdc_time) ** riegel_exponent
        return self.rider.get_pdc_power(duration_sec)
