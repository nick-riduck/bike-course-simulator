# Valhalla Optimization Strategy: Route-Only Pipeline (Traceless Mode)

## Current Issues with Trace Attributes
The current implementation uses Valhalla's `/trace_attributes` (Map Matching) API. While accurate for well-defined GPS traces, it struggles with:
1. **Large Gaps:** Sparse GPX points (e.g., 1km apart) cause matching failures.
2. **Chunking Artifacts:** Splitting long routes results in discontinuities or "jumps" at boundaries.
3. **Detours:** Even with high `gps_accuracy`, the matching engine sometimes snaps to adjacent roads or takes detours, deviating from the intended GPX path.

## Proposed Solution: Route-Only Pipeline
Instead of asking Valhalla to *match* the points (`trace`), we ask it to *connect* the points (`route`).

### Workflow
1. **Simplified Input:** Take the GPX points. If too many, simplify using Ramer-Douglas-Peucker algorithm to keep only key waypoints (turns).
2. **Route Calculation:** Call Valhalla `/route` API with `shape_match: map_snap`.
   - Pass the waypoints as `locations` (via points).
   - Valhalla returns the optimal path geometry connecting these points.
   - **Benefit:** The result is a continuous, topologically correct road geometry. No jumps, no disconnects.
3. **Bulk Elevation:** Use the returned geometry (shape) to call `/height` API and get elevations for every point.
4. **No Stitching:** Since `/route` can handle fairly long lists of locations (or can be chunked more easily by legs), complex stitching logic is minimized.

### Pros
- **Guaranteed Connectivity:** No jumps or gaps.
- **Performance:** `/route` is generally faster than map matching.
- **Robustness:** Handles sparse data naturally.

### Cons
- **Metadata Loss:** We lose detailed edge attributes like `surface`, `grade` (though grade can be calculated), `speed_limit`, etc., which `trace_attributes` provides.
- **Strict Adherence:** If the user *actually* went off-road or took a non-optimal path that Valhalla thinks is "wrong", `/route` might force the "correct" road path.

### Implementation Draft
```python
def get_route_only_course(self, waypoints):
    # 1. Route
    payload = {
        "locations": waypoints, # [{"lat":..., "lon":...}, ...]
        "costing": "auto",
        "directions_options": {"units": "km"}
    }
    resp = requests.post(f"{self.url}/route", json=payload)
    shape = decode_polyline(resp.json()['trip']['legs'][0]['shape'])
    
    # 2. Elevation
    elevations = self._get_bulk_elevations(shape)
    
    # 3. Construct Standard Format
    return {
        "points": {
            "lat": [p[0] for p in shape],
            "lon": [p[1] for p in shape],
            "ele": elevations,
            # ... calculate dist, grade ...
        }
    }
```
