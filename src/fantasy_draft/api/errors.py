"""Consistent public error mapping for the HTTP adapter."""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fantasy_draft.api.repository import (
    BoardNotFoundError,
    InvalidSessionNameError,
    SessionNotFoundError,
)
from fantasy_draft.draft.session import DraftSessionError


def error_payload(
    code: str,
    message: str,
    recoverable: bool = False,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "recoverable": recoverable,
            "details": details or {},
        }
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotFoundError)
    async def session_not_found(_request: Request, exc: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(error_payload("session_not_found", str(exc)), status_code=404)

    @app.exception_handler(BoardNotFoundError)
    async def board_not_found(_request: Request, exc: BoardNotFoundError) -> JSONResponse:
        return JSONResponse(error_payload("board_not_found", str(exc)), status_code=404)

    @app.exception_handler(InvalidSessionNameError)
    async def invalid_session(_request: Request, exc: InvalidSessionNameError) -> JSONResponse:
        return JSONResponse(error_payload("invalid_session_name", str(exc)), status_code=400)

    @app.exception_handler(DraftSessionError)
    async def invalid_session_file(_request: Request, exc: DraftSessionError) -> JSONResponse:
        return JSONResponse(error_payload("invalid_session", str(exc)), status_code=409)

    @app.exception_handler(ValueError)
    async def invalid_request(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(error_payload("invalid_request", str(exc), True), status_code=400)
