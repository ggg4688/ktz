from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RoleName = Literal["viewer", "operator", "admin"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PublicUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    full_name: str
    role: RoleName


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: RoleName = "viewer"


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: PublicUser


class TelemetryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locomotive_id: str = Field(default="locomotive-01", min_length=1, max_length=64)
    captured_at: datetime | None = None
    temperature_c: float = Field(ge=-50, le=200)
    pressure_bar: float = Field(ge=0, le=20)
    fuel_level_pct: float = Field(ge=0, le=100)
    speed_kph: float = Field(ge=0, le=250)
    distance_km: float | None = Field(default=None, ge=0)
    scenario_tag: str | None = Field(default=None, max_length=64)


class FactorContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    label: str
    weight: float
    penalty: float
    score_impact: float
    current_value: float


class AlertItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["warning", "critical"]
    metric: str
    message: str
    recommendation: str


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    priority: int
    message: str


class TelemetrySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: int | None = None
    locomotive_id: str
    captured_at: datetime
    distance_km: float | None = None
    scenario_tag: str | None = None
    temperature_c: float
    pressure_bar: float
    fuel_level_pct: float
    speed_kph: float
    smoothed_temperature_c: float
    smoothed_pressure_bar: float
    smoothed_fuel_level_pct: float
    smoothed_speed_kph: float
    health_score: float
    health_category: Literal["normal", "attention", "critical"]
    alert_penalty: float
    formula: str
    top_factors: list[FactorContribution]
    alerts: list[AlertItem]
    recommendations: list[RecommendationItem]


class TelemetryWindowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locomotive_id: str
    from_at: datetime
    to_at: datetime
    sample_count: int
    items: list[TelemetrySnapshot]


class ReplayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locomotive_id: str
    from_at: datetime
    to_at: datetime
    stride: int
    frame_count: int
    frames: list[TelemetrySnapshot]


class AlertSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: int
    captured_at: datetime
    health_score: float
    health_category: Literal["normal", "attention", "critical"]
    alerts: list[AlertItem]


class AlertHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locomotive_id: str
    from_at: datetime
    to_at: datetime
    sample_count: int
    items: list[AlertSnapshot]


class OverviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    latest: TelemetrySnapshot | None
    active_alerts: list[AlertItem]
    recommendations: list[RecommendationItem]
    service_metrics: dict[str, Any]
    simulator: dict[str, Any]


class BatchIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inserted: int
    last_sequence_id: int | None = None


class SimulatorControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Literal["baseline", "overheat", "pressure_drop", "low_fuel", "mixed_failure"] = "baseline"
    interval_ms: int = Field(default=1000, ge=100, le=10_000)
    burst_size: int = Field(default=1, ge=1, le=100)
    load_multiplier: float = Field(default=1.0, ge=0.5, le=10.0)
    locomotive_id: str = Field(default="locomotive-01", min_length=1, max_length=64)
    reset_state: bool = True


class SimulatorStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    running: bool
    scenario: str
    interval_ms: int
    burst_size: int
    load_multiplier: float
    locomotive_id: str
    tick: int
    distance_km: float
    fuel_level_pct: float
    last_emitted_at: datetime | None = None
