from __future__ import annotations

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.rider import Rider
from src.gpx_loader import Segment
from src.weather_client import WeatherClient
from src.physics_engine_v2 import PhysicsParams, SimulationResult, PhysicsEngineV2

class TheoryEngine(PhysicsEngineV2):
    """
    [Optimal Control Theory Implementation]
    Based on Gordon (2005) & Swain (1997).
    Logic: Inverse velocity pacing (P ~ 1/V) with strict physiological constraints.
    """
    def __init__(self, rider: Rider, params: PhysicsParams, weather_client: Optional[WeatherClient] = None):
        super().__init__(rider, params, weather_client)
        self.p_max_constraint = self.rider.pdc.get(60, self.rider.cp * 2.0) # 1-min Max Power Constraint

    def _calculate_target_power_dynamic(self, p_base: float, grade: float, max_limit: float, current_v: float) -> float:
        # 1. Theoretical Optimum: Inverse Velocity
        # P = C / V (to maintain constant energy per distance)
        safe_v = max(0.5, current_v)
        
        # If speed is half of reference, power should double (theoretically)
        # Ratio = V_ref / V
        ratio = self.v_ref / safe_v
        
        target = p_base * ratio
        
        # 2. Physiological Constraints (The missing piece in previous attempts)
        # Power cannot exceed rider's anaerobic ceiling for short bursts
        limit = min(max_limit, self.p_max_constraint)
        
        return min(target, limit)
