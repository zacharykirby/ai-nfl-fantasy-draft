"""Read-only draft board routes."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from fantasy_draft.api.dependencies import board_path
from fantasy_draft.api.repository import BoardNotFoundError
from fantasy_draft.api.schemas import BoardSummaryResponse
from fantasy_draft.board.builder import board_project_root, load_board, runtime_board_health
from fantasy_draft.draft.session import BOARD_POSITIONS, board_players


router = APIRouter(prefix="/board", tags=["board"])


@router.get("/summary", response_model=BoardSummaryResponse)
def board_summary(path: Path = Depends(board_path)) -> Dict[str, Any]:
    if not path.is_file():
        raise BoardNotFoundError("Draft board is not available")
    board = load_board(path)
    health = runtime_board_health(board, project_root=board_project_root(path))
    canonical_players = board_players(board)
    return {
        "schema_version": str(board.get("schema_version", "unknown")),
        "metadata": board.get("metadata", {}),
        "league": board.get("league", {}),
        "health": health,
        "role_counts": {
            position: sum(
                1 for player in canonical_players if player.get("position") == position
            )
            for position in BOARD_POSITIONS
        },
    }
