# Physics Engine Refactoring Plan (Hyperparameter Externalization)

## 🚨 Critical: Remove Hardcoded Magic Numbers
The following parameters are currently hardcoded in `src/physics_engine.py` and `src/physics_engine_v2.py`. They must be moved to `PhysicsParams` or `SimulationConfig` to ensure extensibility and transparency.

### 1. Physical Constants (PhysicsParams)
These values should be configurable via `rider_data.json` or run-time arguments.

| Parameter | Current Value | Description | Impact |
| :--- | :--- | :--- | :--- |
| `cda` | `0.30` | Coefficient of Drag * Area | Determines aero drag. Varies by rider position/size. |
| `crr` | `0.0045` | Coefficient of Rolling Resistance | Varies by tire type and road surface. |
| `bike_weight` | `8.0` / `8.5` | Bike mass (kg) | Should be explicit. Avoid hidden addition. |
| `drivetrain_loss` | `0.05` (5%) | Mechanical loss | Chain/bearing friction. Usually 2-4% for road bikes. |
| `air_density` | `1.225` | Air density (kg/m^3) | Varies by altitude/temp. Should link to Weather API. |
| `mu` | `0.8` | Tire Friction Coefficient | Limits cornering speed. 0.8 (Dry) vs 0.4 (Wet). |

### 2. Simulation Logic Parameters (Solver & Tuning)
These control the solver's behavior and pacing strategy.

| Parameter | Current Value | Description | Action |
| :--- | :--- | :--- | :--- |
| `v_current` (Start) | `0.1` m/s | Initial Velocity | Keep near-zero but avoid `0` (div-by-zero). |
| `solver_range_low` | `10.0` W | Binary Search Lower Bound | Make configurable for elite/novice ranges. |
| `solver_range_high` | `1500.0` W | Binary Search Upper Bound | |
| `alpha_climb` | `2.5` | Pacing Aggressiveness (Uphill) | Move to `PacingStrategy` config. |
| `alpha_descent` | `10.0` | Recovery Factor (Downhill) | Move to `PacingStrategy` config. |
| `beta_slow` | `0.6` | Asymmetric Tuning (Climb) | V2 Engine specific. |
| `beta_fast` | `1.5` | Asymmetric Tuning (Descent) | V2 Engine specific. |
| `v_ref_default` | `30.0` km/h | Reference Speed | Should be derived from `CP` or `Target Time`. |

### 3. Physiological & Safety Limits
Values related to human performance and safety constraints.

| Parameter | Current Value | Description | Action |
| :--- | :--- | :--- | :--- |
| `f_max_initial` | `1.5 * Weight * g` | Biomechanical Force Limit | Approx 1.5G. Verify with literature. |
| `decay_factor_exp` | `0.05` / `0.07` | Fatigue Decay Exponent | Riegel's formula exponent. Standardize to `0.07`. |
| `walking_speed` | `5.0` km/h | Min speed clamp (Hike-a-bike) | Should be a fallback, not a primary mode. |
| `walking_power` | `30.0` W | Metabolic cost of walking | Review metabolic cost tables (likely higher). |

## 🛠 Refactoring Roadmap

1.  **Phase 1: Structuring `PhysicsParams`**
    *   Update `PhysicsParams` dataclass to include all "Physical Constants".
    *   Remove default values in `__init__` to force explicit injection.

2.  **Phase 2: Config Loader Integration**
    *   Update `Rider` or `Course` loader to parse these values from JSON.
    *   Create a `SimulationConfig` object for Solver/Tuning parameters.

3.  **Phase 3: Dynamic Environment**
    *   Link `air_density` to elevation data (Barometric formula).
    *   Link `mu` (Friction) to Weather API (Rain/Snow).

4.  **Phase 4: UI Exposure**
    *   Allow users to tweak "Wet Road" or "Aero Position" in the Frontend.
