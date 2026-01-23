# [PRO-742] 차세대 바이크 코스 시뮬레이터 & 전략 에디터 명세서 (V2)

## 1. 개요 (Overview)
본 프로젝트는 GPX 경로 데이터를 기반으로 물리 법칙이 적용된 가상 라이딩 시뮬레이션을 수행하고, 사용자가 코스별 파워 전략을 수립할 수 있는 웹 기반 도구를 제작하는 것을 목표로 한다. 
기존 Streamlit 프로토타입에서 검증된 물리 엔진과 3D 시각화 기술을 React + FastAPI 환경으로 이관하여 실제 서비스 수준의 UX를 제공한다.

## 2. 핵심 기능 (Key Features)

### 2.1. 3D 코스 시각화 (Curtain Wall)
- **설명:** 지도 위에 코스의 고도 변화를 수직 벽(Curtain Wall) 형태로 시각화.
- **상세:** 
    - 경사도에 따른 색상 코딩 (업힐: 빨강, 평지: 초록, 다운힐: 파랑).
    - 3D 지형(Terrain)과 결합하여 코스의 고도감을 직관적으로 표현.
    - **기술:** `deck.gl` (PolygonLayer/TriangleLayer), `Mapbox GL JS`.

### 2.2. 인터랙티브 세그먼트 에디터 (Smart Editor)
- **설명:** 고도표(Elevation Profile) 상에서 마우스 조작만으로 구간을 분할하고 병합.
- **상세:**
    - **Auto-detection:** 경사도 변화에 따른 기본 구간 자동 생성.
    - **Drag-to-Merge:** 인접한 여러 구간을 드래그하여 하나로 합침.
    - **Click-to-Split:** 특정 지점을 클릭하여 구간을 세분화.
    - **Power Planning:** 구간별 목표 파워(W) 또는 FTP 비율(%) 설정.
- **기술:** `Recharts` 또는 `D3.js`.

### 2.3. 동적 날씨 시스템 (Dynamic Weather) - [Optional / Phase 4]
- **설명:** 주행 예정 일시의 날씨 예보를 시뮬레이션에 반영.
- **상세:**
    - 출발 시간 설정 시 해당 시간대의 풍향, 풍속, 기온 API 호출.
    - **시공간 매핑:** 라이더의 예상 위치별로 실시간 변화하는 바람 저항 계산.
    - *초기 단계에서는 무풍/표준 기온(20도)을 기본값으로 사용.*
- **기술:** `OpenWeatherMap API`.

### 2.4. 고도화된 물리 엔진 시뮬레이션
- **설명:** 공기 저항, 구름 저항, 중력, 바람, 라이더 무게 등을 종합 고려한 속도 예측.
- **상세:**
    - 초 단위 시뮬레이션 수행.
    - 결과 지표: 예상 완주 시간, AP(Average Power), NP(Normalized Power), IF(Intensity Factor), TSS.
    - **Bonking Alert:** 설정한 파워가 라이더의 능력치(PDC) 대비 과할 경우 경고 메시지 출력.

## 3. 기술 아키텍처 (Architecture)

### Frontend (React App)
- **Framework:** React 18+ (Vite)
- **State Management:** Zustand (가볍고 빠른 상태 전이)
- **Visualization:** Deck.gl (3D Map), Recharts (2D Chart)
- **Communication:** Axios (FastAPI와 통신)

### Backend (FastAPI Server)
- **Engine:** Python 기반 Physics Engine (`src/physics_engine.py`)
- **API Specs:**
    - `POST /simulate`: GPX + 라이더 데이터 + 날짜 -> 결과 JSON
    - `GET /weather`: 위치 + 시간 -> 풍향/풍속 데이터
- **Data Model:** Pydantic을 활용한 엄격한 스키마 정의

## 4. Jira 로드맵 (Roadmap)

본 프로젝트는 **[PRO-742] 에픽** 하위에서 관리하며, 다음 순서로 티켓을 발행하여 진행한다.

| 단계 | 티켓 요약 (Summary) | 주요 작업 내용 |
|:---:|:---|:---|
| **Phase 1** | [BE] 시뮬레이션 엔진 API화 | 기존 Python 로직을 FastAPI 엔드포인트로 전환 |
| **Phase 1** | [FE] React 프로젝트 스캐폴딩 | Vite 기반 프로젝트 세팅 및 Zustand 구조 설계 |
| **Phase 2** | [FE] 3D Map View 구현 | Deck.gl을 이용한 3D Curtain Wall 렌더링 |
| **Phase 2** | [FE] 인터랙티브 고도표 개발 | 구간 Split/Merge가 가능한 차트 컴포넌트 제작 |
| **Phase 3** | [FE] 파워 전략 입력 UI | 세그먼트별 파워 설정 및 시뮬레이션 실행 UI |
| **Phase 3** | [통합] 핵심 기능 검증 | 무풍 조건에서의 시뮬레이션 정확도 및 UX 검증 |
| **Phase 4** | [BE/FE] 동적 날씨 모듈 (Optional) | 날씨 API 연동 및 시뮬레이션 반영 |

---
*본 문서는 개발 진행 상황에 따라 수시로 업데이트됩니다.*
