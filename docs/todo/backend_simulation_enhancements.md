# Backend Simulation Enhancements (Physics & Environment)

## 🎯 Objective
Enhance the realism of the simulation engine by incorporating external environmental data (Road Surface, Weather) rather than relying on global constants.

## ✅ To-Do List

### 1. Segment-specific CRR (Rolling Resistance)
Currently, `crr` is a global constant (0.0045 for asphalt). We need to vary this based on the actual road type.

*   **Data Source:** OpenRouteService (ORS) API or OpenStreetMap (OSM) Surface Tags.
*   **Implementation Steps:**
    *   [ ] Create a mapping table for Surface Type -> CRR.
        *   *Asphalt/Paved:* 0.003 ~ 0.005
        *   *Concrete:* 0.005 ~ 0.006
        *   *Compacted Gravel:* 0.008 ~ 0.012
        *   *Loose Gravel/Dirt:* 0.015+
        *   *Cobblestone:* 0.020+
    *   [ ] Update `GpxLoader` or a post-processing step to query surface data for track coordinates.
    *   [ ] Store `crr` in the `Segment` object.
    *   [ ] Update `PhysicsEngine` to use `seg.crr` instead of `params.crr` in the friction calculation.

### 2. Weather Integration (Wind Dynamics)
Integrate real (or scenario-based) wind data to calculate air resistance accurately per segment.

*   **Data Source:** OpenWeatherMap, VisualCrossing, or existing `WeatherClient`.
*   **Implementation Steps:**
    *   [ ] Enhance `WeatherClient` to support coordinate-based queries (or use a global vector for MVP).
    *   [ ] Calculate **Yaw Angle** (Effective Wind Angle) for each segment:
        *   `rel_angle = wind_direction - segment_heading`
    *   [ ] Calculate **Headwind Component**:
        *   `v_wind_effective = wind_speed * cos(rel_angle)`
    *   [ ] Update `PhysicsEngine._solve_segment_physics`:
        *   Pass `v_wind_effective` into the drag equation: `F_drag = 0.5 * rho * CdA * (v_rider + v_wind)^2`

---

## ⏳ Pending / Under Consideration
*Features currently on hold for further review.*

*   **User-Configurable Pacing (Alpha Climb):** Adjusting how aggressively the rider attacks hills based on rider type (Time Trialist vs. Climber).
*   **Endurance Factor (Riegel Exponent):** Adjusting the fatigue rate for long-distance simulations based on rider experience level.
