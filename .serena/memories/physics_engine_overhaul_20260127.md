# Physics Engine Overhaul & Verification Report (2026-01-27)

## 1. Core Logic Changes
The simulation engine has been fundamentally redesigned to ensure physical accuracy and stability.

### A. Iterative Solver (Binary Search)
- **Problem:** Previous logic assumed a fixed speed (25km/h) to guess ride duration, leading to incorrect power limits.
- **Solution:** Implemented a binary search solver (`find_optimal_pacing`) that iteratively adjusts `P_base` (10W ~ 1500W) until the simulated Normalized Power (NP) converges with the rider's physiological limit (PDC Limit) for the resulting duration.
- **Convergence:** Typically converges within 15 iterations with < 0.1W error margin.

### B. Walking Mode (Clamp)
- **Problem:** On steep climbs (>15%), speed could drop near zero, causing simulation time to diverge to infinity and NP to spike unnaturally.
- **Solution:** Enforced a minimum speed limit of **5.0 km/h** (approx. 40 RPM at 1:1 gear ratio).
- **Behavior:** If speed drops below this threshold, the engine sets `v_next = 5.0 km/h`, `is_walking = True`, and metabolic power cost = 30W.

### C. Actual Power Calculation
- **Problem:** Previously, NP was calculated based on `Target Power`, even if the rider physically couldn't output that power due to torque limits or fatigue.
- **Solution:** Now calculates `Actual Power` by reverse-engineering the force applied to the wheel (limited by `f_max_initial` and fatigue decay).
- **Outcome:** NP accurately reflects the rider's physical output, eliminating "High NP but Slow Time" anomalies.

### D. Riegel Extrapolation
- **Problem:** User PDC data is finite (e.g., up to 1 hour), but simulations (e.g., Seorak Granfondo) can last 7+ hours.
- **Solution:** Applied Riegel's Fatigue Model for durations exceeding the PDC range:
  $$ P_{limit} = P_{max\_pdc} \times \left( \frac{T_{sim}}{T_{max\_pdc}} \right)^{-0.07} $$

## 2. Validation Results

### A. Seorak Granfondo (20seorak.gpx)
- **Rider:** 85kg, 281W CP (Rider A)
- **Result:**
  - **Time:** 7h 04m 22s
  - **NP:** 258 W (Perfectly matches the Extrapolated PDC Limit for 7h)
  - **Walking:** Occurred on Guryongryeong Reverse & Jochimryeong (20-25% grades).

### B. Virtual Slope Test
- **Namsan (1.8km, 120m):** 5m 20s @ 420W (Matches 5m PDC max)
- **Steep Wall (4.12km, 13.5%):** 40m 23s @ 230W (Physically consistent speed ~6.1 km/h)

### C. Sensitivity Analysis
- **Torque Limit (`f_max_factor`):** Tested 1.0G ~ 2.0G on Bukak, Bunwonri, and Seorak.
- **Result:** No significant change in finish time. The 5km/h Walking Clamp activates before torque limits become the primary bottleneck, ensuring stability.

## 3. Tooling
- `tools/calc_virtual_slope.py`: CLI tool for validating physics on simple slope scenarios.
- `tools/sensitivity_test.py`: Script to batch-test physics parameters against real courses.
