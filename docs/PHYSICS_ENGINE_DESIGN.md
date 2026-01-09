# Physics Engine Design Document [PRO-745]

## 1. Overview
This document outlines the enhanced physics engine logic for the cycling simulator. The goal is to calculate the **fastest feasible finish time** while respecting physiological limits and realistic pacing strategies.

---

## 2. Pacing Strategy (The "Policy")

We define how the rider distributes power across the course based on terrain (Grade). This simulates human behavior (pushing uphill, recovering downhill).

### A. Slope-based Power Distribution (3-Stage Logic)
$$P_{target}(i) = P_{base} \times \text{Multiplier}(Grade)$$

1.  **Uphill ($Grade > 0$): Aggressive**
    *   Formula: $P_{target} = P_{base} \times (1 + \alpha_{up} \times Grade)$
    *   Constraint: Must not exceed **Dynamic Safety Cap** (see Section 3).

2.  **Flat / Gentle Downhill ($-2\% \le Grade \le 0$): Momentum Preservation**
    *   Goal: Maintain momentum without wasting energy on high drag.
    *   Logic: Maintain $P_{base}$ or slightly reduced (e.g., $0.8 \times P_{base}$) to keep speed $> 35km/h$. Do not coast immediately.

3.  **Steep Downhill ($Grade < -2\%$): Recovery**
    *   Goal: Maximize W' recovery.
    *   Logic: **Cut-off to 0W** (Coasting). Gravity provides sufficient speed.

---

## 3. Physiological Constraints & Safety

### A. Duration-based Safety Cap (Dynamic Ceiling)
To prevent "suicide pacing" on long rides (e.g., riding at VO2max during an 8-hour Gran Fondo), we enforce a **Hard Cap** on peak power based on estimated duration.

**Model (Linear Interpolation):**
*   $T = 1h$: Max Power = **120% FTP**
*   $T = 3h$: Max Power = **110% FTP**
*   $T = 5h$: Max Power = **105% FTP**
*   $T = 8h+$: Max Power = **95% FTP** (Strict Aerobic Cap)

*Implementation:* The engine estimates finish time first, determines the cap factor, and clamps all uphill power targets to this ceiling.

### B. W' Balance Model (Skiba)
Real-time tracking of anaerobic battery.
*   **Depletion ($P > CP$):** $W'_{bal} -= (P - CP) \times t$
*   **Recovery ($P < CP$):** Exponential recovery.
*   **Failure:** $W'_{bal} < 0$ $\rightarrow$ Simulation aborted or forced slow-down (Bonk).

### C. PDC Check (Momentary Power)
Rolling average check against the rider's Power Duration Curve.
*   Example: "Can I hold 400W for this 3-minute climb?" $\rightarrow$ Check `PDC['180s']`.

---

## 4. Optimization Algorithm (The Solver)

**Objective:** Find maximum $P_{base}$ such that the rider completes the course **without Bonking**.

*   **Variable:** $P_{base}$ (Baseline Intensity).
*   **Algorithm (Binary Search):**
    *   Range: $[0, CP \times MaxCapFactor]$
    *   Iteration:
        1.  Set candidate $P_{base}$.
        2.  Apply Pacing Strategy (Stage A).
        3.  Apply Safety Cap (Stage B).
        4.  Run Simulation (verify W' > 0).
        5.  Adjust range based on Success/Failure.

---

## 5. Core Physics Math (UPDATED)

### A. Kinetic Energy & Inertia Model
Instead of assuming steady-state velocity for short segments, we use an **acceleration-based model** to properly simulate inertia (carrying momentum into climbs).

1.  **Net Force Calculation:**
    $$F_{net} = F_{propulsion} - (F_{gravity} + F_{rolling} + F_{aero})$$
    *   $F_{propulsion} \approx Power / v_{entry}$ (Approximation for small steps. Use small epsilon for v=0)
    *   $F_{gravity} = m \cdot g \cdot \sin(\arctan(Grade))$
    *   $F_{rolling} = m \cdot g \cdot \cos(\arctan(Grade)) \cdot C_{rr}$
    *   $F_{aero} = 0.5 \cdot \rho \cdot CdA \cdot (v_{entry} + v_{wind})^2$

2.  **Final Velocity (Work-Energy Principle):**
    Using equation of motion $v^2 = v_0^2 + 2ad$:
    $$v_{final} = \sqrt{\max(0, v_{entry}^2 + 2 \cdot \frac{F_{net}}{m} \cdot d)}$$
    
    *   If $v_{entry}$ is very low (< 3km/h), revert to Newton-Raphson (Steady State) to initiate movement from standstill.

3.  **Time Calculation:**
    $$t = \frac{2 \cdot d}{v_{entry} + v_{final}}$$

### B. Vector Wind
*   $V_{eff} = V_{wind} \times \cos(\theta_{wind} - \theta_{road})$

### C. Drafting
*   $CdA_{final} = CdA \times (1 - \text{DraftingFactor})$

---

## 6. Implementation Structure
*   `src/rider.py`: Class `Rider` (Stores CP, W', PDC, calculates limits).
*   `src/physics_engine.py`: Class `PhysicsEngine` (Main loop, solver, segment physics).
*   `src/strategy.py`: Helper functions for Pacing Policy & Cap calculation.
