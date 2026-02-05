import numpy as np
from scipy.integrate import solve_ivp

class PyfunValidator:
    def __init__(self, rider_mass=81.0, bike_mass=10.0, cda=0.314, crr=0.003, loss=0.03, rho=1.225):
        # [설정] 물리 상수 및 파라미터 초기화
        self.total_mass = rider_mass + bike_mass
        self.eff_mass = self.total_mass 
        self.cda = cda
        self.crr = crr
        self.rho = rho # Dynamic Air Density
        self.g = 9.81
        self.loss = loss

    def get_exact_final_speed(self, v_init, distance, grade, power_input, f_limit=1000.0):
        """
        [새로운 로직] 미분방정식 솔버(RK45)를 이용한 정밀 적분
        pyfun의 'Soft Wall'과 'Torque Limit'을 포함하여 물리적으로 검증함.
        """
        p_avail = power_input * (1 - self.loss) # [5] 구동계 손실

        # --- 1. 알짜힘(Net Force) 함수 정의 (게임 규칙 포함) ---
        def net_force_func(v):
            # 속도 0 예외 처리 (0.1m/s 미만은 0.1로 고정)
            v_safe = max(v, 0.1)

            # (A) 구동력 + 토크 제한 [6]
            f_pedal = p_avail / v_safe
            if f_pedal > f_limit: 
                f_pedal = f_limit
            
            # (B) 공기 저항 (Martin Eq. 2) [7]
            f_drag = 0.5 * self.rho * self.cda * (v_safe ** 2)

            # (C) 구름 저항 + 중력 (Martin Eq. 6a, 9a) [8][9]
            f_resist = self.total_mass * self.g * (self.crr + grade)

            # (D) [핵심] pyfun 특수 로직: Soft Wall (내리막 브레이크) [3]
            f_brake = 0.0
            if v_safe > 13.8889: # 50 km/h 초과 시
                v_kmh = v_safe * 3.6
                # pyfun의 가속도 기반 브레이크 공식을 힘으로 변환 (F=ma)
                # a_brake = 0.22 * ((v - 50)^1.2) / 3.6
                a_brake = (0.22 * ((v_kmh - 50.0) ** 1.2)) / 3.6
                f_brake = self.total_mass * a_brake

            return f_pedal - f_drag - f_resist - f_brake

        # --- 2. 미분방정식 정의 (dv/dx = F / mv, dt/dx = 1/v) ---
        def derivative(x, y):
            v = y[0]
            # t = y[1] (Not used in calc, but integrated)
            
            if v < 0.1: v = 0.1 # 저속 발산 방지
            
            f_net = net_force_func(v)
            
            # dv/dx = a / v = (F/m) / v
            d_v_d_x = f_net / (self.eff_mass * v)
            
            # dt/dx = 1 / v
            d_t_d_x = 1.0 / v
            
            return [d_v_d_x, d_t_d_x]

        # --- 3. 솔버 실행 (0m -> distance 까지 적분) ---
        v_start = max(v_init, 0.1)
        
        # y = [velocity, time]
        try:
            # y0=[v_start, 0.0] -> time starts at 0 for this segment
            sol = solve_ivp(derivative, [0, distance], [v_start, 0.0], rtol=1e-6, atol=1e-9)
            if sol.success:
                v_final_exact = sol.y[0][-1] # 적분 결과 (마지막 속도)
                time_exact = sol.y[1][-1]    # 적분 결과 (소요 시간)
            else:
                print(f"Warning: ODE Solver failed: {sol.message}")
                v_final_exact = v_start
                time_exact = distance / v_start
        except Exception as e:
             print(f"Error in ODE Solver: {e}")
             return v_start, 0.0

        # (E) Walking Mode 후처리 [10]
        min_speed = 5.0 / 3.6
        if v_final_exact < min_speed:
            v_final_exact = min_speed
            # 속도가 클램핑 되었다면 시간도 보정해야 하나, 
            # ODE는 물리적으로 감속된 과정을 적분했으므로 그대로 두는 게 더 정확할 수 있음.
            # 다만 5km/h 이하로 떨어진 구간을 5km/h로 달렸다고 치환한다면 시간은 줄어들어야 함.
            # 여기서는 단순 속도 클램핑만 적용.
            
        return v_final_exact, time_exact

        # (E) Walking Mode 후처리 [10]
        min_speed = 5.0 / 3.6
        if v_final_exact < min_speed:
            v_final_exact = min_speed
            
        return v_final_exact

# --- Self Check ---
if __name__ == "__main__":
    validator = PyfunValidator()
    
    # Test Case: 200W, -5% grade, 1km
    v_in = 40.0 / 3.6 
    dist = 1000.0     
    grade = -0.05     
    power = 200.0
    
    v_out = validator.get_exact_final_speed(v_in, dist, grade, power)
    
    print(f"=== Validator Self Check ===")
    print(f"Input: {power}W, Grade: {grade*100}%, Dist: {dist}m")
    print(f"V_in: {v_in*3.6:.2f} km/h")
    print(f"V_out (Exact): {v_out*3.6:.2f} km/h")
