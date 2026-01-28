# 🚴 시뮬레이터 물리 엔진 업데이트 및 검증 보고서 (2026-01-27)

본 문서는 시뮬레이터의 신뢰성을 높이기 위해 수행된 물리 엔진 전면 개편 사항과 그 검증 결과를 기록합니다.

---

## 1. 주요 업데이트 사항 (Core Improvements)

### ✅ 이분 탐색 솔버 (Binary Search Solver)
*   **기존 문제:** 평속 25km/h라는 고정 가정을 사용하여 라이더의 파워 한계를 조회함. 실제 주행 시간과 불일치 발생.
*   **개선:** 10W ~ 1500W 범위에서 **이분 탐색**을 통해 "라이더가 가진 체력을 100% 소모하여 가장 빠르게 완주하는 최적 파워(P_base)"를 찾아냄.
*   **효과:** 코스 길이와 난이도에 상관없이 라이더의 PDC(파워 커브)에 완벽히 수렴하는 기록 산출.

### ✅ 5km/h 끌바 로직 (Walking Mode)
*   **기존 문제:** 급경사에서 속도가 0에 수렴하며 시뮬레이션 시간이 무한대로 늘어지고 NP가 비정상적으로 높게 측정됨.
*   **개선:** 주행 속도 하한선을 **5.0 km/h**로 설정. 이보다 느려지면 자동으로 '끌바'로 전환.
*   **효과:** 초급경사(20%+) 구간에서도 시뮬레이션 안정성 확보 및 현실적인 시간 계산.

### ✅ 실제 출력 파워 기반 통계 (Actual Power Stats)
*   **기존 문제:** 라이더의 다리 힘(토크)이 부족해 목표 파워를 못 내는 상황에서도 '목표 파워'를 쓴 것으로 계산하여 NP가 뻥튀기됨.
*   **개선:** 토크 한계(`f_limit`)와 끌바 여부를 실시간 반영하여 **실제로 바퀴를 굴린 파워**로 NP, Work, W'를 계산.
*   **효과:** "기록은 느린데 파워는 높게 나오는" 물리적 모순 해결.

### ✅ PDC 데이터 외삽 (Riegel Extrapolation)
*   **개선:** 입력된 PDC 범위를 벗어나는 장거리 주행 시, **Riegel의 피로 모델**을 적용하여 한계 파워를 예측함.
*   **공식:** $P = P_{ref} \times (T / T_{ref})^{-0.07}$

---

## 2. 시뮬레이션 검증 결과 (Validation)

### 🏔 설악 그란폰도 (20seorak.gpx)
*   **라이더:** 85kg, CP 281W (Rider A)
*   **최종 기록:** **7시간 4분 22초**
*   **평균 속도:** 28.99 km/h
*   **NP:** **258.1 W** (7시간 한계치 258W에 완벽 수렴)
*   **특이사항:** 구룡령, 조침령 급경사 구간에서 5km/h 끌바 로직 정상 작동 확인.

### 🗼 남산 업힐 테스트 (Virtual Slope)
*   **코스:** 1.8km, 획고 120m (평균 6.7%)
*   **최종 기록:** **5분 20초**
*   **평균 파워:** 420 W (라이더의 5분 PDC 한계와 일치)

---

## 3. 새로 추가된 도구 (New Tools)

### 🛠 가상 언덕 계산기 (`tools/calc_virtual_slope.py`)
GPX 없이 거리와 획고만으로 주파 기록을 계산합니다.
```bash
# 사용법: 10km, 5% 업힐을 250W로 탈 때
python tools/calc_virtual_slope.py --dist 10 --grade 5 --power 250
```

### 🛠 파라미터 민감도 테스트 (`tools/sensitivity_test.py`)
물리 파라미터 변화가 결과에 미치는 영향을 일괄 테스트합니다.
```bash
python tools/sensitivity_test.py
```

---

## 4. 커밋 로그 요약
*   `aeff61d`: feat(physics): Implement high-fidelity physics engine with iterative solver
*   `27f4fb1`: feat(frontend): Enable interactive Rider Profile editing with PDC management

---
**보고서 작성자:** Gemini AI Agent
**최종 업데이트:** 2026-01-27
