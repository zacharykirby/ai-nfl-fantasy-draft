"""Read-only live session routes."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from fantasy_draft.api.dependencies import session_repository
from fantasy_draft.api.repository import SessionRepository
from fantasy_draft.api.schemas import (
    CockpitResponse,
    PlayerListResponse,
    RecommendationResponse,
    SessionDetailResponse,
    SessionListResponse,
)
from fantasy_draft.draft.cockpit import DraftCockpitService
from fantasy_draft.draft.recommendations import DraftRecommendationEngine, MODES


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=SessionListResponse)
def list_sessions(
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    return {"sessions": [session.summary() for session in repository.list()]}


@router.get("/{session_name}", response_model=SessionDetailResponse)
def session_detail(
    session_name: str,
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    session = repository.load(session_name)
    return {
        "schema_version": session.payload["schema_version"],
        "session": session.payload["session"],
        "league": session.payload["league"],
        "board": {
            key: value for key, value in session.payload["board"].items()
            if key != "players"
        },
        "summary": session.summary(),
    }


@router.get("/{session_name}/cockpit", response_model=CockpitResponse)
def cockpit(
    session_name: str,
    mode: str = Query("balanced"),
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    return DraftCockpitService(repository.load(session_name)).snapshot(mode=mode)


@router.get("/{session_name}/players/search", response_model=PlayerListResponse)
def search_players(
    session_name: str,
    q: str = Query(..., min_length=1, max_length=80),
    position: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=50),
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    players = DraftCockpitService(repository.load(session_name)).search(
        q, position=position, limit=limit
    )
    return {"players": players, "count": len(players)}


@router.get("/{session_name}/available", response_model=PlayerListResponse)
def available_players(
    session_name: str,
    position: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    players = DraftCockpitService(repository.load(session_name)).available(
        position=position, limit=limit
    )
    return {"players": players, "count": len(players)}


@router.get("/{session_name}/recommendation", response_model=RecommendationResponse)
def recommendation(
    session_name: str,
    mode: str = Query("balanced"),
    alternatives: int = Query(4, ge=0, le=10),
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    if mode not in MODES:
        raise ValueError("mode must be safe, balanced, or upside")
    session = repository.load(session_name)
    result = DraftRecommendationEngine(session).recommend(
        mode=mode, alternatives=alternatives
    )
    return {"recommendation": result}

