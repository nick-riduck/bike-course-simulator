# Database Schema Design: Routes & Segments

## 1. 개요 및 서비스 목표
이 문서는 **GPX 코스 생성기 및 물리 시뮬레이터**의 핵심인 코스(Route)와 구간(Segment) 데이터를 정의합니다.

### 🎯 서비스 목표 (Service Goals)
1.  **코스 탐색:** "내 집 앞을 지나가는 코스"나 "한강을 따라가는 코스"를 지도 기반으로 쉽게 찾을 수 있어야 합니다.
2.  **워크아웃 발견:** "내 주변 5km 이내에 있는 **평균 경사도 7% 이상의 업힐**"을 검색하여 시뮬레이션하거나 훈련할 수 있어야 합니다.
3.  **정밀 시뮬레이션:** 단순한 GPX 재생이 아닌, **20m 단위의 미세한 지형 변화(낙타등), 노면 상태, 풍향/풍속**을 반영한 물리 시뮬레이션을 제공해야 합니다.
4.  **표준화된 경쟁:** 사용자가 임의로 자른 구간이 아닌, **"남산", "북악" 등 표준화된 구간(Standard Segments)** 위에서 기록과 파워 데이터를 비교할 수 있어야 합니다.

---

## 2. 기술적 의사결정 (Technical Decisions)

### 2.1 Hybrid Storage Strategy (DB vs File)
대용량 공간 데이터 처리에 따른 DB 부하를 최소화하면서도 검색 성능을 극대화하기 위해 **이원화된 저장 방식**을 채택했습니다.

| 구분 | 저장 위치 | 데이터 내용 | 이유 (Why) |
| :--- | :--- | :--- | :--- |
| **검색/메타** | **PostgreSQL (PostGIS)** | 코스 개요, 단순화된 선(LineString), 시작점(Point), 태그 | 공간 인덱스(GiST)를 활용한 실시간 위치 기반 검색("내 주변 찾기") 지원. |
| **상세/연산** | **File Storage (JSON)** | **Valhalla Refined Data** (20m 단위 정밀 좌표, 고도, 경사도, 노면 타입) | 수십만 개의 좌표 데이터를 RDB에 넣는 오버헤드 제거. 시뮬레이터는 파일만 읽어서 연산 수행. |

### 2.2 Valhalla Data Enrichment (데이터 정제 및 표준화)
외부 GPX(가민, 스트라바 등)와 자체 생성 GPX 간의 데이터 품질 격차를 해소하고 정밀 시뮬레이션을 수행하기 위해, **모든 입력 데이터는 Valhalla Map Matching 과정을 거쳐 저장**됩니다.
*   **Process:** `Raw GPX Upload` -> `Valhalla Trace Attributes API` -> `Map Matching & DEM Elevation` -> `Refined JSON Save`
*   **Benefit:** 노면 상태(Surface), 도로 등급, 정확한 경사도 정보를 획득하여 물리 엔진의 정확도 향상.

### 2.3 Standard Segments (표준 구간 모델)
데이터 파편화를 막기 위해, 세그먼트를 코스에 종속시키지 않고 **독립적인 마스터 데이터**로 관리합니다.
*   **AS-IS:** 코스 A에 포함된 남산 vs 코스 B에 포함된 남산이 서로 다름. (비교 불가)
*   **TO-BE:** `Segments` 테이블에 '남산'을 정의하고, 코스들은 이를 참조(N:M)함. (데이터 표준화)

---

## 3. Schema Definition

### 3.1 Routes (코스 메타데이터)
**역할:** 코스 목록, 검색, 공유의 단위.

```sql
CREATE TABLE routes (
    -- [PK] 내부 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- [Unique] URL 공유용 짧은 ID (예: ridingazua.cc/c/12345)
    route_num SERIAL UNIQUE NOT NULL,

    -- 작성자 (Users FK)
    user_id UUID NOT NULL REFERENCES users(id),

    -- 기본 정보
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- [Storage] 상세 데이터 파일 경로 (S3 Key or Local Path)
    -- 내용: full_path(20m 단위 좌표), control_points(편집용 웨이포인트)
    data_file_path TEXT NOT NULL,

    -- [Spatial] 검색 최적화 지리 정보 (PostGIS)
    -- 1. 내 주변을 '지나가는' 코스 검색용 (단순화된 LineString)
    summary_path GEOMETRY(LineString, 4326),
    -- 2. 지도 로딩 시 핀 표시 및 출발지 검색용
    start_point GEOMETRY(Point, 4326),

    -- 통계 정보
    distance INTEGER NOT NULL,          -- 총 거리 (meters)
    elevation_gain INTEGER NOT NULL,    -- 획득 고도 (meters)
    
    -- 서비스 지표
    view_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    visibility VARCHAR(20) DEFAULT 'public', -- 'public', 'private', 'link_only'

    -- 메타 데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index: 공간 검색 속도 향상
CREATE INDEX idx_routes_summary_path ON routes USING GIST (summary_path);
CREATE INDEX idx_routes_start_point ON routes USING GIST (start_point);
```

