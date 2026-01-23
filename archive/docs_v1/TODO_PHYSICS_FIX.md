# Physics Engine Stabilization Plan

## 1. Problem Statement
Simulation results show unrealistic spikes:
*   **Grade Spikes:** Some segments have > 50% grade (Vertical wall).
*   **Speed Spikes:** > 160km/h on uphills.
*   **Cause:** GPS noise creates tiny distance segments ($\Delta d \approx 0$), causing $Grade = \Delta h / \Delta d$ and $Force = Power / v$ to explode.

## 2. Action Plan

### Step 1: GpxLoader Refactoring (Data Cleaning)
Clean the input data before it reaches the physics engine.

*   **[Logic] Min Distance Pruning:** During `load()`, ignore points where distance from previous point is **< 5 meters**.
    *   *Effect:* Eliminates "stationary drift" noise and prevents division by zero.
*   **[Logic] Enhanced Smoothing:** Increase Moving Average window from 5 to **10**.
    *   *Effect:* Softens sudden elevation jumps.
*   **[Logic] Grade Clamping:** In `compress_segments`, cap `grade` to **[-25%, +25%]**.
    *   *Effect:* Prevents mathematical singularities.

### Step 2: Physics Engine Safeguards
Add physical limits to prevent runaway acceleration.

*   **[Physics] Max Speed Cap:** Clamp velocity to **100 km/h** (Safety net).
*   **[Physics] Traction Limit:** Limit propulsive force ($F_{pedal}$) to **1000 N**.
    *   *Reason:* Tires slip beyond this force. Prevents infinite acceleration at low speeds.

## 3. Verification
*   Re-run `simulate.py` with `20seorak.gpx`.
*   Check `simulation_result.json` for grade spikes.
*   Check `simulation_analysis.png` for smooth speed/power curves.
