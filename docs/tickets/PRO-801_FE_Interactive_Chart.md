# [PRO-801] FE: 인터랙티브 고도표 및 세그먼트 편집 로직 구현

## 🎯 목표
코스의 고도 변화를 그래프로 보여주고, 사용자가 그래프 상에서 구간을 선택/분할/병합할 수 있는 인터페이스를 제공한다.

## ✅ To-Do List
- [x] `chart.js` & `react-chartjs-2` 라이브러리 설치 (Recharts 대체)
- [x] `ElevationChart` 컴포넌트 구현
- [x] 3D 지도와 고도표 간 마우스 호버 싱크(Sync) 구현
- [x] 구간 편집 인터랙션:
    - [x] **Click-to-Split:** 차트 클릭 시 해당 지점에서 세그먼트 분할
    - [x] **Drag-to-Resize:** 세그먼트 경계 드래그하여 거리 조절
    - [x] **Drag-to-Merge:** (SegmentList에서 구현됨) 구간 선택 후 병합
- [x] 편집된 세그먼트 정보를 Zustand 스토어(`segments`)에 반영

## 🏁 Definition of Done (DoD)
- [x] 고도표에서 구간을 나누거나 합치면, 3D 지도상의 색상도 즉시 변경되어야 한다.
- [x] 편집된 세그먼트 정보가 GPX 메타데이터로 저장(Export) 가능해야 한다.

**Status:** DONE (2026-01-28)