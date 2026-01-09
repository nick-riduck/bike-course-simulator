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
        # Realistic Caps: Long rides limit peak power due to fatigue/durability
        points = [
            (1.0, 1.20), # Short race: can push VO2max
            (3.0, 1.10),
            (5.0, 1.05), # Threshold limit
            (8.0, 1.00)  # Long endurance: Do not exceed FTP on climbs
        ]
        
        if t <= points[0][0]: return points[0][1]
        if t >= points[-1][0]: return points[-1][1]
        
        # Linear interpolation
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            if x1 <= t <= x2:
                # y = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
                return y1 + (y2 - y1) * (t - x1) / (x2 - x1)
                
        return 1.0 # Fallback