### 3.2 Segments (표준 구간 정보)
**역할:** "남산", "북악" 등 공통으로 사용되는 표준 구간 정의. 워크아웃 검색의 대상.

```sql
CREATE TABLE segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 최초 등록자 (관리자 또는 유저)
    creator_id UUID REFERENCES users(id),

    -- 구간 정보
    name VARCHAR(100) NOT NULL,          -- 예: "남산 타워 업힐"
    type VARCHAR(50) NOT NULL,           -- 'UPHILL', 'SPRINT', 'ROLLING'
    
    -- [Spatial] 표준 경로 및 검색 지점
    geometry GEOMETRY(LineString, 4326), -- 표준 경로 (Map Matching 기준)
    start_point GEOMETRY(Point, 4326),   -- "내 주변 업힐 찾기" 검색용

    -- 구간 통계 (표준 기준)
    length INTEGER NOT NULL,             -- m
    avg_grade FLOAT NOT NULL,            -- %
    elevation_gain INTEGER NOT NULL,     -- m
    
    -- 신뢰도 관리
    is_verified BOOLEAN DEFAULT FALSE,   -- 공식 인증 여부

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index: 내 주변 워크아웃(업힐) 검색용
CREATE INDEX idx_segments_start_point ON segments USING GIST (start_point);
```

### 3.3 RouteSegments (코스-세그먼트 연결)
**역할:** "이 코스에는 어떤 업힐들이 포함되어 있는가?"를 정의하는 N:M 연결 테이블.
**중요:** 단순 연결뿐만 아니라, **해당 코스 내에서의 위치(Index)** 정보를 포함하여 시뮬레이터가 구간 진입/이탈을 인식할 수 있게 합니다.

```sql
CREATE TABLE route_segments (
    route_id UUID REFERENCES routes(id) ON DELETE CASCADE,
    segment_id UUID REFERENCES segments(id) ON DELETE CASCADE,
    
    -- 정렬 순서 (1번째 업힐, 2번째 업힐...)
    sequence INTEGER NOT NULL,
    
    -- [Slicing] 전체 코스 데이터(JSON) 내에서의 위치 정보
    -- 이 정보를 이용해 서버는 별도 파일 없이도 구간 GPX를 실시간 생성 가능
    start_index INTEGER NOT NULL, 
    end_index INTEGER NOT NULL,

    PRIMARY KEY (route_id, segment_id)
);
```

---

## 4. 태그 및 다국어 지원 (Tags & I18N)
해외 서비스 확장을 고려하여 **JSONB 기반의 다국어 태그 시스템**을 도입합니다.

### 4.1 Tags (태그 마스터)
```sql
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    
    -- 다국어 이름 저장 (JSONB)
    -- 예: {"ko": "한강", "en": "Han River", "jp": "漢江"}
    names JSONB NOT NULL,
    
    -- 관리 및 코드 참조용 영문 키워드 (URL Slug 등으로 활용)
    -- 예: 'han-river', 'uphill', 'night-ride'
    slug VARCHAR(50) UNIQUE NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index: JSONB 내부 값 검색을 위한 GIN 인덱스
CREATE INDEX idx_tags_names ON tags USING GIN (names);
```

### 4.2 RouteTags (코스-태그 연결)
```sql
CREATE TABLE route_tags (
    route_id UUID REFERENCES routes(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    
    PRIMARY KEY (route_id, tag_id)
);
```

---

## 5. 데이터 파일 구조 (Data File Structure)
`routes.data_file_path`에 저장되는 실제 물리 파일(JSON)의 구조입니다. 이 파일은 **Valhalla Trace API를 통해 정제된 표준 시뮬레이션 및 지도 렌더링용 데이터**입니다.

