from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class Rider:
    """
    Rider model to handle physiological constraints (CP, W', PDC).
    Tracks W' balance during simulation.
    """
    cp: float              # Critical Power (Watts)
    w_prime_max: float      # Total Anaerobic Capacity (Joules)
    weight: float           # Rider weight (kg)
    pdc: Dict[int, float] = field(default_factory=dict) # Power Duration Curve {seconds: watts}
    
    # State variables for simulation
    w_prime_bal: float = 0.0
    
    def __post_init__(self):
        """Initialize simulation state."""
        # Normalize PDC keys to int
        if self.pdc:
            self.pdc = {int(k): float(v) for k, v in self.pdc.items()}
        self.reset_state()

    def reset_state(self):
        """Reset W' balance to maximum."""
        self.w_prime_bal = self.w_prime_max

    def update_w_prime(self, power: float, duration_sec: float):
        """
        Update W' balance using the Skiba model.
        
        If Power > CP: Depletion is linear.
        If Power < CP: Recovery is exponential.
        """
        delta_p = power - self.cp
        
        if delta_p > 0:
            # Depletion
            self.w_prime_bal -= delta_p * duration_sec
        else:
            # Recovery
            # Tau (time constant) estimation - Skiba (2012)
            # D_cp = CP - P_recovery
            d_cp = abs(delta_p)
            if d_cp > 0:
                tau = 546 * math.exp(-0.01 * d_cp) + 316
                # Exponential recovery formula
                w_exp = self.w_prime_max - self.w_prime_bal
                self.w_prime_bal = self.w_prime_max - w_exp * math.exp(-duration_sec / tau)
            else:
                # No recovery if Power == CP
                pass
        
        # Clamp balance between 0 and Max
        # self.w_prime_bal = max(0.0, min(self.w_prime_bal, self.w_prime_max))

    def is_bonked(self) -> bool:
        """Check if anaerobic battery is exhausted."""
        return self.w_prime_bal < 0

    def check_pdc_limit(self, power: float, duration_sec: float) -> bool:
        """
        Validate if the rider can sustain 'power' for 'duration_sec' based on PDC.
        """
        if not self.pdc:
            return True # No PDC data, assume okay
            
        # Find the closest duration in PDC
        sorted_keys = sorted(self.pdc.keys())
        
        # Simple lookup: find first key >= duration
        limit_power = 0.0
        for k in sorted_keys:
            if k >= duration_sec:
                limit_power = self.pdc[k]
                break
        else:
            # If duration is longer than max PDC key, use the longest one
            limit_power = self.pdc[sorted_keys[-1]]
            
        return power <= (limit_power + 5) # 5W margin

    def get_dynamic_max_cap(self, estimated_duration_hours: float) -> float:
        """
        Calculate Max Power Cap (as % of FTP/CP) based on estimated ride duration.
        Linear interpolation based on the design document.
        """
        t = estimated_duration_hours
        
        # Data points for interpolation: (hours, cap_factor)
        points = [
            (1.0, 1.20),
            (3.0, 1.10),
            (5.0, 1.25),
            (8.0, 1.20)
        ]
        
        if t <= points[0][0]: return points[0][1]
        if t >= points[-1][0]: return points[-1][1]
        
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            if x1 <= t <= x2:
                return y1 + (y2 - y1) * (t - x1) / (x2 - x1)
                
        return 1.0

    def get_max_force(self) -> float:
        """
        Calculate maximum pedal force (Thrust Limit) based on PDC.
        Target: 5s Power at Sprint Cadence (110rpm).
        """
        p_max = self.get_pdc_power(5)
        # F = P / (Omega * Radius) = P / (11.52 * 0.34) = P / 3.91
        return p_max / 3.91

    def get_pdc_power(self, duration_sec: float) -> float:
        """
        Returns the maximum sustainable power for a given duration using 
        linear interpolation of the PDC data.
        """
        if not self.pdc:
            return self.cp * 1.2 # Fallback
            
        durations = sorted(self.pdc.keys())
        powers = [self.pdc[d] for d in durations]
        
        # Boundary cases
        if duration_sec <= durations[0]: return powers[0]
        if duration_sec >= durations[-1]: return powers[-1]
        
        # Linear Interpolation
        for i in range(len(durations) - 1):
            if durations[i] <= duration_sec <= durations[i+1]:
                t1, p1 = durations[i], powers[i]
                t2, p2 = durations[i+1], powers[i+1]
                # Log-linear interpolation is more accurate for PDC, 
                # but linear is sufficient for this range.
                return p1 + (p2 - p1) * (duration_sec - t1) / (t2 - t1)
                
        return self.cp
