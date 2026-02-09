from __future__ import annotations

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.core.rider import Rider
from src.core.gpx_loader import Segment
from src.weather_client import WeatherClient
from src.engines.v2 import PhysicsParams, SimulationResult, PhysicsEngineV2

class GordonTheoryEngine(PhysicsEngineV2):
    """
    Strict Implementation Rules:
    1. P_max is FIXED (Physiological Constraint, typically CP or MAP).
    2. Optimization Variable is V_crit (Critical Velocity).
    3. Control Law:
       - If V < V_crit: P = P_max (Full Gas on climbs)
       - If V >= V_crit: P = (P_max * V_crit) / V (Inverse relationship)
    """
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        super().__init__(rider, params, weather_client)
        # P_max should be a physiological constant.
        # For a long event (7h+), P_max is roughly CP (Critical Power).
        # We use CP as the hard cap for sustainable aerobic effort.
        self.p_max_fixed = self.rider.cp 
        self.v_crit = 0.0 # Optimization variable

    def find_pbase_for_work(self, segments: List[Segment], target_work_kj: float):
        """
        Finds the optimal V_crit that results in the target total work.
        Note: The method name 'find_pbase...' is kept for interface compatibility, 
        but it actually searches for 'v_crit'.
        """
        low_vcrit, high_vcrit = 0.1, 20.0 # m/s (0.36 ~ 72 km/h)
        best_res = None
        
        # Binary Search for V_crit
        for _ in range(20):
            mid_vcrit = (low_vcrit + high_vcrit) / 2
            self.v_crit = mid_vcrit
            
            # Run simulation with fixed P_max and current V_crit
            # p_base argument is ignored by _calculate_target_power_dynamic
            res = self.simulate_course(segments, p_base=0.0, max_power_limit=self.p_max_fixed)
            
            if res.work_kj < target_work_kj:
                # Need to burn MORE energy -> Increase V_crit (expand P_max zone)
                low_vcrit = mid_vcrit
            else:
                # Need to burn LESS energy -> Decrease V_crit
                high_vcrit = mid_vcrit
            best_res = res
            
        return best_res

    def _calculate_target_power_dynamic(self, p_base: float, grade: float, max_limit: float, current_v: float) -> float:
        # STRICT implementation of Gordon (2005) Eq. 7 & 8
        
        # 1. Safety Coasting (Not in paper, but required for simulation sanity)
        if grade < -0.05: return 0.0

        # 2. Control Law
        if current_v < self.v_crit:
            return self.p_max_fixed
        else:
            # P = C / V where C = P_max * V_crit
            # This ensures continuity at V = V_crit
            return (self.p_max_fixed * self.v_crit) / max(0.1, current_v)