from __future__ import annotations
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.core.rider import Rider
from src.core.gpx_loader import Segment
from src.weather_client import WeatherClient
from src.engines.v2 import PhysicsParams, SimulationResult

class PhysicsEngineV5:
    """
    Physics Engine V5: Iterative Gradient Descent with Smoothing
    - Solves the Optimal Control problem by iteratively refining the power profile.
    - Decouples Inertia (Simulation) from Optimization (Local Probe).
    - Uses Alpha Smoothing to prevent oscillation and ensure convergence.
    """
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client

    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        """
        [Corrected Logic] Watt-Based Convergence
        시간 예측이나 총 에너지 예산에 의존하지 않고,
        '목표 파워(Target Watts)'를 직접 조절하여 수렴시킵니다.
        """
        
        # 1. 초기 설정: 안전하게 FTP의 70% 정도로 시작
        # (너무 낮게 시작해서 올려가는 것이 Bonk를 피하는 지름길)
        target_watts = self.rider.cp * 0.7 
        
        best_result = None
        best_time = float('inf')
        
        print(f"DEBUG: Starting Optimization Loop with Target: {target_watts:.1f}W")

        for i in range(15):
            # A. 목표 예산 설정 (Dynamic Budgeting)
            # "이 코스를 target_watts로 달리면 대충 몇 kJ이 필요한가?"를 역산
            # 거리 / (대략적 속도) = 시간
            # 시간 * target_watts = 예산
            # 속도 추정은 루프가 돌면서 시뮬레이션 결과값으로 보정됨.
            
            if best_result:
                # 이전 기록이 있으면 그 속도 기반으로 정교하게 계산
                est_time = best_result.total_time_sec
            else:
                # 첫 시도면 대충 평지 기준 추정
                total_dist = sum(s.length for s in segments)
                est_time = total_dist / 9.0 # 약 32km/h
            
            target_joules = target_watts * est_time
            
            # B. [Optimizer] 예산 배분
            # 상한선(Max Limit)은 목표 파워보다 여유 있게(1.5배) 주어 오르막 인터벌 허용
            power_profile = self.solve_pacing_final(segments, target_joules, target_watts * 1.5)
            
            # C. [Simulation] 검증
            sim_res = self.simulate_course(segments, power_profile)
            
            # D. 결과 분석 및 피드백 (핵심!)
            if not sim_res.is_success:
                # 실패(Bonk) -> "목표 파워가 너무 높다" -> 낮춰라!
                # 절대 시간을 늘리는 멍청한 짓을 하지 않음.
                old_target = target_watts
                target_watts *= 0.90 # 10% 삭감
                print(f"DEBUG: Iter {i} | {old_target:.1f}W -> BONK. Lowering to {target_watts:.1f}W")
                
                # 혹시라도 best_result가 있다면 그것도 초기화 (너무 센 설정이었으므로)
                # best_result = None 
                
            else:
                # 성공 -> "더 밟을 수 있나?" 확인 (PDC 모델 대조)
                real_time = sim_res.total_time_sec
                real_avg_p = sim_res.average_power
                
                # 현재 기록(real_time) 동안 내가 낼 수 있는 최대 파워(Limit)
                limit_watts = self._get_fatigue_adjusted_limit(real_time)
                
                print(f"DEBUG: Iter {i} | Result: {real_time/60:.2f}min @ {real_avg_p:.1f}W (Limit: {limit_watts:.1f}W)")
                
                # 수렴 조건: 실제 파워가 한계 파워의 98% 이상이면 최선이라고 판단
                if real_avg_p >= limit_watts * 0.98:
                    if real_time < best_time:
                        best_result = sim_res
                        best_time = real_time
                    print("DEBUG: Converged! Reached physiological limit.")
                    break
                
                # 아직 여유 있음 (Limit > Real) -> 파워를 올리자!
                # 단순하게 올리지 않고, (현재 + 한계) / 2 로 부드럽게 접근
                next_target = (target_watts + limit_watts) / 2.0
                
                # 진동 방지: 이미 베스트 기록 근처라면 미세 조정
                if abs(next_target - target_watts) < 2.0:
                    print("DEBUG: Converged (Power delta too small).")
                    best_result = sim_res
                    break
                    
                target_watts = next_target
                
                # 기록 갱신
                if real_time < best_time:
                    best_result = sim_res
                    best_time = real_time

        return best_result if best_result else self.simulate_course(segments, [150.0]*len(segments))

    def solve_pacing_final(self, segments: List[Segment], target_joules: float, max_limit: float) -> List[float]:
        """
        [Iterative Gradient Descent with Smoothing]
        1. Forward Simulation (Get Inertia)
        2. Local Optimization (Find P_ideal for Lambda)
        3. Update with Smoothing (P_next = (1-a)P + a*P_ideal)
        """
        # [수정] 초기값을 'Target Watts'로 설정하여 시작부터 공격적으로 배분 유도
        est_time = sum(s.length for s in segments) / 10.0 # 대략 10m/s 가정
        avg_target_power = target_joules / est_time
        
        # 만약 계산된 파워가 너무 낮으면(오류 방지), 최소 200W 이상으로 강제 시작
        start_watts = max(avg_target_power, 200.0)
        current_powers = [start_watts] * len(segments)
        
        # Parameters
        alpha = 0.2  # Smoothing Factor (Conservative)
        iterations = 30
        
        # Outer Loop: Optimize Lambda to match Energy Budget
        low_lambda, high_lambda = -20.0, -1e-10
        
        # To save computation, we do a nested approach:
        # We need to find ONE lambda that works for the converged profile.
        # But profile changes as lambda changes.
        # Strategy: Inside the Iterative Loop, we adjust Lambda dynamically to match budget.
        
        current_lambda = -0.5 # Start guess
        
        for _iter in range(iterations):
            # 1. Forward Simulation (Get v_in profile)
            sim_results = self._run_simulation_with_inertia(segments, current_powers)
            # sim_results[i] = v_in for segment i
            
            # 2. Find optimal Lambda for this fixed velocity profile
            # We want Sum(Energy(P_ideal)) = Target.
            # This is a sub-problem: Binary search for Lambda given FIXED v_in.
            target_lambda = self._find_lambda_for_budget(segments, target_joules, max_limit, sim_results)
            
            # 3. Calculate P_ideal and Update with Smoothing
            next_powers = []
            max_diff = 0.0
            
            for i, seg in enumerate(segments):
                v_in = sim_results[i]
                p_ideal = self._find_power_for_lambda(seg, target_lambda, max_limit, v_in)
                
                # Smoothing Update
                p_new = current_powers[i] + alpha * (p_ideal - current_powers[i])
                
                # Physical Constraint (Min Power for 4km/h) is handled inside _find_power...
                # But we apply it here again to be safe
                # p_new = max(self._calculate_min_power_for_speed(seg, 4.0), p_new)
                
                max_diff = max(max_diff, abs(p_new - current_powers[i]))
                next_powers.append(p_new)
            
            current_powers = next_powers
            
            if max_diff < 0.5: # Converged
                break
                
        return current_powers

    def _run_simulation_with_inertia(self, segments: List[Segment], powers: List[float]) -> List[float]:
        """
        Runs full physics simulation and returns list of v_in for each segment.
        """
        v_ins = []
        v_curr = 0.1
        
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        
        for i, seg in enumerate(segments):
            v_ins.append(v_curr)
            p = powers[i]
            
            # Solve segment physics (similar to simulate_course but simplified for speed)
            v_next, _, _, _ = self._solve_segment_physics(seg, p, v_curr, 0.0, 9999.0)
            v_curr = v_next
            
        return v_ins

    def _find_lambda_for_budget(self, segments: List[Segment], target_joules: float, max_limit: float, v_ins: List[float]) -> float:
        """
        [FIXED] Binary Search Direction Inverted
        Lambda 범위: -1000 (Very Strict, Save Energy) ~ -1e-9 (Very Generous, Spend Energy)
        """
        # 범위 설정: -1000 (효율충) ~ 0 (낭비충)
        low_l, high_l = -1000.0, -1e-9
        
        for _ in range(30): # 횟수 충분히
            mid_l = (low_l + high_l) / 2.0
            total_e = 0.0
            
            # 현재 Lambda(mid_l) 기준 파워 계산
            for i, seg in enumerate(segments):
                v_in = v_ins[i]
                p = self._find_power_for_lambda(seg, mid_l, max_limit, v_in)
                
                v_out = self._solve_segment_speed(seg, p, v_in)
                v_avg = (v_in + v_out) / 2.0
                if v_avg < 0.1: v_avg = 0.1
                t = seg.length / v_avg
                total_e += p * t
            
            # [핵심 수정 구간]
            if total_e > target_joules:
                # 예산 초과! -> 아껴 써야 함 -> 더 엄격한 쪽(-1000)으로
                high_l = mid_l 
            else:
                # 예산 남음! -> 펑펑 써야 함 -> 더 관대한 쪽(0)으로
                low_l = mid_l
                
        return (low_l + high_l) / 2.0

    def _find_power_for_lambda(self, seg: Segment, target_lambda: float, max_limit: float, v_in: float) -> float:
        """
        [FUNDAMENTAL FIX] Kinetic Energy Aware Gradient
        단순히 (시간/에너지)만 보는 게 아니라, '운동에너지의 변화'를 비용에 반영함.
        - 속도를 유지/가속하면: 운동에너지(KE)가 자산으로 남으므로 실질 비용을 깎아줌 -> 효율 높게 평가 -> 파워 유지
        - 속도를 감속하면: 운동에너지(KE)를 잃어버리므로 실질 비용에 페널티 부과 -> 효율 낮게 평가 -> 감속 지양
        """
        low_p, high_p = 0.0, max_limit # 0부터 시작해도 됨. 수학이 알아서 0을 거를 것임.
        
        total_mass = self.rider.weight + self.params.bike_weight
        
        # 반복 횟수 20회
        for _ in range(20):
            mid_p = (low_p + high_p) / 2.0
            h = 5.0 # 미분 간격을 좀 더 넓혀서 거시적인 변화를 보게 함
            
            # 1. P일 때
            v_out_1 = self._solve_segment_speed(seg, mid_p, v_in)
            v_avg_1 = (v_in + v_out_1) / 2.0
            t1 = seg.length / v_avg_1
            w_pedal_1 = mid_p * t1 # 내가 쓴 '생' 에너지
            
            # 운동에너지 변화량 (나중 - 처음)
            ke_change_1 = 0.5 * total_mass * (v_out_1**2 - v_in**2)
            
            # 2. P+h일 때
            v_out_2 = self._solve_segment_speed(seg, mid_p + h, v_in)
            v_avg_2 = (v_in + v_out_2) / 2.0
            t2 = seg.length / v_avg_2
            w_pedal_2 = (mid_p + h) * t2 
            
            ke_change_2 = 0.5 * total_mass * (v_out_2**2 - v_in**2)
            
            # [핵심] Gradient 계산 (Chain Rule 간소화)
            dt = t2 - t1 # 시간 단축 (음수)
            
            # dw_eff (실질 비용) = 페달링 에너지 - 운동에너지 이득(자산)
            # 즉, 에너지를 써서 속도가 빨라졌다면 그만큼은 '비용'이 아니라 '저축'으로 본다.
            dw_eff_1 = w_pedal_1 - ke_change_1
            dw_eff_2 = w_pedal_2 - ke_change_2
            
            dw = dw_eff_2 - dw_eff_1
            
            # 분모가 0이거나 음수가 되는 특이점 방지 (매우 높은 효율로 처리)
            if abs(dw) < 1e-6: 
                grad = -1e9 # 효율 무한대
            else:
                grad = dt / dw 
            
            # grad가 target_lambda보다 작다(더 음수다) = 가성비가 좋다
            if grad < target_lambda:
                low_p = mid_p
            else:
                high_p = mid_p
                
        return (low_p + high_p) / 2.0

    def _solve_segment_speed(self, seg: Segment, power: float, v_entry: float) -> float:
        """
        [수정됨] 정밀도 대폭 향상 (10회 -> 30회 반복)
        미분 계산 시 노이즈를 없애기 위해 높은 정밀도가 필수입니다.
        """
        if v_entry < 0.1: v_entry = 0.1 
        
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        p_wheel = power * (1 - self.params.drivetrain_loss)
        d = max(0.1, seg.length)
        
        theta = math.atan(seg.grade)
        f_const = total_mass * g * (math.sin(theta) + self.params.crr * math.cos(theta))
        
        low_v, high_v = 0.1, 130.0 / 3.6 # 범위 확장
        
        # [핵심 변경] 반복 횟수 10 -> 30
        for _ in range(30):
            v_final = (low_v + high_v) / 2.0
            v_avg = (v_entry + v_final) / 2.0
            
            f_aero = 0.5 * self.params.air_density * eff_cda * (v_avg**2)
            f_net = (p_wheel / v_avg) - f_aero - f_const
            
            work_net = f_net * d
            ke_change = 0.5 * total_mass * (v_final**2 - v_entry**2)
            
            if work_net > ke_change:
                low_v = v_final 
            else:
                high_v = v_final
                
        return (low_v + high_v) / 2.0

    def _calculate_min_power_for_speed(self, seg: Segment, speed_kmh: float) -> float:
        v = speed_kmh / 3.6
        total_mass = self.rider.weight + self.params.bike_weight
        theta = math.atan(seg.grade)
        f_resist = total_mass * 9.81 * (math.sin(theta) + self.params.crr * math.cos(theta)) + 0.5 * 1.225 * self.params.cda * v**2
        return max(20.0, f_resist * v / (1 - self.params.drivetrain_loss))

    def _solve_segment_physics(self, seg: Segment, p_target: float, v_entry: float, v_wind: float, f_limit: float) -> Tuple[float, float, bool, float]:
        # Same as V2/V3/V4 core physics
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

    def simulate_course(self, segments: List[Segment], power_profile: List[float]) -> SimulationResult:
        self.rider.reset_state()
        total_time, total_work, weighted_power_sum = 0.0, 0.0, 0.0
        v_current = 0.1
        track_data = []
        for i, seg in enumerate(segments):
            p_target = power_profile[i] if i < len(power_profile) else 150.0
            v_next, time_sec, _, p_actual = self._solve_segment_physics(seg, p_target, v_current, 0, 9999.0)
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

    def _get_fatigue_adjusted_limit(self, duration_sec: float) -> float:
        sorted_pdc = sorted([(int(k), v) for k, v in self.rider.pdc.items()])
        if not sorted_pdc: return self.rider.cp
        max_pdc_time, max_pdc_watts = sorted_pdc[-1]
        if duration_sec > max_pdc_time: return max_pdc_watts * (duration_sec / max_pdc_time) ** -0.10
        return self.rider.get_pdc_power(duration_sec)