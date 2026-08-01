"""Application and local artifact health routes."""

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from fantasy_draft.api.dependencies import board_path, session_repository
from fantasy_draft.api.repository import SessionRepository
from fantasy_draft.api.schemas import HealthResponse
from fantasy_draft.board import validate_board_path


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    path: Path = Depends(board_path),
    repository: SessionRepository = Depends(session_repository),
) -> Dict[str, Any]:
    board = _board_health(path)
    return {
        "status": "ok" if board["status"] == "ready" else "degraded",
        "service": "fantasy-draft-assistant",
        "schema_version": "1.0",
        "board": board,
        "sessions": {"directory_exists": repository.sessions_dir.exists(), "count": repository.count()},
        "model": {"configured": bool(os.getenv("OPENROUTER_API_KEY"))},
    }


def _board_health(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return _unavailable_board_health("missing", "Draft board is not available")
    try:
        return validate_board_path(path)
    except (OSError, ValueError) as exc:
        return _unavailable_board_health("unreadable", str(exc))


def _unavailable_board_health(component_status: str, message: str) -> Dict[str, Any]:
    issue = {
        "severity": "error",
        "code": "board_{}".format(component_status),
        "message": message,
    }
    return {
        "status": "not_ready",
        "can_create_session": False,
        "error_count": 1,
        "warning_count": 0,
        "issues": [issue],
        "snapshot": {
            "status": component_status,
            "error_count": 1,
            "warning_count": 0,
            "issues": [issue],
        },
        "source": {
            "status": "unknown",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
            "metrics": {},
        },
        "freshness": {
            "status": "unknown",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
            "metrics": {},
        },
    }
