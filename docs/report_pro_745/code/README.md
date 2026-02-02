# Physics Engine Verification Code

[PRO-745] 물리 엔진 정밀도 검증 보고서에 사용된 실험 재현 코드입니다.

## 파일 구성
* `common.py`: 라이더, 파라미터, 세그먼트 데이터 클래스 (프로젝트 `src/`에서 발췌)
* `engine_core.py`: 신규 물리 엔진 (`src/physics_engine.py`)의 핵심 로직 (20m Chunking)
* `validator.py`: 미분방정식 정밀 적분 검증기 (Ground Truth)
* `run_experiment_1.py`: [실험 1] 알고리즘 정밀도 및 구간 처리 로직 검증 스크립트

## 실행 방법

1. 의존성 설치
```bash
pip install -r requirements.txt
```

2. 실험 1 실행 (단일 구간 정밀도)
```bash
python run_experiment_1.py
```
