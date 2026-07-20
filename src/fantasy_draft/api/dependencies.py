"""Request-scoped access to application configuration."""

from pathlib import Path

from fastapi import Request

from fantasy_draft.api.repository import SessionRepository


def session_repository(request: Request) -> SessionRepository:
    return SessionRepository(Path(request.app.state.sessions_dir))


def board_path(request: Request) -> Path:
    return Path(request.app.state.board_path)

