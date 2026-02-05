# [PLAN] 물리 엔진 정밀 검증 (Physics Kernel Validation)

## 1. 개요 (Overview)
본 문서는 현재 프로젝트의 물리 엔진(`Work-Energy` 방식, 이산화 계산)이 수학적 참값(`ODE Solver`, 연속 계산)과 비교했을 때 얼마나 정확한지 검증하고, 특히 **다운힐 브레이크(Soft Wall)** 및 **고토크/저속** 구간에서의 오차를 정량화하기 위한 구체적인 실행 계획을 기술한다.

## 2. 목표 (Goal)
- **정밀도 검증:** 기존 엔진의 20m 청킹 방식이 수학적 미분방정식 해와 비교하여 오차가 허용 범위 내인지 확인.
- **특이점 점검:** 50km/h 이상 고속 구간(브레이크 로직) 및 저속 구간(Walking Mode)에서의 동작 무결성 확인.
- **실전 데이터 검증:** 실제 GPX 데이터를 사용하여 복합적인 지형 변화에서도 누적 오차가 발생하지 않음을 증명.

## 3. 비교 방법론 (Methodology)

### A. 비교 대상
1.  **Legacy Kernel (Target):**
    - `src/physics_engine.py` (또는 v5) 내부의 단위 물리 계산 로직 (`_solve_segment_physics`).
    - 방식: 에너지 보존 법칙 (`Work_net = ΔKE`) + 20m 이산화(Discretization).
2.  **ODE Validator (Ground Truth):**
    - `scipy.integrate.solve_ivp` (Runge-Kutta 45) 사용.
    - 방식: 뉴턴 제2법칙 ($F=ma$) 미분방정식을 직접 적분.

### B. 허용 오차 기준 (Acceptance Criteria)
- **속도 오차:** `±0.1 km/h` (또는 `±0.03 m/s`) 이내.
- **시간 오차:** 1km 주행 시 `±0.1초` 이내.

## 4. 테스트 케이스 설계 (Test Cases)

물리 엔진이 오류를 범하기 쉬운 5가지 기초 케이스와 1가지 실전 케이스를 선정한다.

| Case | 상황 | 입력 조건 (예시) | 검증 목적 |
|:---:|:---|:---|:---|
| **1** | **평지 가속** | 0% 경사, 200W, 초기속도 30km/h, 1km | 기본적인 공기저항/구름저항 수식 일치 여부 |
| **2** | **급경사 업힐** | 10% 경사, 300W, 초기속도 10km/h, 500m | 저속/고토크 상황에서 중력 계산 정확도 |
| **3** | **고속 다운힐 (No Brake)** | -3% 경사, 0W, 초기속도 40km/h, 1km | 50km/h 미만에서의 순수 가속(중력 vs 공기저항) 검증 |
| **4** | **초고속 다운힐 (With Brake)** | -10% 경사, 0W, 초기속도 60km/h, 1km | **핵심:** 50km/h 초과 시 `Soft Wall` 브레이크 로직 작동 여부 |
| **5** | **극저속 (Walking)** | 15% 경사, 100W, 초기속도 3km/h, 100m | 걷기 속도(Walking Speed) 보정 로직 및 발산 방지 확인 |
| **6** | **Real World GPX** | `Namsan1_7.gpx` (1km~2km 구간) | 실제 지형에서의 누적 오차(Cascading Error) 확인 |

## 5. 실행 계획 (Execution Plan)

### Step 1. 검증 도구 구현 (`tools/ode_validator.py`)
- `scipy` 라이브러리를 활용하여 미분방정식 정의 및 솔버 구현.
- `PyfunValidator` 클래스 내에 `get_exact_final_speed` 메서드 작성.
- 브레이크 로직(Soft Wall) 및 토크 제한 로직을 수식적으로 포함.

### Step 2. 비교 스크립트 작성 (`tools/check_physics_accuracy.py`)
- **Unit Test Mode:** 위 Case 1~5를 순차적으로 실행하여 `Legacy vs ODE` 결과 표 출력.
- **Real World Mode:** 
    1. `GpxLoader`로 실제 코스 로딩.
    2. 기존 엔진으로 시뮬레이션 수행 -> `SimulationResult` 획득.
    3. 동일한 코스를 Validator로 세그먼트별 연속 적분 수행.
    4. 각 지점별 속도 차이를 계산하여 `Max Error` 및 `Avg Error` 도출.

### Step 3. 분석 및 조치
- 스크립트 실행 결과, 허용 오차를 초과하는 케이스 발생 시:
    - 물리 상수의 불일치(공기밀도, 구름저항 계수 등) 확인.
    - 이산화 간격(Step Size)에 따른 오차인지 확인.
    - 필요 시 기존 엔진 로직 수정 (`fix`).
