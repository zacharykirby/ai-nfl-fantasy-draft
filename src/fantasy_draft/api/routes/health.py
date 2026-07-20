"""Application and local artifact health routes."""

import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from fantasy_draft.api.dependencies import board_path, session_repository
from fantasy_draft.api.repository import SessionRepository
from fantasy_draft.api.schemas import HealthResponse


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
        return {"status": "missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "unreadable", "message": str(exc)}
    return {
        "status": payload.get("health", {}).get("status", "unknown"),
        "generated_at": payload.get("metadata", {}).get("generated_at"),
    }
