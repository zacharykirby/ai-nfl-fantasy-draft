"""Live session read and explicit mutation routes."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from fantasy_draft.api.dependencies import assistant_client, session_repository
from fantasy_draft.api.repository import SessionRepository
from fantasy_draft.api.schemas import (
    AssistantAnswerResponse,
    AssistantQuestionRequest,
    BulkMutationResponse,
    BulkPickPreviewRequest,
    BulkPickPreviewResponse,
    BulkPickRequest,
    CockpitResponse,
    InterpretCommandRequest,
    InterpretCommandResponse,
    MutationResponse,
    PickRequest,
    PlayerListResponse,
    RecommendationResponse,
    SessionDetailResponse,
    SessionListResponse,
    UndoRequest,
)
from fantasy_draft.assistant import DraftAssistantQueryService
from fantasy_draft.draft.cockpit import DraftCockpitService, player_view
from fantasy_draft.draft.commands import bulk_pick_queries, pick_query
from fantasy_draft.draft.mutations import DraftMutationService
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


@router.post("/{session_name}/commands/interpret", response_model=InterpretCommandResponse)
def interpret_command(
    session_name: str,
    command: InterpretCommandRequest,
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    session = repository.load(session_name)
    query = pick_query(command.text)
    if not query:
        return {
            "intent": "question",
            "message": "This looks like a read-only draft question.",
        }
    player = session.match_player(query)
    return {
        "intent": "record_pick",
        "message": "Confirm this selection before changing draft state.",
        "player": player_view(player),
        "confirmation": {
            "overall_pick": session.current_pick,
            "round": ((session.current_pick - 1) // session.league_size) + 1,
            "team": session.current_team,
            "text": "Record {} at pick {} for team {}?".format(
                player["player"], session.current_pick, session.current_team
            ),
        },
    }


@router.post("/{session_name}/assistant/ask", response_model=AssistantAnswerResponse)
def ask_assistant(
    session_name: str,
    request: AssistantQuestionRequest,
    repository: SessionRepository = Depends(session_repository),
    client: Any = Depends(assistant_client),
) -> Dict[str, Any]:
    return DraftAssistantQueryService(
        repository.path(session_name),
        client=client,
        timeout=12,
    ).ask(request.question, mode=request.mode)


@router.post("/{session_name}/picks", response_model=MutationResponse)
def record_pick(
    session_name: str,
    request: PickRequest,
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    return DraftMutationService(repository.path(session_name)).record_pick(
        request.player,
        request.request_id,
        mode=request.mode,
    )


@router.post(
    "/{session_name}/picks/bulk/preview",
    response_model=BulkPickPreviewResponse,
)
def preview_bulk_picks(
    session_name: str,
    request: BulkPickPreviewRequest,
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    players = bulk_pick_queries(request.text)
    return DraftMutationService(repository.path(session_name)).preview_bulk(players)


@router.post("/{session_name}/picks/bulk", response_model=BulkMutationResponse)
def record_bulk_picks(
    session_name: str,
    request: BulkPickRequest,
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    return DraftMutationService(repository.path(session_name)).record_bulk(
        request.players,
        request.request_id,
        request.expected_start_pick,
        mode=request.mode,
    )


@router.post("/{session_name}/undo", response_model=MutationResponse)
def undo_pick(
    session_name: str,
    request: UndoRequest,
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    return DraftMutationService(repository.path(session_name)).undo(
        request.request_id,
        mode=request.mode,
        expected_target_event_id=request.target_event_id,
    )
