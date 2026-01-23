import math

def calculate_flat_time():
    # 1. 입력 파라미터
    rider_power = 160.0    # Watts
    rider_weight = 80.0    # kg
    cda = 0.32             # m^2
    distance_km = 100.0    # km
    
    # 2. 시스템 기본 상수 (PhysicsParams 및 엔진 로직 참조)
    bike_weight = 8.0      # kg (기본값)
    equipment_weight = 1.0 # kg (코드 내 하드코딩된 값)
    total_mass = rider_weight + bike_weight + equipment_weight # 89.0 kg
    
    crr = 0.006            # 기본 구름저항
    drivetrain_loss = 0.05 # 구동계 손실 5%
    air_density = 1.225    # kg/m^3
    
    g = 9.81
    grade = 0.0            # 평지
    
    # 3. 유효 파워 (바퀴에 전달되는 파워)
    p_wheel = rider_power * (1 - drivetrain_loss) # 160 * 0.95 = 152 W
    
    # 4. 저항력 계산 함수
    # F_total = F_gravity + F_roll + F_drag
    # 평지이므로 F_gravity = 0
    f_gravity = total_mass * g * math.sin(math.atan(grade)) # 0
    f_roll = total_mass * g * crr * math.cos(math.atan(grade)) # 약 89 * 9.81 * 0.006
    
    # 5. 속도 찾기 (이분 탐색 - 엔진 로직과 동일 방식)
    # P_wheel = F_total * v
    # P_wheel = (F_roll + 0.5 * rho * CdA * v^2) * v
    # f(v) = 0.5 * rho * CdA * v^3 + F_roll * v - P_wheel = 0
    
    low = 0.0
    high = 100.0 # m/s (충분히 큰 값)
    
    print(f"--- Simulation Conditions ---")
    print(f"Power (Input): {rider_power} W")
    print(f"Power (Wheel): {p_wheel:.2f} W")
    print(f"Total Mass   : {total_mass} kg")
    print(f"CdA          : {cda}")
    print(f"Distance     : {distance_km} km")
    print(f"-----------------------------")
    
    v_solution = 0.0
    
    for i in range(50):
        mid = (low + high) / 2
        v = mid
        
        if v < 0.001: v = 0.001
        
        # 공기 저항
        f_drag = 0.5 * air_density * cda * (v ** 2)
        
        # 필요한 힘
        f_req = f_roll + f_drag
        
        # 이 속도를 유지하기 위한 파워
        p_req = f_req * v
        
        if p_req < p_wheel:
            low = mid # 파워가 남음 -> 더 빠르게 가능
        else:
            high = mid # 파워 부족 -> 느리게
            
    v_solution = (low + high) / 2
    
    # 6. 결과 계산
    speed_kmh = v_solution * 3.6
    time_sec = (distance_km * 1000) / v_solution
    
    hours = int(time_sec // 3600)
    minutes = int((time_sec % 3600) // 60)
    seconds = int(time_sec % 60)
    
    print(f"Calculated Constant Speed : {speed_kmh:.2f} km/h")
    print(f"Total Time                : {hours}h {minutes}m {seconds}s")

if __name__ == "__main__":
    calculate_flat_time()
