from dataclasses import dataclass, field
import json
from typing import Dict, Any, Optional

@dataclass
class PhysicalConfig:
    """물리 법칙 및 하드웨어 관련 상수"""
    cda: float = 0.30
    crr: float = 0.0045
    bike_weight: float = 8.0
    drivetrain_loss: float = 0.05
    air_density_sea_level: float = 1.225
    tire_friction_mu: float = 0.8

@dataclass
class SolverConfig:
    """솔버 알고리즘 및 페이싱 전략 파라미터"""
    pacing_mode: str = "asymmetric"  # linear, asymmetric, logarithmic, theory
    beta_slow: float = 0.6
    beta_fast: float = 1.5
    v_ref_mode: str = "adaptive"    # fixed, adaptive
    v_ref_fixed_kmh: float = 30.0
    brake_start_kmh: float = 50.0   # 제동 시작 속도
    brake_limit_kmh: float = 80.0   # 최대 마지노선 속도
    binary_search_iterations: int = 15

@dataclass
class SimulationConfig:
    """통합 시뮬레이션 설정"""
    physics: PhysicalConfig = field(default_factory=PhysicalConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)

    @classmethod
    def load_from_json(cls, file_path: str) -> 'SimulationConfig':
        """JSON 파일에서 설정을 로드"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            p_data = data.get('physics', {})
            s_data = data.get('solver', {})
            
            return cls(
                physics=PhysicalConfig(**p_data),
                solver=SolverConfig(**s_data)
            )
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using default configuration.")
            return cls()
        except Exception as e:
            print(f"Error loading config: {e}. Using default configuration.")
            return cls()

    def to_physics_params(self):
        """기존 PhysicsEngine과의 호환성을 위해 PhysicsParams 객체로 변환"""
        # Note: 여기서 drafting_factor 같은 값은 상황에 따라 주입 필요
        from src.engines.base import PhysicsParams
        return PhysicsParams(
            cda=self.physics.cda,
            crr=self.physics.crr,
            bike_weight=self.physics.bike_weight,
            drivetrain_loss=self.physics.drivetrain_loss,
            air_density=self.physics.air_density_sea_level,
            drafting_factor=0.0 # Default
        )
