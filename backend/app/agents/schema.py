from pydantic import BaseModel, Field


class ActivityInput(BaseModel):
    activity_name: str
    duration_sec: int
    distance_m: float
    sport_type: str
    tss: float
    hr_tss: float
    hr_drift_pct: float
    aerobic_decoupling_pct: float
    ngp_sec_km: float
    zone_distribution: dict[str, float]
    elevation_gain_m: float = 0.0
    cadence_avg: float | None = None


class RaceTargetContext(BaseModel):
    race_name: str
    weeks_out: int
    distance_km: float
    goal_time_sec: int | None = None
    training_phase: str  # Base / Build / Peak / Taper


class AthleteContext(BaseModel):
    lthr: int
    threshold_pace_sec_km: int
    tss_30d_avg: float
    acwr: float
    ctl: float
    atl: float
    tsb: float
    training_phase: str
    race_target: RaceTargetContext | None = None


class DebriefOutput(BaseModel):
    load_verdict: str = Field(max_length=500)
    technical_insight: str = Field(max_length=500)
    next_session_action: str = Field(max_length=500)
    nutrition_protocol: str = Field(default="", max_length=500)
    vmm_projection: str = Field(default="", max_length=500)
