"""Read-only draft board routes."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from fantasy_draft.api.dependencies import board_path
from fantasy_draft.api.repository import BoardNotFoundError
from fantasy_draft.api.schemas import BoardSummaryResponse
from fantasy_draft.board.builder import load_board


router = APIRouter(prefix="/board", tags=["board"])


@router.get("/summary", response_model=BoardSummaryResponse)
def board_summary(path: Path = Depends(board_path)) -> Dict[str, Any]:
    if not path.is_file():
        raise BoardNotFoundError("Draft board is not available")
    board = load_board(path)
    roles = board.get("roles", {})
    return {
        "schema_version": str(board.get("schema_version", "unknown")),
        "metadata": board.get("metadata", {}),
        "league": board.get("league", {}),
        "health": board.get("health", {}),
        "role_counts": {
            position: len(players) if isinstance(players, list) else 0
            for position, players in roles.items()
        },
    }
