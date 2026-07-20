"""Consistent public error mapping for the HTTP adapter."""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fantasy_draft.api.repository import (
    BoardNotFoundError,
    InvalidSessionNameError,
    SessionNotFoundError,
)
from fantasy_draft.draft.mutations import (
    IdempotencyConflictError,
    SessionAlreadyExistsError,
    SessionDeletionNotFoundError,
    StaleMutationError,
)
from fantasy_draft.draft.session import (
    AmbiguousPlayerError,
    DraftSessionError,
    PlayerNotFoundError,
)


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
    @app.exception_handler(RequestValidationError)
    async def invalid_payload(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            jsonable_encoder(
                error_payload(
                    "invalid_payload",
                    "Request validation failed",
                    True,
                    {"errors": exc.errors()},
                )
            ),
            status_code=422,
        )

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found(_request: Request, exc: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(error_payload("session_not_found", str(exc)), status_code=404)

    @app.exception_handler(BoardNotFoundError)
    async def board_not_found(_request: Request, exc: BoardNotFoundError) -> JSONResponse:
        return JSONResponse(error_payload("board_not_found", str(exc)), status_code=404)

    @app.exception_handler(InvalidSessionNameError)
    async def invalid_session(_request: Request, exc: InvalidSessionNameError) -> JSONResponse:
        return JSONResponse(error_payload("invalid_session_name", str(exc)), status_code=400)

    @app.exception_handler(AmbiguousPlayerError)
    async def ambiguous_player(_request: Request, exc: AmbiguousPlayerError) -> JSONResponse:
        return JSONResponse(
            error_payload(
                "ambiguous_player",
                str(exc),
                True,
                {"query": exc.query, "candidates": exc.candidates},
            ),
            status_code=409,
        )

    @app.exception_handler(PlayerNotFoundError)
    async def player_not_found(_request: Request, exc: PlayerNotFoundError) -> JSONResponse:
        return JSONResponse(error_payload("player_not_found", str(exc), True), status_code=404)

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict(
        _request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        return JSONResponse(error_payload("idempotency_conflict", str(exc)), status_code=409)

    @app.exception_handler(StaleMutationError)
    async def stale_mutation(_request: Request, exc: StaleMutationError) -> JSONResponse:
        return JSONResponse(
            error_payload("stale_mutation", str(exc), True), status_code=409
        )

    @app.exception_handler(SessionAlreadyExistsError)
    async def session_exists(
        _request: Request, exc: SessionAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(
            error_payload("session_exists", str(exc), True), status_code=409
        )

    @app.exception_handler(SessionDeletionNotFoundError)
    async def deleted_session_not_found(
        _request: Request, exc: SessionDeletionNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            error_payload("session_not_found", str(exc)), status_code=404
        )

    @app.exception_handler(DraftSessionError)
    async def invalid_session_file(_request: Request, exc: DraftSessionError) -> JSONResponse:
        return JSONResponse(error_payload("invalid_session", str(exc)), status_code=409)

    @app.exception_handler(ValueError)
    async def invalid_request(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(error_payload("invalid_request", str(exc), True), status_code=400)
