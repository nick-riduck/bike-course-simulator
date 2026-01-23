# Python Source (Converted)

> Converted from the PHP logic with the same calculation flow.
> Notes:
> - DB / WordPress / JWT parts were not ported here (engine-only).
> - `power_curve_model.php` tables must be provided as Python dict if you use the curve features.

```python
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Union

Number = Union[int, float]


def make_decimal(v: Number, ndigits: int) -> float:
    try:
        return round(float(v), ndigits)
    except (TypeError, ValueError):
        return round(0.0, ndigits)


def trans_time(minutes_value: Number) -> str:
    """
    PHP transTime()과 동일한 포맷:
      - 1분 미만: "xx초"
      - 60분 초과: "h시간 mm분 ss초"
      - 그 외: "m분 ss초"
    """
    v = float(minutes_value or 0.0)
    dec = v - int(v)
    m = int(v)

    if m < 1:
        ss = round(dec * 60, 1)
        return f"{ss}초"
    elif m > 60:
        h = int(m / 60)
        mm = m % 60
        ss = round(dec * 60)
        return f"{h}시간 {mm}분 {ss}초"
    else:
        ss = round(dec * 60)
        return f"{m}분 {ss}초"


def newton(aero: float, hw: float, tr: float, tran: float, p: float) -> float:
    """
    PHP Newton() 그대로:
      - 초기값 vel=20 (m/s)
      - MAX=10
      - TOL=0.05
      - 수렴 실패 시 0.0 반환
    """
    vel = 20.0
    MAX = 10
    TOL = 0.05

    for _ in range(1, MAX):
        tv = vel + hw
        aero_eff = aero if tv > 0.0 else -aero
        f = vel * (aero_eff * tv * tv + tr) - tran * p
        fp = aero_eff * (3.0 * vel + hw) * tv + tr

        # fp가 0에 가까우면 발산/NaN 방지
        if abs(fp) < 1e-12:
            return 0.0

        v_new = vel - f / fp
        if abs(v_new - vel) < TOL:
            return v_new
        vel = v_new

    return 0.0


def drivetrain_efficiency(dt: str, powerv: float) -> float:
    """
    PHP drivetrainEfficiency() 그대로:
      1) 구동계별 base efficiency
      2) powerv를 50~400으로 clamp
      3) r = 2.1246*log(pm) - 11.5
      4) (r + efficiency*100)/100 반환
    """
    dt_map = {
        "duraAce": 0.963,
        "ultegra": 0.962,
        "105": 0.961,
        "tiagra": 0.960,
        "sora": 0.958,
        "claris": 0.956,
        "sis": 0.940,
        "redAxs": 0.965,
        "forceAxs": 0.962,
        "rival": 0.961,
        "apex": 0.960,
        "superRecord": 0.963,
        "Record": 0.962,
        "Chorus": 0.961,
        "Potenza": 0.960,
        "Athena": 0.960,
        "Veloce": 0.958,
        "Centaur": 0.958,
        "kForce": 0.962,
    }
    efficiency = dt_map.get(dt, 0.962)

    if powerv >= 400:
        pm = 400.0
    elif powerv <= 50:
        pm = 50.0
    else:
        pm = float(powerv)

    r = 2.1246 * math.log(pm) - 11.5
    return (r + efficiency * 100.0) / 100.0


def calculate(avg_power: float, avg_speed: float, params: Mapping[str, Any]) -> Dict[str, Any]:
    """
    PHP calculate() 변환.
    params에 필요한 키 예:
      gender, age, rider_weight, rider_height,
      distance, temperature, elevation, altitude, grade,
      bike_type, bike_weight,
      crr, cda, rim_height, drivetrain,
      result_select
    """
    result_select = str(params.get("result_select", "speedToPower"))

    # Rider
    gender = str(params.get("gender", "M"))
    age = float(params.get("age", 30))
    rider_weight = float(params.get("rider_weight", 60))
    rider_height = float(params.get("rider_height", 170))

    # Environment
    distance_km = float(params.get("distance", 0))
    temperature_c = float(params.get("temperature", 20))
    elevation_m = float(params.get("elevation", 0))
    altitude_m = float(params.get("altitude", 0))
    grade = float(params.get("grade", 0.0))

    # Bike
    bike_type = str(params.get("bike_type", "road_allround"))  # kept for parity; not used in physics below
    bike_weight = float(params.get("bike_weight", 8.0))

    # grade auto-calc (distance+elevation 주어지고 grade=0이면)
    if (distance_km > 0 and elevation_m > 0) and grade == 0:
        grade = elevation_m / (distance_km * 1000.0)

    # BMR (Harris-Benedict, PHP 그대로)
    if gender == "M":
        default_cal = 66.47 + (13.7 * rider_weight) + (5 * rider_height) - (6.76 * age)
    else:  # "F"
        default_cal = 665.1 + (9.58 * rider_weight) + (1.85 * rider_height) - (4.68 * age)

    # Resistance
    rolling_res = float(params.get("crr", 0.0))
    frontal_area = float(params.get("cda", 0.0))  # CdA
    rim_height = float(params.get("rim_height", 0.0))  # present in PHP but not applied directly in core equations
    headwind = 0.0  # PHP에서 미사용

    dt = str(params.get("drivetrain", "ultegra"))

    # Air density (ISA 기반 식)
    density = (1.293 - 0.00426 * temperature_c) * math.exp(-(altitude_m * 0.709) / 7000.0)

    # total weight in Newtons (rider + bike + 1.0kg)
    twt = 9.798 * (rider_weight + bike_weight + 1.0)
    tres = twt * (grade + rolling_res)

    powerv = 0.0
    speed_kmh = 0.0
    t_min = 0.0  # minutes

    if result_select == "powerToSpeed":
        powerv = float(avg_power)
        transv = drivetrain_efficiency(dt, powerv)
        A2 = 0.5 * frontal_area * density
        v_ms = newton(A2, headwind, tres, transv, powerv)  # m/s
        v_kmh = v_ms * 3.6
        t_min = (60.0 * distance_km) / v_kmh if v_kmh > 0.0 else 0.0
        speed_kmh = make_decimal(v_kmh, 2)

    elif result_select == "speedToPower":
        speed_kmh = float(avg_speed)
        A2 = 0.5 * frontal_area * density
        v_ms = speed_kmh / 3.6
        tv = v_ms + headwind
        A2_eff = A2 if tv > 0.0 else -A2
        powerv_100 = (v_ms * tres + v_ms * tv * tv * A2_eff)  # drivetrain 효율 적용 전
        transv = drivetrain_efficiency(dt, powerv_100)
        powerv = powerv_100 / transv if transv != 0 else 0.0
        t_min = (16.6667 * distance_km) / v_ms if v_ms > 0.0 else 0.0

    elif result_select == "estimatePR":
        # PR 모드에서도 PHP는 powerToSpeed와 같은 속도/시간 계산을 수행
        powerv = float(avg_power)
        transv = drivetrain_efficiency(dt, powerv)
        A2 = 0.5 * frontal_area * density
        v_ms = newton(A2, headwind, tres, transv, powerv)
        v_kmh = v_ms * 3.6
        t_min = (60.0 * distance_km) / v_kmh if v_kmh > 0.0 else 0.0
        speed_kmh = make_decimal(v_kmh, 2)

    elif result_select == "estimateCdA":
        powerv = float(avg_power)
        speed_kmh = float(avg_speed)
        transv = drivetrain_efficiency(dt, powerv)

        v_ms = speed_kmh / 3.6
        tv = v_ms + headwind

        denom = (v_ms * tv * tv)
        if abs(denom) < 1e-12 or density == 0:
            frontal_area = 0.0
        else:
            A2_eff = ((powerv * transv) - (v_ms * tres)) / denom
            A2 = abs(A2_eff)
            frontal_area = (A2 * 2.0) / density

        t_min = (16.6667 * distance_km) / v_ms if v_ms > 0.0 else 0.0

    # Common outputs
    jouls = t_min * 60.0 * powerv
    kj = t_min * powerv * 0.24
    cal = (kj * 0.239) + (default_cal * (t_min / 1440.0) * 1.55)
    fb = (cal / 3500.0) * 0.45
    wkg = powerv / rider_weight if rider_weight > 0 else 0.0

    return {
        "resultSelect": result_select,
        "power": round(powerv),
        "wkg": make_decimal(wkg, 2),
        "time_string": trans_time(t_min),
        "time": t_min * 60.0,  # seconds
        "distance": make_decimal(distance_km, 2),
        "speed": make_decimal(speed_kmh, 2),
        "CdA": make_decimal(frontal_area, 4),
        "jouls": round(jouls),
        "calorie": make_decimal(cal, 4),
        "fat_burn": make_decimal(fb, 4),
        "gradeCalc": round(grade * 100.0, 2),
    }

```
