# Physics Engine Upgrade Candidates

## 🎯 Objective
Identify the most effective pacing strategy model that integrates gravity, aerodynamic drag (wind), and rolling resistance into a unified logic.

## 候选 1: Virtual Grade Model (Recommended for Stability)
Convert all resistance forces into an **"Equivalent Gradient"** and reuse the proven `Alpha` (Grade-based) pacing logic.

### 📐 Formula
1.  **Calculate Total Force:**
    $$ F_{total} = F_{gravity} + F_{aero} + F_{roll} $$
    *   $F_{gravity} = m \cdot g \cdot \sin(\theta)$
    *   $F_{aero} = 0.5 \cdot \rho \cdot C_d A \cdot (V_{rider} + V_{wind})^2$
    *   $F_{roll} = m \cdot g \cdot C_{rr} \cdot \cos(\theta)$

2.  **Convert to Virtual Grade:**
    $$ G_{virt} = \frac{F_{total}}{m \cdot g} $$
    *   Includes headwind and rough road effects as "steeper grade".

3.  **Apply Pacing:**
    $$ P_{target} = P_{base} \times (1 + \alpha_{climb} \times G_{virt}) $$

### ✅ Pros & Cons
*   **Pros:** Extremely stable (linear response), naturally handles headwinds as hills.
*   **Cons:** Requires nested solver to estimate $F_{aero}$ (which depends on speed).

---

## 候选 2: Beta Tuning Model (Current Experiment)
Refine the velocity-based weighting (`Beta`) to handle extreme edge cases.

### 🛠 Tuning Strategies
1.  **Deadzone:** Ignore small speed deviations (e.g., ±5km/h from V_ref).
2.  **Asymmetric:** Low sensitivity for climbing (prevent spikes), High for descending (save energy).
3.  **Logarithmic:** Use `ln(V/V_ref)` to dampen power spikes at very low speeds.

### ✅ Pros & Cons
*   **Pros:** Directly optimizes for aerodynamic efficiency.
*   **Cons:** Prone to instability at low speeds ($V \to 0$) without careful tuning.

---

## 候选 3: Critical Speed / Iso-Effort
Maintain a specific target speed or normalized resistance ratio.

### 📐 Formula
$$ P_{req} = F_{total}(V_{target}) \times V_{target} $$
*   Cap power at $P_{max\_limit}$.

### ✅ Pros & Cons
*   **Pros:** User-friendly ("I want to average 30km/h").
*   **Cons:** Often leads to early burnout (Bonk) on climbs if $V_{target}$ is unrealistic.
