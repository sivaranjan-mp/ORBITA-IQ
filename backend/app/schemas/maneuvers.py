from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ManeuverCandidateResponse(BaseModel):
    id: Optional[str] = None
    alert_id: str
    direction: str
    delta_v_m_s: float
    delta_v_r_m_s: float = 0.0
    delta_v_t_m_s: float = 0.0
    delta_v_n_m_s: float = 0.0
    burn_epoch: datetime
    time_before_tca_hours: float
    resulting_tca: datetime
    resulting_miss_distance_m: float
    resulting_miss_distance_km: float
    resulting_relative_velocity_km_s: Optional[float] = None
    resulting_probability: float = 0.0
    resulting_risk_level: str
    miss_distance_improvement_m: float
    risk_level_change: Optional[str] = None
    efficiency_m_per_m_s: float = 0.0
    fuel_cost_proxy_m_s: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ManeuverGenerationRequest(BaseModel):
    magnitude_grid_m_s: Optional[List[float]] = Field(
        None,
        description="Discrete burn magnitudes in m/s (default: [0.01, 0.05, 0.1, 0.5, 1.0, 2.0])"
    )
    timing_grid_hours: Optional[List[float]] = Field(
        None,
        description="Burn timing offsets before original TCA in hours (default: [24.0, 12.0, 6.0, 2.0, 1.0])"
    )
    directions: Optional[List[str]] = Field(
        None,
        description="Subset of directions to evaluate (default: all 6 directions)"
    )
    save_to_db: bool = Field(
        True,
        description="Whether to persist generated candidates to the database"
    )


class ManeuverGenerationResponse(BaseModel):
    alert_id: str
    primary_satellite_name: str
    primary_norad_id: int
    secondary_object_name: str
    secondary_norad_id: int
    baseline_tca: datetime
    baseline_miss_distance_m: float
    baseline_miss_distance_km: float
    baseline_probability: float
    baseline_risk_level: str
    total_candidates: int
    candidates: List[ManeuverCandidateResponse]
    generated_at: datetime

    class Config:
        from_attributes = True
