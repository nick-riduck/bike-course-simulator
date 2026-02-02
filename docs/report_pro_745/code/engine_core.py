"""
[Physics Engine Core Logic]
실제 프로젝트(`src/physics_engine.py`)에서 물리 연산의 핵심인 `_solve_segment_physics` 및
페이싱 시뮬레이션 로직을 발췌하였습니다.
"""
import math
from typing import List, Tuple, Optional
from common import Rider, PhysicsParams, Segment, SimulationResult
from numba import njit

@njit
def solve_physics_kernel(length, grade, power, v_entry, v_wind, f_limit, total_mass, cda, crr, drivetrain_loss, air_density, drafting_factor):
    """
    [Optimized Kernel using Numba JIT]
    Accelerates the nested loops and bisection search.
    """
    p_avail = power * (1.0 - drivetrain_loss)
    eff_cda = cda * (1.0 - drafting_factor)
    g = 9.81
    f_gravity = total_mass * g * grade
    f_roll = total_mass * g * crr
    
    chunk_size = 20.0
    num_chunks = int(math.ceil(length / chunk_size))
    if num_chunks < 1: num_chunks = 1
    d_sub = length / num_chunks
    
    v_current = v_entry
    t_total = 0.0
    is_walking = False
    min_speed_ms = 5.0 / 3.6
    first_raw_speed = -1.0 # Use -1 as sentinel for Numba

    for _ in range(num_chunks):
        low = 0.01
        high = 45.0
        v_next = v_current
        
        for _i in range(15):
            if (high - low) < 0.005: break
            mid = (low + high) / 2
            
            v_avg = (v_current + mid) / 2
            if v_avg < 0.1: v_avg = 0.1
            
            f_pedal = p_avail / v_avg
            if f_pedal > f_limit: f_pedal = f_limit
            
            v_air = v_avg + v_wind
            f_drag = 0.5 * air_density * eff_cda * (v_air * abs(v_air))
            
            # Soft Wall Brake
            f_brake = 0.0
            if v_avg > 13.8889:
                v_avg_kmh = v_avg * 3.6
                a_brake_ms2 = (0.22 * ((v_avg_kmh - 50.0) ** 1.2)) / 3.6
                f_brake = total_mass * a_brake_ms2
            
            f_net = f_pedal - f_drag - f_gravity - f_roll - f_brake
            work_net = f_net * d_sub
            
            ke_initial = 0.5 * total_mass * (v_current ** 2)
            ke_final_target = 0.5 * total_mass * (mid ** 2)
            
            if (ke_initial + work_net) > ke_final_target:
                low = mid
            else:
                high = mid
        
        v_next = (low + high) / 2
        raw_v_next = v_next
        
        if v_next < min_speed_ms:
            v_next = min_speed_ms
            is_walking = True
            if first_raw_speed < 0: first_raw_speed = raw_v_next
        
        v_avg_chunk = (v_current + v_next) / 2
        if v_avg_chunk < 0.1: v_avg_chunk = 0.1
        t_total += d_sub / v_avg_chunk
        v_current = v_next
        
    final_raw_return = first_raw_speed if first_raw_speed >= 0 else v_next
    return v_current, t_total, is_walking, final_raw_return

class PhysicsEngine:
    def __init__(self, rider: Rider, params: PhysicsParams):
        self.rider = rider
        self.params = params
        # Pacing Strategy Parameters
        self.alpha_climb = 2.5
        self.alpha_descent = 10.0

    def _solve_segment_physics(self, seg: Segment, power: float, v_entry: float, v_wind: float, f_limit: float) -> Tuple[float, float, bool, float]:
        """
        [Core Kernel: Work-Energy Theorem]
        Calls the Numba-optimized static kernel.
        """
        total_mass = self.rider.weight + self.params.bike_weight
        rho = getattr(self.params, 'air_density', 1.225)
        
        return solve_physics_kernel(
            seg.length, seg.grade, power, v_entry, v_wind, f_limit,
            total_mass, self.params.cda, self.params.crr, 
            self.params.drivetrain_loss, rho, self.params.drafting_factor
        )

    def simulate_course(self, segments: List[Segment], p_base: float, max_power_limit: float) -> SimulationResult:
        self.rider.reset_state()
        total_time, total_work = 0.0, 0.0
        v_current = 0.1
        track_data = []
        f_max_initial = self.rider.weight * 9.81 * 1.5

        for seg in segments:
            # Pacing Strategy
            if seg.grade >= 0:
                p_target = p_base * (1.0 + self.alpha_climb * seg.grade)
            else:
                p_target = p_base * max(0.0, 1.0 + (self.alpha_descent * seg.grade))
            p_target = min(p_target, max_power_limit)
            
            v_next, time_sec, is_walking, raw_v_next = self._solve_segment_physics(seg, p_target, v_current, 0.0, f_max_initial)
            
            # Simple power estimation for result
            v_avg = (v_current + v_next) / 2
            p_actual = 30.0 if is_walking else p_target 
            
            total_time += time_sec
            total_work += p_actual * time_sec
            
            track_data.append({
                "dist_km": seg.end_dist / 1000.0,
                "speed_kmh": (v_next + v_current) / 2 * 3.6,
                "power": p_actual,
                "time_sec": total_time
            })
            v_current = v_next
            
        avg_p = total_work / total_time if total_time > 0 else 0
        return SimulationResult(total_time, p_base, 0, avg_p, 0, total_work/1000, 0, True, track_data=track_data)
