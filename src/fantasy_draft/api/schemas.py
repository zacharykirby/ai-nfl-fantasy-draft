"""Versioned HTTP response contracts."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    recoverable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PlayerResponse(BaseModel):
    player_id: Optional[str] = None
    player: str
    position: str
    team: Optional[str] = None
    position_rank: Optional[int] = None
    overall_rank: Optional[int] = None
    tier: Optional[int] = None
    projected_points: Optional[float] = None
    vorp: Optional[float] = None
    adp: Optional[float] = None
    bye_week: Optional[int] = None
    projection_method: Optional[str] = None
    risk: Dict[str, Any] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    service: str
    schema_version: str
    board: Dict[str, Any]
    sessions: Dict[str, Any]
    model: Dict[str, Any]


class BoardSummaryResponse(BaseModel):
    schema_version: str
    metadata: Dict[str, Any]
    league: Dict[str, Any]
    health: Dict[str, Any]
    role_counts: Dict[str, int]


class SessionSummaryResponse(BaseModel):
    name: str
    status: str
    current_pick: int
    current_team: Optional[int] = None
    next_user_pick: Optional[int] = None
    selections: int
    available: int
    user_roster: List[PlayerResponse]


class SessionListResponse(BaseModel):
    sessions: List[SessionSummaryResponse]


class SessionDetailResponse(BaseModel):
    schema_version: str
    session: Dict[str, Any]
    league: Dict[str, Any]
    board: Dict[str, Any]
    summary: SessionSummaryResponse


class PlayerListResponse(BaseModel):
    players: List[PlayerResponse]
    count: int


class RecommendationResponse(BaseModel):
    recommendation: Dict[str, Any]


class CockpitResponse(BaseModel):
    schema_version: str
    session: Dict[str, Any]
    league: Dict[str, Any]
    user_roster: List[PlayerResponse]
    recent_picks: List[Dict[str, Any]]
    recommendation: Optional[Dict[str, Any]] = None
    best_available: List[PlayerResponse]
    top_available_by_position: Dict[str, List[PlayerResponse]]
    tier_alerts: List[Dict[str, Any]]
    position_run: Dict[str, Any]
    health: Dict[str, Any]


class InterpretCommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=160)


class InterpretCommandResponse(BaseModel):
    intent: str
    message: str
    player: Optional[PlayerResponse] = None
    confirmation: Optional[Dict[str, Any]] = None


class PickRequest(BaseModel):
    player: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)
    mode: str = "balanced"


class BulkPickPreviewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1000)


class BulkPickPreviewResponse(BaseModel):
    start_pick: int
    end_pick: int
    picks: List[Dict[str, Any]]


class BulkPickRequest(BaseModel):
    players: List[str] = Field(min_length=2, max_length=20)
    request_id: str = Field(min_length=8, max_length=100)
    expected_start_pick: int = Field(ge=1)
    mode: str = "balanced"


class UndoRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    target_event_id: str = Field(default="", max_length=100)
    mode: str = "balanced"


class MutationResponse(BaseModel):
    event: Dict[str, Any]
    cockpit: CockpitResponse
    replayed: bool


class BulkMutationResponse(BaseModel):
    events: List[Dict[str, Any]]
    cockpit: CockpitResponse
    replayed: bool
