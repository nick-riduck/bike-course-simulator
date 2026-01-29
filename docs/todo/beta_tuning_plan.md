# Beta Model Tuning Strategy

## 🎯 Objective
Refine the velocity-based pacing model (Beta Model) to address its instability at extreme speeds (steep climbs & fast descents) and improve flat-terrain cruising efficiency.

## 🛠 Tuning Methods

### 1. Deadzone (Speed Buffer)
Prevent power fluctuation during steady cruising.
*   **Logic:** If `abs(V - V_ref) < threshold`, set pacing factor to 1.0 (neutral).
*   **Target:** `20 ~ 30 km/h` range (assuming V_ref = 25km/h).

### 2. Asymmetric Beta (Split Weights)
Apply different sensitivities for slow (climbing) and fast (descending) scenarios.
*   **Beta_Slow:** Lower value (e.g., 0.5) to prevent power spikes on steep hills.
*   **Beta_Fast:** Higher value (e.g., 1.5 ~ 2.0) to encourage coasting/resting on descents.

### 3. Logarithmic Scaling
Use a log function instead of linear to dampen the response at extreme low speeds.
*   **Formula:** `Factor = 1.0 - Beta * ln(V / V_ref)`
*   **Effect:** Prevents power from doubling/tripling at 5km/h, providing a smoother ramp-up.

## ✅ Implementation Plan
1.  Update `PhysicsEngineV2` to support these parameters.
2.  Run `sensitivity_test.py` to compare:
    *   Linear Beta (Original)
    *   Deadzone + Asymmetric
    *   Logarithmic
