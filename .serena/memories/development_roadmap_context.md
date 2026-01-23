# 차세대 시뮬레이터 개발을 위한 핵심 기술 문맥 (Context)

## 1. 3D 시각화 핵심 노하우 (Curtain Wall)
- **문제:** `PolygonLayer`나 `TriangleLayer`는 완벽한 수직 면(Vertical Wall)일 경우 XY 평면 투영 면적이 0이 되어 렌더링 엔진이 이를 무시함.
- **해결책 (Epsilon Hack):** 상단 정점(Vertex) 좌표에 아주 미세한 오프셋(예: `0.00001`)을 더해 강제로 면적을 확보해야 함.
- **레이어 설정:** `extruded=True`, `get_elevation=0.1` 설정을 통해 3D 공간에서의 부피감과 마우스 피킹(Picking) 감도를 확보함.

## 2. 프론트엔드 (FE) 아키텍처 가이드
- **Stack:** React 18+ (Vite), Zustand, Deck.gl, Recharts.
- **Zustand State:** 코스 데이터(GPX 점들), 세그먼트 리스트, 라이더 정보, 시뮬레이션 결과를 전역 상태로 관리.
- **Interactions:**
    - 고도표(Recharts)에서 드래그하여 여러 세그먼트 병합 (Merge).
    - 고도표 특정 지점 클릭 시 세그먼트 분할 (Split).
    - 3D 지도와 고도표 간의 커서 동기화 (Hover Sync).

## 3. 백엔드 및 물리 엔진
- **API Framework:** FastAPI.
- **Core Logic:** `src/physics_engine.py`의 물리 법칙(공기저항, 중력 등)을 그대로 이관.
- **Sim Specs:** 초 단위 시뮬레이션을 수행하여 `dist_km`, `ele`, `speed_kmh`, `power`, `w_prime`, `time_sec` 등을 포함한 JSON 배열 반환.

## 4. 프로젝트 관리 (Jira)
- **Epic:** [PRO-742] 사이클링 시뮬레이터 물리 엔진 및 GPX 처리 고도화.
- **Priority:** 시뮬레이션 정확도 검증 > 3D 시각화 > 인터랙티브 편집 > 날씨 데이터(후순위).
