"""Request-scoped access to application configuration."""

from pathlib import Path
from typing import Any

from fastapi import Request

from fantasy_draft.api.repository import SessionRepository
from fantasy_draft.providers.openrouter import OpenRouterClient


def session_repository(request: Request) -> SessionRepository:
    return SessionRepository(Path(request.app.state.sessions_dir))


def board_path(request: Request) -> Path:
    return Path(request.app.state.board_path)


def assistant_client(request: Request) -> Any:
    factory = request.app.state.assistant_client_factory
    return factory() if factory else OpenRouterClient()
