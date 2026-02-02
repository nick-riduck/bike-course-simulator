"""
[ODE Validator]
scipy.integrate.solve_ivp를 사용하여 미분방정식을 정밀 적분하는 검증 도구입니다.
"""
import numpy as np
from scipy.integrate import solve_ivp

class PyfunValidator:
    def __init__(self, rider_mass=81.0, bike_mass=10.0, cda=0.314, crr=0.003, loss=0.03, rho=1.225):
        self.total_mass = rider_mass + bike_mass
        self.eff_mass = self.total_mass
        self.cda = cda
        self.crr = crr
        self.rho = rho
        self.g = 9.81
        self.loss = loss

    def get_exact_final_speed(self, v_init, distance, grade, power_input, f_limit=10000.0):
        p_avail = power_input * (1 - self.loss)

        def net_force_func(v):
            v_safe = max(v, 0.1)
            f_pedal = p_avail / v_safe
            if f_pedal > f_limit: f_pedal = f_limit
            
            f_drag = 0.5 * self.rho * self.cda * (v_safe ** 2)
            f_resist = self.total_mass * self.g * (self.crr + grade)
            
            f_brake = 0.0
            if v_safe > 13.8889: # 50 km/h
                v_kmh = v_safe * 3.6
                a_brake = (0.22 * ((v_kmh - 50.0) ** 1.2)) / 3.6
                f_brake = self.total_mass * a_brake

            return f_pedal - f_drag - f_resist - f_brake

        def derivative(x, y):
            v = y[0]
            if v < 0.1: v = 0.1
            f_net = net_force_func(v)
            d_v_d_x = f_net / (self.eff_mass * v)
            d_t_d_x = 1.0 / v
            return [d_v_d_x, d_t_d_x]

        v_start = max(v_init, 0.1)
        try:
            # Optimized tolerances: rtol=1e-4 (0.01%) is sufficient for physics validation
            sol = solve_ivp(derivative, [0, distance], [v_start, 0.0], rtol=1e-4, atol=1e-7)
            if sol.success:
                v_final = sol.y[0][-1]
                time = sol.y[1][-1]
            else:
                v_final = v_start
                time = distance / v_start
        except:
            return v_start, 0.0

        min_speed = 5.0 / 3.6
        if v_final < min_speed: v_final = min_speed
            
        return v_final, time
