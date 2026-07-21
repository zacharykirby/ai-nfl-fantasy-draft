"""Private FastAPI application for the mobile draft cockpit."""

import argparse
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fantasy_draft.api.errors import error_payload, install_error_handlers
from fantasy_draft.api.routes import board, health, sessions
from fantasy_draft.config import load_environment


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAX_REQUEST_BYTES = 64 * 1024
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'none'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "img-src 'self' data:",
        "script-src 'self'",
        "style-src 'self'",
    ]
)


def _same_origin(request: Request, origin: str) -> bool:
    parsed = urlsplit(origin)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.hostname.lower() == (request.url.hostname or "").lower()
        and parsed.username is None
        and parsed.password is None
    )


def create_app(
    sessions_dir: Path = Path("sessions"),
    board_path: Path = Path("outputs/draft_board.json"),
    frontend_dir: Optional[Path] = None,
    assistant_client_factory: Optional[Callable] = None,
) -> FastAPI:
    load_environment()
    app = FastAPI(
        title="NFL Fantasy Draft Assistant",
        version="0.1.0",
        description="Private API for the live fantasy draft cockpit.",
    )
    app.state.sessions_dir = Path(sessions_dir)
    app.state.board_path = Path(board_path)
    app.state.frontend_dir = Path(frontend_dir or PROJECT_ROOT / "frontend")
    app.state.assistant_client_factory = assistant_client_factory
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver", "*.ts.net"],
    )

    @app.middleware("http")
    async def private_app_headers(request: Request, call_next):
        response = None
        if request.method in MUTATING_METHODS:
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin and not _same_origin(request, origin)
            ):
                response = JSONResponse(
                    error_payload("cross_origin_request", "Cross-origin requests are not allowed"),
                    status_code=403,
                )

            content_length = request.headers.get("content-length")
            if response is None and content_length:
                try:
                    too_large = int(content_length) > MAX_REQUEST_BYTES
                except ValueError:
                    too_large = True
                if too_large:
                    response = JSONResponse(
                        error_payload("request_too_large", "Request body exceeds 64 KiB"),
                        status_code=413,
                    )

        if response is None:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    install_error_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(board.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")

    assets = app.state.frontend_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(app.state.frontend_dir / "index.html")

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the private fantasy draft web server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--sessions-dir", type=Path, default=Path("sessions"))
    parser.add_argument("--board", type=Path, default=Path("outputs/draft_board.json"))
    args = parser.parse_args()

    import uvicorn

    server_app = create_app(sessions_dir=args.sessions_dir, board_path=args.board)
    uvicorn.run(server_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
