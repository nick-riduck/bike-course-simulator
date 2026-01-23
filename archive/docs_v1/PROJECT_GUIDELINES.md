# Project Guidelines & Roadmap

## 🛑 Operational Rules (Critical)

1.  **NO Arbitrary Code Generation:** Do not write or modify code unless explicitly instructed by the user or after a plan has been approved.
2.  **Documentation First:** Always finalize documentation, specifications, and plans *before* proceeding to code implementation.
3.  **Jira Driven:** Development follows the tasks defined in Jira.
4.  **Confirm Assumptions:** Do not make broad assumptions about file contents or user intent; verify with `read_file` or asking the user.

---

## 📅 Jira Roadmap (Cycle Simulator Enhancement)

### Epic: [PRO-742] 사이클링 시뮬레이터 물리 엔진 및 GPX 처리 고도화
**Goal:** GPX 경로의 지형적 특성, 실시간 기상 데이터(풍향/풍속), 팩라이딩 효과, 관성 모델을 결합하여 현실적인 완주 시간(PR)을 예측하는 엔진 개발.

#### Sub-tasks

1.  **[PRO-743] WeatherClient 구현 (Priority: 1)**
    *   **Description:** Open-Meteo API 연동, 위도/경도/시간 기반 기상 데이터(풍속, 풍향, 기온) 조회.
    *   **Status:** To Do
    *   **Key Features:**
        *   Open-Meteo API Client (No Auth).
        *   Inputs: Lat, Lon, ISO 8601 Timestamp.
        *   Outputs: Wind Speed, Wind Direction, Temperature.
        *   Support for manual weather override (Scenario Mode).

2.  **[PRO-744] GpxLoader 구현**
    *   **Description:** GPX 파싱 및 가변 세그먼트 압축.
    *   **Status:** To Do
    *   **Key Features:**
        *   XML Parsing & Track Point extraction.
        *   Preprocessing: Elevation Smoothing (Moving Average).
        *   **Adaptive Segmentation:**
            *   Trigger 1: Grade change > 0.5%
            *   Trigger 2: Heading change > 15 degrees

3.  **[PRO-745] PhysicsEngine 고도화**
    *   **Description:** 벡터 풍향, 관성, 드래프팅 적용.
    *   **Status:** To Do
    *   **Key Features:**
        *   Vector Wind Logic: $V_{eff} = V_{wind} \times \cos(\theta_{wind} - \theta_{road})$
        *   Inertia Model: Carry over exit velocity to next segment.
        *   Drafting: Effective CdA reduction (e.g., -30%).

4.  **[PRO-746] CLI 통합 개발**
    *   **Description:** 시뮬레이터 파이프라인 연결.
    *   **Status:** To Do
    *   **Key Features:**
        *   CLI Arguments parsing (argparse).
        *   Pipeline: Input -> GpxLoader -> WeatherClient -> PhysicsEngine -> Result.
