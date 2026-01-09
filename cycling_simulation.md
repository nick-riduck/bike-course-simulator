# 🚴 Cycling Power/Speed Simulation API

## 개요

`get-simulation.php`는 물리 법칙 기반의 사이클링 파워-속도 시뮬레이션 API입니다.  
라이더와 자전거의 조건, 환경 변수를 입력받아 **파워↔속도 변환**, **CdA 추정**, **PR 예측** 등을 수행합니다.

---

## 📋 목차

1. [API 정보](#api-정보)
2. [파일 구조](#파일-구조)
3. [의존성](#의존성)
4. [입력 파라미터](#입력-파라미터)
5. [계산 모드 (result_select)](#계산-모드-result_select)
6. [출력 형식](#출력-형식)
7. [핵심 함수](#핵심-함수)
8. [물리 공식 및 출처](#물리-공식-및-출처)
9. [데이터베이스 테이블](#데이터베이스-테이블)
10. [사용 예시](#사용-예시)

---

## API 정보

| 항목 | 내용 |
|------|------|
| **엔드포인트** | `/json-api/get-simulation.php` |
| **메서드** | `GET`, `POST` |
| **인증** | JWT 토큰 필수 (Authorization 헤더 또는 `jwt` 파라미터) |
| **응답 형식** | `application/json` |

---

## 파일 구조

```
json-api/
├── get-simulation.php      # 메인 시뮬레이션 API (인증 필요)
├── get-simulation-open.php # 공개 시뮬레이션 API (인증 불필요)
├── power_curve_model.php   # W/kg 파워 커브 모델 데이터
├── bikekit.php             # 바이크 키트 관리 API
└── ...

riduck-api-common.php       # JWT 인증, WordPress 환경, XSS 필터
```

---

## 의존성

### riduck-api-common.php
- **JWT 인증**: `AAM_Core_Jwt_Issuer`를 통한 토큰 검증
- **WordPress 환경**: `$wpdb` 데이터베이스 객체 제공
- **XSS 필터**: `xssClean()` 함수로 입력값 정제
- **사용자 정보**: 인증된 `$user_id` 제공

### power_curve_model.php
- W/kg 기반 파워 커브 모델 데이터
- `$power_curve_model['maxWkg']`, `$power_curve_model['minWkg']` 배열

---

## 입력 파라미터

### 라이더 정보

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `gender` | string | `"M"` | 성별 (`M`: 남성, `F`: 여성) |
| `rider_height` | float | `170` | 키 (cm) |
| `rider_weight` | float | `60` | 체중 (kg) |
| `age` | int | `30` | 나이 (기초대사량 계산용) |

### 자전거 정보

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `bike_type` | string | `road_allround` | 자전거 유형 |
| `bike_weight` | float | `8.0` | 자전거 무게 (kg) |
| `drivetrain` | string | `ultegra` | 구동계 종류 |

#### 구동계 옵션

| 브랜드 | 옵션 |
|--------|------|
| **Shimano** | `duraAce`, `ultegra`, `105`, `tiagra`, `sora`, `claris`, `sis` |
| **SRAM** | `redAxs`, `forceAxs`, `rival`, `apex` |
| **Campagnolo** | `superRecord`, `Record`, `Chorus`, `Potenza`, `Athena`, `Veloce`, `Centaur` |
| **FSA** | `kForce` |

### 주행 환경

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `distance` | float | `0` | 주행 거리 (km) |
| `elevation` | float | `0` | 획득 고도 (m) |
| `altitude` | float | `0` | 평균 고도 (m) - 공기밀도 계산용 |
| `temperature` | float | `20` | 온도 (°C) - 공기밀도 계산용 |
| `grade` | float | `0.00` | 경사도 (소수, 예: 0.05 = 5%) |

### 저항 계수

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `crr` | float | `0` | 구름저항계수 (Coefficient of Rolling Resistance) |
| `cda` | float | `0` | 공기저항면적 (CdA, m²) |
| `rim_height` | int | `0` | 휠 림 높이 (mm) |

### 바이크 키트 상세

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `tire_product` | int | `1022` | 타이어 제품 ID |
| `tire_width` | int | `2` | 타이어 폭 인덱스 |
| `cadence` | int | `90` | 케이던스 (rpm) |
| `rider_pose` | int | `2` | 라이딩 자세 (1:업라이트, 2:노멀, 3:에어로) |
| `surface_select` | int | `2` | 노면 상태 |

### 계산 입력

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `result_select` | string | `speedToPower` | 계산 모드 |
| `avg_power` | float | `100` | 입력 파워 (W) |
| `avg_speed` | float | `10` | 입력 속도 (km/h) |

---

## 계산 모드 (result_select)

| 모드 | 설명 | 주요 입력 | 주요 출력 |
|------|------|----------|----------|
| `speedToPower` | 속도 → 필요 파워 계산 | `avg_speed` | `power`, `wkg`, `calorie` |
| `powerToSpeed` | 파워 → 예상 속도 계산 | `avg_power` | `speed`, `time`, `time_string` |
| `estimateCdA` | 파워+속도로 CdA 역산 | `avg_power`, `avg_speed` | `CdA` |
| `estimatePR` | 코스에 대한 PR 예측 | 사용자 PDC 커브 | `workable_pr`, `ideal_pr` |

---

## 출력 형식

### 기본 응답 구조

```json
{
  "user_result": {
    "resultSelect": "speedToPower",
    "power": 200,
    "wkg": 3.33,
    "time_string": "30분 0초",
    "time": 1800,
    "distance": 15.0,
    "speed": 30.0,
    "CdA": 0.32,
    "jouls": 360000,
    "calorie": 450.5,
    "fat_burn": 0.058,
    "gradeCalc": 2.5
  },
  "power_table": [
    { "power": 150, "speed": 25.0, ... },
    { "power": 175, "speed": 27.5, ... },
    ...
  ],
  "bikeKit": { ... }
}
```

### estimatePR 모드 추가 필드

```json
{
  "workable_pr": {
    "time": 3600,
    "time_string": "1시간 0분 0초",
    "power": 250,
    "e_range": ["5분 0초", 10]
  },
  "ideal_pr": {
    "time": 3400,
    "time_string": "56분 40초",
    "power": 260,
    "e_range": ["4분 0초", 8]
  }
}
```

---

## 핵심 함수

### 1. `calculate($avgPower, $avgSpeed, $params)`

**메인 시뮬레이션 계산 엔진**

물리 법칙 기반으로 파워↔속도 변환, CdA 추정 등을 수행합니다.

```php
/**
 * @param float $avgPower  입력 파워 (W)
 * @param float $avgSpeed  입력 속도 (km/h)
 * @param array $params    시뮬레이션 파라미터 배열
 * @return array           계산 결과
 */
function calculate($avgPower, $avgSpeed, $params) {
    // 1. 라이더/자전거/환경 정보 추출
    // 2. 기초대사량(BMR) 계산 - Harris-Benedict 공식
    // 3. 공기밀도 계산 - ISA 기반
    // 4. 저항력 계산 (중력 + 구름저항)
    // 5. result_select에 따른 분기 계산
    // 6. 칼로리, 지방연소량 등 부가 정보 계산
    // 7. 결과 반환
}
```

### 2. `Newton($aero, $hw, $tr, $tran, $p)`

**Newton-Raphson 속도 수렴 알고리즘**

파워가 주어졌을 때 속도를 구하는 비선형 방정식을 풀기 위한 수치해석 함수입니다.

```php
/**
 * @param float $aero  공기저항 계수 (0.5 × CdA × ρ)
 * @param float $hw    맞바람 속도 (m/s)
 * @param float $tr    총 저항력 (N)
 * @param float $tran  구동계 효율
 * @param float $p     입력 파워 (W)
 * @return float       계산된 속도 (m/s)
 */
function Newton($aero, $hw, $tr, $tran, $p) {
    $vel = 20;       // 초기 추정값
    $MAX = 10;       // 최대 반복 횟수
    $TOL = 0.05;     // 수렴 허용 오차
    
    for ($i = 1; $i < $MAX; $i++) {
        // f(v) = v × (aero × v² + tr) - η × P = 0
        // f'(v) = aero × (3v + hw) × (v + hw) + tr
        $vNew = $vel - $f / $fp;  // Newton-Raphson 공식
        if (abs($vNew - $vel) < $TOL) return $vNew;
        $vel = $vNew;
    }
    return 0.0;  // 수렴 실패
}
```

### 3. `drivetrainEfficiency($dt, $powerv)`

**구동계 효율 계산**

구동계 종류와 파워에 따른 동력 전달 효율을 반환합니다.

```php
/**
 * @param string $dt      구동계 종류 (예: 'ultegra', 'duraAce')
 * @param float  $powerv  입력 파워 (W)
 * @return float          효율 (0~1)
 */
function drivetrainEfficiency($dt, $powerv) {
    // 구동계별 기본 효율
    // Shimano: 96.3% (Dura-Ace) ~ 94.0% (SIS)
    // SRAM: 96.5% (Red eTap) ~ 96.0% (Apex)
    // Campagnolo: 96.3% (Super Record) ~ 95.8% (Centaur)
    
    // 파워에 따른 효율 보정
    // 저파워(50W)에서 효율 저하, 고파워(400W)에서 효율 개선
    $r = 2.1246 * log($pm) - 11.5;
    return ($r + $efficiency * 100) / 100;
}
```

### 4. `pr_estimate($ftp, $curve, $params)`

**개인기록(PR) 예측**

사용자의 FTP와 파워 커브를 기반으로 특정 코스의 예상 완주 시간을 계산합니다.

```php
/**
 * @param float  $ftp     사용자 FTP (W)
 * @param object $curve   파워 커브 데이터 (초:파워 매핑)
 * @param array  $params  코스 정보
 * @return array          예상 시간, 파워, 오차 범위
 */
function pr_estimate($ftp, $curve, $params) {
    // 1. FTP로 필요 에너지(줄) 계산
    // 2. 파워 커브에서 해당 에너지를 낼 수 있는 시간대 탐색
    // 3. 선형 보간으로 정확한 예상 시간 계산
    // 4. 오차 범위 계산
}
```

### 5. `setBikeKit($params, $user_id, $option)`

**바이크 키트 설정 저장**

사용자의 바이크 키트 설정을 데이터베이스에 저장합니다.

```php
/**
 * @param array  $params   바이크 키트 파라미터
 * @param int    $user_id  사용자 ID
 * @param bool   $option   옵션 (현재 미사용)
 * @return array           저장된 파라미터
 */
function setBikeKit($params, $user_id, $option) {
    // riduck_user_extrainfo.bikeKit_json 업데이트
    // riduck_bike_kit 테이블 UPDATE 또는 INSERT
}
```

### 6. 유틸리티 함수

| 함수 | 설명 |
|------|------|
| `makeDecimal2($v)` | 소수점 2자리 반올림 |
| `makeDecimal4($v)` | 소수점 4자리 반올림 |
| `makeDecimal6($v)` | 소수점 6자리 반올림 |
| `transTime($v)` | 분 → "X시간 Y분 Z초" 문자열 변환 |
| `ftpToCurve($ftp, $weight)` | FTP로부터 예상 파워 커브 생성 |

---

## 물리 공식 및 출처

### 1. 기초대사량 (BMR) - Harris-Benedict Equation (1918)

현재 시스템에서 사용하는 공식입니다.

```
남성: BMR = 66.47 + (13.7 × 체중kg) + (5 × 키cm) - (6.76 × 나이)
여성: BMR = 655.1 + (9.58 × 체중kg) + (1.85 × 키cm) - (4.68 × 나이)
```

**출처:**
> Harris JA, Benedict FG. "A Biometric Study of Human Basal Metabolism"  
> Proceedings of the National Academy of Sciences. 1918;4(12):370-373  
> DOI: [10.1073/pnas.4.12.370](https://doi.org/10.1073/pnas.4.12.370)

### 2. 기초대사량 (BMR) - Mifflin-St Jeor Equation (1990)

더 정확한 현대 공식으로, 참고용으로 주석에 포함되어 있습니다.

```
남성: BMR = (10 × 체중kg) + (6.25 × 키cm) - (5 × 나이) + 5
여성: BMR = (10 × 체중kg) + (6.25 × 키cm) - (5 × 나이) - 161
```

**출처:**
> Mifflin MD, St Jeor ST, et al. "A new predictive equation for resting energy expenditure in healthy individuals"  
> American Journal of Clinical Nutrition. 1990;51(2):241-247  
> DOI: [10.1093/ajcn/51.2.241](https://doi.org/10.1093/ajcn/51.2.241)

### 3. 공기밀도 공식 - ISA (International Standard Atmosphere)

```
ρ = (1.293 - 0.00426 × T) × exp(-h × 0.709 / 7000)
```

- `1.293 kg/m³`: 0°C 해수면 표준 공기밀도
- `0.00426`: 온도 계수 (약 -0.33%/°C)
- `7000/0.709 ≈ 9873m`: 대기 스케일 높이

**출처:**
> ISO 2533:1975 "Standard Atmosphere"

### 4. 사이클링 파워 방정식

```
P = v × (F_gravity + F_rolling + F_aero) / η_drivetrain
```

- **중력 저항**: `F_gravity = m × g × grade`
- **구름 저항**: `F_rolling = m × g × Crr`
- **공기 저항**: `F_aero = 0.5 × ρ × CdA × v²`

**출처:**
> Martin JC, et al. "Validation of a mathematical model for road cycling power"  
> Journal of Applied Biomechanics. 1998;14(3):276-291

### 5. Newton-Raphson Method

비선형 방정식 `f(v) = 0`의 근을 찾는 수치해석 방법입니다.

```
v_new = v - f(v) / f'(v)
```

**출처:**
> Press WH, et al. "Numerical Recipes: The Art of Scientific Computing"  
> Cambridge University Press

### 6. CdA 역산 공식

파워와 속도가 주어졌을 때 CdA를 역산하는 공식입니다.

```
CdA = ((P × η - v × m × g × (grade + Crr)) / (0.5 × ρ × v³)) × 2
```

---

## 데이터베이스 테이블

### riduck_user_extrainfo

사용자 추가 정보를 저장하는 테이블입니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `user_id` | int | 사용자 ID (PK) |
| `ftp` | int | FTP (W) |
| `weight` | float | 체중 (kg) |
| `pdc_json` | text | 파워 커브 데이터 (JSON) |
| `bikeKit_json` | text | 바이크 키트 설정 (JSON) |

### riduck_bike_kit

바이크 키트 설정을 저장하는 테이블입니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `user_id` | int | 사용자 ID |
| `gender` | char(1) | 성별 |
| `rider_height` | float | 키 (cm) |
| `rider_weight` | float | 체중 (kg) |
| `bike_type` | varchar | 자전거 유형 |
| `bike_weight` | float | 자전거 무게 (kg) |
| `tire_product` | int | 타이어 제품 ID |
| `drivetrain` | varchar | 구동계 |
| `tire_width` | int | 타이어 폭 |
| `rim_height` | int | 림 높이 (mm) |
| `cadence` | int | 케이던스 (rpm) |
| `rider_pose` | int | 라이딩 자세 |
| `crr` | float | 구름저항계수 |
| `cda` | float | 공기저항면적 |
| `surface_select` | int | 노면 상태 |
| `updated_at` | datetime | 수정 시각 |

### riduck_gears

사용자 장비 정보를 저장하는 테이블입니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `user_id` | int | 사용자 ID |
| `gear_id` | varchar | 장비 ID |
| `gear_primary` | tinyint | 주요 장비 여부 |
| `gear_name` | varchar | 장비 이름 |
| `bike_kit_json` | text | 바이크 키트 설정 (JSON) |

---

## 사용 예시

### 1. 속도 → 파워 계산

```bash
curl -X POST "https://api.riduck.com/json-api/get-simulation.php" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d "result_select=speedToPower" \
  -d "avg_speed=30" \
  -d "rider_weight=70" \
  -d "bike_weight=8" \
  -d "cda=0.32" \
  -d "crr=0.004" \
  -d "temperature=20" \
  -d "altitude=100"
```

### 2. 파워 → 속도 계산

```bash
curl -X POST "https://api.riduck.com/json-api/get-simulation.php" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d "result_select=powerToSpeed" \
  -d "avg_power=200" \
  -d "distance=40" \
  -d "elevation=500" \
  -d "rider_weight=70" \
  -d "bike_weight=8" \
  -d "cda=0.32" \
  -d "crr=0.004"
```

### 3. CdA 추정

```bash
curl -X POST "https://api.riduck.com/json-api/get-simulation.php" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d "result_select=estimateCdA" \
  -d "avg_power=200" \
  -d "avg_speed=35" \
  -d "rider_weight=70" \
  -d "bike_weight=8" \
  -d "crr=0.004" \
  -d "temperature=20" \
  -d "altitude=100"
```

---

## 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | - | 초기 버전 |

---

## 관련 파일

- `/json-api/get-simulation.php` - 메인 시뮬레이션 API (인증 필요)
- `/json-api/get-simulation-open.php` - 공개 시뮬레이션 API
- `/json-api/bikekit.php` - 바이크 키트 관리 API
- `/json-api/power_curve_model.php` - 파워 커브 모델 데이터
- `/riduck-api-common.php` - 공통 인증/유틸리티

---

## 문의

기술적인 문의사항은 개발팀에 문의해주세요.