```json
{
  "version": "1.0",
  "meta": {
    "creator": "Riduck Engine",
    "surface_map": {
      "0": "unknown", "1": "asphalt", "2": "concrete", 
      "3": "wood_metal", "4": "paving_stones", "5": "cycleway", 
      "6": "compacted", "7": "gravel_dirt"
    }
  },
  "stats": {
    "distance": 2500.5,      // 총 거리 (m)
    "ascent": 152,           // 총 획득고도 (m)
    "descent": 10,           // 총 하강고도 (m)
    "points_count": 1250,    // 전체 포인트 수
    "segments_count": 45     // 생성된 세그먼트 수
  },
  
  // 1. 점 데이터 (지도 렌더링 & 고해상도 차트용)
  // Columnar 포맷으로 용량 최적화 및 프론트엔드 연산 부하 감소
  "points": {
    "lat": [37.123456, ...],  // 위도
    "lon": [127.123456, ...], // 경도
    "ele": [50.5, ...],       // 고도 (m)
    "dist": [0.0, 15.2, ...], // 누적 거리 (m)
    "grade": [0.5, 0.5, ...], // 순간 경사도 (지도 색상용)
    "surf": [1, 1, ...]       // 노면 ID (meta.surface_map 참조)
  },

  // 2. 물리 엔진용 요약 구간 (Simulation Atomic Segments)
  // 시뮬레이터는 points를 순회하지 않고 이 segments 데이터만 보고 즉시 계산 수행
  "segments": {
    "p_start": [0, 15, ...],   // points 리스트 내 시작 인덱스
    "p_end": [15, 32, ...],    // points 리스트 내 끝 인덱스
    "length": [240.5, 120.0, ...], // 구간 길이 (m)
    "avg_grade": [0.052, ...], // 구간 평균 경사도 (소수점)
    "surf_id": [1, 5, ...],    // 구간 노면 ID
    "avg_head": [180.5, ...]   // 구간 평균 방위각 (degrees)
  },
  
  // 3. 코스 생성기 편집용 데이터 (Waypoints)
  "control_points": [
    {"lat": 37.5, "lon": 127.0, "type": "start"},
    {"lat": 37.6, "lon": 127.1, "type": "end"}
  ]
}
```
```

---

## 6. GPX/TCX Export Strategy (파일 변환 전략)
사용자가 속도계(Garmin, Wahoo 등)에 코스를 넣기 위해 다운로드를 요청할 때의 처리 방식입니다.

### 6.1 포맷 정의 (Domain Context)
*   **GPX (GPS Exchange Format):** 위치(위도, 경도, 고도) 정보를 담은 가장 범용적인 XML 표준입니다. 대부분의 기기에서 호환되지만, 경로 안내 정보(Turn-by-turn)나 구간 정보는 포함되지 않는 경우가 많습니다.
*   **TCX (Training Center XML):** 가민(Garmin)에서 만든 트레이닝 특화 XML 포맷입니다. 경로뿐만 아니라 **"코스 포인트(Course Point)"** 기능을 지원하여, 라이딩 중 "남산 업힐 시작 500m 전" 같은 알림을 띄워줄 수 있습니다.

### 6.2 On-demand Conversion (실시간 변환)
별도의 GPX/TCX 파일을 서버에 미리 저장하지 않고, **요청 시점에 JSON 데이터를 변환하여 제공**합니다.

*   **Why?**
    1.  **단일 진실 공급원(Single Source of Truth):** JSON 데이터만 수정하면 다운로드 파일도 자동으로 최신화됨. (데이터 불일치 방지)
    2.  **스토리지 절약:** 중복된 좌표 데이터를 포맷별로 저장할 필요가 없음.
    3.  **Cloud Run 활용:** 변환 로직을 Serverless(Cloud Run)로 위임하여 트래픽 폭주 시에도 유연하게 확장 가능.

*   **Logic:**
    *   **GPX:** `full_path`의 좌표 데이터를 XML `<trkpt>` 태그로 단순 매핑.
    *   **TCX:** `full_path`의 좌표 데이터 변환 + **DB의 `route_segments` 정보를 조회하여 `<CoursePoint>` 태그(업힐 시작/종료 알림) 자동 삽입.** -> 사용자에게 "업힐 구간 안내"라는 부가가치 제공.

### 6.3 Sample Data (Format Reference)

#### GPX Sample (Standard)
```xml
<gpx version="1.1" creator="RideGazua">
  <trk>
    <name>남산 라이딩</name>
    <trkseg>
      <trkpt lat="37.5001" lon="127.0001">
        <ele>100.5</ele>
        <time>2026-02-03T10:00:00Z</time>
      </trkpt>
      <trkpt lat="37.5002" lon="127.0003">
        <ele>100.8</ele>
        <time>2026-02-03T10:00:05Z</time>
      </trkpt>
      <!-- ... -->
    </trkseg>
  </trk>
</gpx>
```

#### TCX Sample (With CoursePoints)
TCX는 아래와 같이 `CoursePoint`를 통해 업힐 시작/종료 지점을 기기에 알려줍니다.
```xml
<TrainingCenterDatabase>
  <Courses>
    <Course>
      <Name>남산 라이딩</Name>
      <Track>
        <Trackpoint>
          <Time>2026-02-03T10:00:00Z</Time>
          <Position>
            <LatitudeDegrees>37.5001</LatitudeDegrees>
            <LongitudeDegrees>127.0001</LongitudeDegrees>
          </Position>
          <AltitudeMeters>100.5</AltitudeMeters>
          <DistanceMeters>0.0</DistanceMeters>
        </Trackpoint>
        <!-- ... -->
      </Track>
      
      <!-- 핵심: 세그먼트 알림 기능 -->
      <CoursePoint>
        <Name>남산 업힐 시작</Name>
        <Time>2026-02-03T10:15:00Z</Time>
        <Position>
          <LatitudeDegrees>37.5500</LatitudeDegrees>
          <LongitudeDegrees>126.9900</LongitudeDegrees>
        </Position>
        <PointType>Summit</PointType> <!-- 업힐 아이콘 표시 -->
        <Notes>거리 1.8km, 평균 6%</Notes>
      </CoursePoint>
    </Course>
  </Courses>
</TrainingCenterDatabase>
```
