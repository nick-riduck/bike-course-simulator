# [PRO-799] FE: React 프로젝트 환경 구성 및 Zustand 스토어 설계

## 🎯 목표
React(Vite) 기반의 프론트엔드 프로젝트를 초기화하고, 전역 상태 관리(Zustand) 및 GPX 데이터 파싱 구조를 수립한다.

## ✅ To-Do List
- [x] Vite + React 프로젝트 생성 (`frontend/`)
- [x] Tailwind CSS (Riduck Theme) 설정
- [x] `zustand` 라이브러리 설치 및 `useCourseStore` 설계
- [x] `fast-xml-parser` 설치 및 GPX 로딩 로직(`GpxLoader`) 이식 (백엔드 `upload_gpx`와 연동 완료)
- [x] 상태 구조 정의:
    - `gpxData`: 트랙 포인트 배열 (lat, lon, ele, dist)
    - `segments`: 구간 정보 배열 (start_dist, end_dist, target_power)
    - `riderProfile`: 라이더 정보 (weight, ftp)

## 🏁 Definition of Done (DoD)
- [x] GPX 파일을 업로드하면 파싱된 데이터가 Zustand 스토어에 저장되어야 한다.
- [x] 저장된 데이터가 콘솔 로그에 정상적으로 출력되어야 한다.

**Status:** DONE (2026-01-28)