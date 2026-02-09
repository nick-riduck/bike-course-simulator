from __future__ import annotations

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.core.rider import Rider
from src.core.gpx_loader import Segment
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
    track_data: List[Dict[str, Any]] = None

class PhysicsEngine:
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        self.rider = rider
        self.params = params
        self.weather = weather_client
        # 경사도에 따른 파워 가중치 (오르막에서는 더 쓰고, 내리막에서는 덜 쓰는 전략)
        self.alpha_climb = 2.5   # 오르막 가중치 (경사도 10%일 때 약 25% 더 씀)
        self.alpha_descent = 10.0 # 내리막 감산치 (경사도 -5%일 때 파워 50% 감소)
    
    def find_optimal_pacing(self, segments: List[Segment]) -> SimulationResult:
        """
        [최적 페이싱 솔버: 이분 탐색 (Binary Search)]
        
        복잡한 수렴 공식 대신, 강력하고 확실한 이분 탐색을 사용합니다.
        "최적의 파워는 10W ~ 1500W 사이에 반드시 존재한다"는 전제로,
        NP(Normalized Power)와 PDC Limit(생리학적 한계)가 교차하는 지점을 찾습니다.
        
        판단 로직:
        1. 임의의 파워(Mid)로 달린다.
        2. 결과 시간(Time)에 해당하는 라이더의 한계 파워(PDC Limit)를 조회한다.
        3. 실제 쓴 파워(NP)가 한계(Limit)보다 큰가?
           - YES (오버페이스/Bonk): 파워를 낮춘다 (High = Mid)
           - NO (힘이 남음): 파워를 높인다 (Low = Mid)
           
        반복 횟수: 15회 (1500W 범위에서 오차 0.1W 이내 정밀도)
        """
        low = 10.0
        high = 1500.0
        
        best_result: Optional[SimulationResult] = None
        
        for i in range(15):
            mid = (low + high) / 2.0
            
            # 시뮬레이션 수행
            # max_power_limit는 페이싱 전략상 '순간적으로' 낼 수 있는 최대치를 의미하므로,
            # 평균 목표인 mid보다 넉넉하게 잡아줍니다. (Pacing 함수에서 비율로 조절됨)
            res = self.simulate_course(segments, p_base=mid, max_power_limit=mid * 2.0)
            
            # 비교를 위한 지표 계산
            # NP가 계산되지 않은 경우(너무 짧거나 오류) p_base를 대신 사용
            simulated_intensity = res.normalized_power if res.normalized_power > 0 else mid
            
            # 시뮬레이션 시간에 해당하는 라이더의 생리학적 한계(PDC) 조회
            pdc_limit_watts = self._get_dynamic_pdc_limit(res.total_time_sec)
            
            # 디버깅 출력
            print(f"[Binary Search #{i+1}] P_base: {mid:.1f}W -> Time: {res.total_time_sec:.0f}s, NP: {simulated_intensity:.0f}W / Limit: {pdc_limit_watts:.0f}W", flush=True)
            
            # 판단: Bonk가 났거나, NP가 한계보다 높으면 -> 파워를 줄여야 함
            if not res.is_success or simulated_intensity > pdc_limit_watts:
                high = mid
            else:
                # 성공했고 NP가 한계보다 낮으면 -> 파워를 더 올려도 됨
                # (성공한 케이스만 best_result로 저장)
                best_result = res
                low = mid
        
        # 탐색 실패 시(전 구간 Bonk 등), 마지막 시도 결과를 반환
        return best_result if best_result else self.simulate_course(segments, low, low * 2.0)

    def _get_dynamic_pdc_limit(self, duration_sec: float) -> float:
        """
        [PDC + Riegel Extrapolation]
        
        사용자의 질문: "PDC 범위 밖의 파워는 어떻게 구하는가?"
        답변: Riegel의 피로 모델(Fatigue Model)을 사용하여 외삽(Extrapolation)합니다.
        
        공식: P = P_ref * (T / T_ref) ^ -0.07
        
        1. duration_sec가 PDC 데이터 범위 내(예: 1초~2시간)라면?
           -> 저장된 PDC 데이터를 선형 보간(Interpolation)하여 정확한 값을 줍니다.
        2. duration_sec가 PDC 범위 밖(예: 5시간)이라면?
           -> 가지고 있는 데이터 중 가장 긴 시간(예: 2시간)의 파워를 기준점(Reference)으로 삼고,
              Riegel 지수(-0.07)를 적용하여 시간이 길어질수록 파워가 자연스럽게 떨어지도록 계산합니다.
           -> 1.2배 같은 매직 넘버는 일절 사용하지 않습니다. 순수 데이터 기반입니다.
        """
        # 1. PDC 데이터 정렬
        sorted_pdc = sorted([(int(k), v) for k, v in self.rider.pdc.items()])
        if not sorted_pdc:
            return self.rider.cp # 데이터 없으면 CP 리턴 (안전장치)
            
        max_pdc_time, max_pdc_watts = sorted_pdc[-1]
        
        # 2. 범위 밖 (장거리) 처리: Riegel Model 적용
        if duration_sec > max_pdc_time:
            # 피로 계수 0.07은 사이클링 통계학적 표준값 (0.05 ~ 0.08 사이)
            riegel_exponent = -0.07 
            extrapolated_power = max_pdc_watts * (duration_sec / max_pdc_time) ** riegel_exponent
            return extrapolated_power
            
        # 3. 범위 내 처리: 선형 보간 (Linear Interpolation)
        #    더 정교한 로그 보간도 가능하지만, 촘촘한 PDC 데이터가 있다면 선형으로도 충분합니다.
        return self.rider.get_pdc_power(duration_sec)

    def simulate_course(self, segments: List[Segment], p_base: float, max_power_limit: float) -> SimulationResult:
        self.rider.reset_state()
        
        total_time = 0.0
        total_work = 0.0
        weighted_power_sum = 0.0
        v_current = 0.1 # Start from near-zero (0.1 m/s) to avoid div-by-zero
        min_w_prime = self.rider.w_prime_max
        track_data = []

        wind_speed_global = 0.0
        wind_deg_global = 0.0
        if self.weather and self.weather.use_scenario_mode:
             d = self.weather._get_scenario_weather()
             wind_speed_global = d['wind_speed']
             wind_deg_global = d['wind_deg']

        # 초기 최대 근력 (스프린트 제한용, 약 1.5G)
        f_max_initial = self.rider.weight * 9.81 * 1.5
        prev_heading = segments[0].heading

        for seg in segments:
            # --- Cornering Speed Limit Logic (Restored from Jan 23) ---
            heading_change = abs(seg.heading - prev_heading)
            if heading_change > 180: heading_change = 360 - heading_change
            
            # Physics-based Cornering Limit: V = sqrt(mu * g * R)
            if seg.length > 0 and heading_change > 1.0: # Ignore micro-jitters (< 1 deg)
                # 1. Calculate Radius (R)
                theta_rad = math.radians(heading_change)
                curvature_rad = theta_rad / seg.length
                
                if curvature_rad > 0.0001:
                    radius = 1.0 / curvature_rad
                    
                    # 2. Limit Speed
                    # mu = 0.8 (Tire Grip + Banking), g = 9.81
                    mu = 0.8
                    g = 9.81
                    v_corner_limit = math.sqrt(mu * g * radius)
                    
                    v_current = min(v_current, v_corner_limit) 
            
            prev_heading = seg.heading
            # ----------------------------------
            
            # -----------------------------------------------------
            # [페이싱 전략 적용]
            # 경사도에 따라 목표 파워를 연속적으로 조절합니다.
            # -----------------------------------------------------
            p_target = self._calculate_target_power(p_base, seg.grade, max_power_limit)
            
            # -----------------------------------------------------
            # [환경 변수 계산]
            # 상대 풍속(Yaw Angle)을 고려한 공기저항 벡터 계산
            # -----------------------------------------------------
            rel_angle_rad = math.radians(wind_deg_global - seg.heading)
            v_headwind_env = wind_speed_global * math.cos(rel_angle_rad)
            
            # 장시간 주행 시 근신경계 피로로 인한 최대 토크 감소 (Riegel 기반 감쇠)
            decay_factor = 1.0
            if total_time > 3600:
                decay_factor = (3600.0 / total_time) ** 0.05
            current_f_limit = f_max_initial * decay_factor
            
            # -----------------------------------------------------
            # [물리 엔진 코어: 에너지 보존 법칙]
            # _solve_segment_physics 내부에서 '일-에너지 정리'를 통해 속도를 구합니다.
            # -----------------------------------------------------
            v_next, time_sec, is_walking, raw_v_next = self._solve_segment_physics(seg, p_target, v_current, v_headwind_env, f_limit=current_f_limit)
            
            # --- 실제 파워(Actual Power) 결정 로직 ---
            if is_walking:
                # 끌바 시: 자전거 동력은 0W, 라이더 대사량(체력소모)은 30W로 간주
                p_actual = 30.0
                original_speed_kmh = raw_v_next * 3.6
                print(f"[Walking] @ {seg.start_dist/1000:.2f}km, Grade {seg.grade*100:.1f}%, Original Speed {original_speed_kmh:.4f} km/h -> 5km/h enforced", flush=True)
            else:
                # 주행 시: 토크 한계에 걸렸는지 확인하여 실제 출력 파워 역산
                v_avg = (v_current + v_next) / 2
                if v_avg < 0.1: v_avg = 0.1
                
                # 목표 파워를 내기 위해 필요한 힘
                p_avail_required = p_target * (1 - self.params.drivetrain_loss)
                f_required = p_avail_required / v_avg
                
                # 실제 바퀴를 밀어낸 힘 (토크 리밋 적용)
                f_actual_wheel = min(f_required, current_f_limit)
                
                # 실제 라이더가 낸 파워 (구동계 손실 역보정)
                p_actual = (f_actual_wheel * v_avg) / (1 - self.params.drivetrain_loss)
            
            # 생리학적 상태 업데이트 (실제 파워 기반)
            self.rider.update_w_prime(p_actual, time_sec)
            
            if self.rider.is_bonked():
                return SimulationResult(total_time, p_base, 0, 0, 0, 0, -1, False, "BONK (W' Depleted)")

            total_time += time_sec
            total_work += p_actual * time_sec
            weighted_power_sum += (p_actual ** 4) * time_sec
            min_w_prime = min(min_w_prime, self.rider.w_prime_bal)

            track_data.append({
                "dist_km": seg.end_dist / 1000.0,
                "ele": seg.end_ele,
                "grade_pct": seg.grade * 100,
                "speed_kmh": (v_next + v_current) / 2 * 3.6,
                "power": p_actual, # 실제 낸 파워 기록
                "time_sec": total_time,
                "w_prime_bal": self.rider.w_prime_bal,
                "lat": seg.lat,
                "lon": seg.lon
            })
            v_current = v_next
            
        avg_p = total_work / total_time if total_time > 0 else 0
        np = math.pow(weighted_power_sum / total_time, 0.25) if total_time > 0 else 0
        dist_km = sum(s.length for s in segments) / 1000.0
        avg_spd = (dist_km * 3600) / total_time if total_time > 0 else 0
        
        return SimulationResult(total_time, p_base, avg_spd, avg_p, np, total_work/1000, min_w_prime, True, track_data=track_data)

    def _calculate_target_power(self, p_base: float, grade: float, max_limit: float) -> float:
        """
        [가변 페이싱 전략 (Continuous Variable Pacing)]
        
        기존의 계단식(Discrete) 로직(-0.02, -0.04 기준)을 제거하고,
        경사도에 따라 연속적으로 변하는 부드러운 함수를 적용했습니다.
        
        1. 오르막 (Grade > 0):
           P_target = P_base * (1 + alpha * grade)
           경사가 셀수록 파워를 더 씁니다. 단, max_limit(PDC 상한선)은 넘지 않습니다.
           
        2. 내리막 (Grade < 0):
           P_target = P_base * (1 + alpha_descent * grade)
           경사가 -10%면 파워를 거의 0으로 줄여서 회복(Coasting)합니다.
           기존처럼 특정 각도에서 갑자기 파워가 반토막 나는 현상을 방지합니다.
        """
        if grade >= 0:
            # 오르막: 경사도 비례 증가 (최대치 제한)
            # 예: 경사도 5% -> 1 + 2.5*0.05 = 1.125배 (12.5% 더 씀)
            target = p_base * (1.0 + self.alpha_climb * grade)
            return min(target, max_limit)
        else:
            # 내리막: 경사도 비례 감소
            # 예: 경사도 -5% -> 1 + 10.0*(-0.05) = 1 - 0.5 = 0.5배 (50%만 씀)
            # 예: 경사도 -10% -> 1 - 1.0 = 0 (페달링 중지)
            factor = 1.0 + (self.alpha_descent * grade)
            return p_base * max(0.0, factor)

    def _solve_segment_physics(self, seg: Segment, power: float, v_entry: float, v_wind: float, f_limit: float) -> Tuple[float, float, bool, float]:
        """
        [물리 엔진 코어: 에너지 보존 법칙 (Work-Energy Theorem)]
        
        이 함수는 단순히 힘의 평형(F_net=0)을 구하는 것이 아니라,
        '에너지의 변화량'을 적분하여 다음 구간의 속도를 계산합니다.
        
        공식: Delta K.E. = Net Work
        0.5 * m * (v_next^2 - v_curr^2) = F_net * distance
        
        이를 통해 내리막에서 얻은 가속도(운동 에너지)가 
        다음 오르막 초입까지 유지되는 '관성 주행(Momentum)'을 구현합니다.
        """
        g = 9.81
        total_mass = self.rider.weight + self.params.bike_weight
        # 구동계 손실 반영 (예: 95%만 바닥으로 전달)
        p_avail = power * (1 - self.params.drivetrain_loss)
        
        # 공기저항 계수 (드래프팅 효과 반영)
        eff_cda = self.params.cda * (1 - self.params.drafting_factor)
        
        # 경사 저항 (Gravity) & 구름 저항 (Rolling)
        f_gravity = total_mass * g * seg.grade
        f_roll = total_mass * g * self.params.crr
        
        # 수치해석 안정성을 위해 긴 구간은 20m 단위로 잘라서 계산 (Sub-stepping)
        chunk_size = 20.0
        num_chunks = max(1, math.ceil(seg.length / chunk_size))
        d_sub = seg.length / num_chunks
        
        v_current = v_entry
        t_total = 0.0
        is_walking = False
        min_speed_ms = 5.0 / 3.6
        first_raw_speed = None # 끌바 발생 시점의 원래 속도

        for _ in range(num_chunks):
            # Bisection Method (이분 탐색)
            # 에너지 방정식을 만족하는 v_next를 찾습니다.
            # v_next가 커지면 공기저항(F_drag)이 커져서 Work_net이 줄어들고,
            # v_next가 작으면 반대가 되는 관계를 이용합니다.
            
            low = 0.01  # 최소 속도
            high = 45.0 # 최대 속도 (약 160km/h) - 물리적 한계
            
            v_next = v_current
            
            for _i in range(15): # 15회 반복이면 오차 0.01km/h 미만으로 수렴
                if (high - low) < 0.005: break
                
                mid = (low + high) / 2
                
                # 평균 속도 (사다리꼴 적분 근사)
                v_avg = (v_current + mid) / 2
                if v_avg < 0.1: v_avg = 0.1
                
                # 힘 계산
                # F_pedal = Power / Velocity (P=Fv)
                f_pedal = p_avail / v_avg
                
                # 토크(근력) 한계 적용 (너무 느린 속도에서 무한대 힘 방지)
                if f_pedal > f_limit: f_pedal = f_limit
                
                # 공기저항: F = 0.5 * rho * CdA * v_rel^2
                # (바람이 불 경우 상대 속도 v_avg + v_wind 고려)
                v_air = v_avg + v_wind
                f_drag = 0.5 * self.params.air_density * eff_cda * (v_air * abs(v_air))
                
                # --- Downhill Braking Logic (Soft Wall @ 80km/h) ---
                f_brake = 0.0
                if v_avg > 13.8889: # 50 km/h
                    v_avg_kmh = v_avg * 3.6
                    # Deceleration a = 0.22 * (V - 50)^1.2 (km/h per sec)
                    a_brake_ms2 = (0.22 * ((v_avg_kmh - 50.0) ** 1.2)) / 3.6
                    f_brake = total_mass * a_brake_ms2
                
                f_net = f_pedal - f_drag - f_gravity - f_roll - f_brake
                
                # 일-에너지 정리 검증
                work_net = f_net * d_sub
                
                ke_initial = 0.5 * total_mass * (v_current ** 2)
                ke_final_target = 0.5 * total_mass * (mid ** 2)
                
                # 에너지 보존식: 초기E + 알짜일 = 나중E
                # 좌변(공급된 에너지)이 우변(필요한 에너지)보다 크면? -> 속도 더 낼 수 있음 (Low 올림)
                if (ke_initial + work_net) > ke_final_target:
                    low = mid
                else:
                    high = mid
            
            v_next = (low + high) / 2
            raw_v_next = v_next # 클램핑 전 원본 속도
            
            # --- 5km/h Min Speed Clamp (Walking Mode) ---
            if v_next < min_speed_ms:
                v_next = min_speed_ms
                is_walking = True
                if first_raw_speed is None:
                    first_raw_speed = raw_v_next
            
            # 시간 누적 (t = d / v)
            v_avg_chunk = (v_current + v_next) / 2
            if v_avg_chunk < 0.1: v_avg_chunk = 0.1
            t_total += d_sub / v_avg_chunk
            
            v_current = v_next
        
        # 만약 끌바가 없었다면 마지막 속도를 반환
        final_raw_return = first_raw_speed if first_raw_speed is not None else v_next
            
        return v_current, t_total, is_walking, final_raw_return