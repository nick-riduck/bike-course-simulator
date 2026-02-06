# Valhalla 최적화 전략: 경로 전용 파이프라인 (추적 없는 모드)

## 현재 Trace Attributes의 문제점
현재 구현은 Valhalla의 `/trace_attributes` (맵 매칭) API를 사용합니다. 이는 잘 정의된 GPS 추적에는 정확하지만, 다음과 같은 상황에서 어려움을 겪습니다:
1. **큰 간격:** 희소한 GPX 포인트(예: 1km 간격)는 매칭 실패를 유발합니다.
2. **청킹 아티팩트 (Chunking Artifacts):** 긴 경로를 분할할 때 경계 부분에서 불연속성이나 "점프" 현상이 발생합니다.
3. **우회로:** 높은 `gps_accuracy` 설정에도 불구하고, 매칭 엔진이 때때로 인접한 도로로 스냅(snap)하거나 우회로를 택하여 의도한 GPX 경로에서 벗어나는 경우가 있습니다.

## 제안된 해결책: 경로 전용 파이프라인
Valhalla에 포인트를 *매칭*(`trace`)하도록 요청하는 대신, 포인트를 *연결*(`route`)하도록 요청합니다.

### 워크플로우
1. **단순화된 입력:** GPX 포인트를 가져옵니다. 포인트가 너무 많으면 Ramer-Douglas-Peucker 알고리즘을 사용하여 주요 웨이포인트(회전 지점 등)만 남기고 단순화합니다.
2. **경로 계산:** `shape_match: map_snap` 옵션과 함께 Valhalla `/route` API를 호출합니다.
   - 웨이포인트를 `locations`(경유지)로 전달합니다.
   - Valhalla는 이 포인트들을 연결하는 최적의 경로 기하구조(geometry)를 반환합니다.
   - **장점:** 결과물은 연속적이고 위상적으로 정확한 도로 기하구조입니다. 점프나 끊김 현상이 없습니다.
3. **대량 고도 데이터:** 반환된 기하구조(shape)를 사용하여 `/height` API를 호출하고 모든 포인트의 고도를 가져옵니다.
4. **스티칭(Stitching) 불필요:** `/route`는 상당히 긴 위치 목록을 처리할 수 있으며(또는 구간별로 더 쉽게 나눌 수 있음), 복잡한 스티칭 로직을 최소화할 수 있습니다.

### 장점
- **연결성 보장:** 점프나 간격이 발생하지 않음.
- **성능:** 일반적으로 `/route`가 맵 매칭보다 빠름.
- **견고성:** 희소한 데이터를 자연스럽게 처리함.

### 단점
- **메타데이터 손실:** `trace_attributes`가 제공하는 `surface`(노면), `grade`(경사도, 계산은 가능함), `speed_limit`(속도 제한) 등 상세한 엣지 속성을 잃게 됩니다.
- **엄격한 준수:** 사용자가 *실제로* 오프로드로 주행했거나 Valhalla가 "틀렸다"고 판단하는 비최적 경로를 주행한 경우, `/route`는 이를 "올바른" 도로 경로로 강제할 수 있습니다.

### 구현 초안
```python
def get_route_only_course(self, waypoints):
    # 1. 경로 계산
    payload = {
        "locations": waypoints, # [{"lat":..., "lon":...}, ...]
        "costing": "auto",
        "directions_options": {"units": "km"}
    }
    resp = requests.post(f"{self.url}/route", json=payload)
    shape = decode_polyline(resp.json()['trip']['legs'][0]['shape'])
    
    # 2. 고도 데이터 가져오기
    elevations = self._get_bulk_elevations(shape)
    
    # 3. 표준 형식 생성
    return {
        "points": {
            "lat": [p[0] for p in shape],
            "lon": [p[1] for p in shape],
            "ele": elevations,
            # ... 거리, 경사도 등 계산 ...
        }
    }
```
