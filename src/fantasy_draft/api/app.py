"""Private FastAPI application for the mobile draft cockpit."""

import argparse
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fantasy_draft.api.errors import install_error_handlers
from fantasy_draft.api.routes import board, health, sessions
from fantasy_draft.config import load_environment


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def create_app(
    sessions_dir: Path = Path("sessions"),
    board_path: Path = Path("outputs/draft_board.json"),
    frontend_dir: Optional[Path] = None,
) -> FastAPI:
    load_environment()
    app = FastAPI(
        title="NFL Fantasy Draft Assistant",
        version="0.1.0",
        description="Private, read-only API for the live fantasy draft cockpit.",
    )
    app.state.sessions_dir = Path(sessions_dir)
    app.state.board_path = Path(board_path)
    app.state.frontend_dir = Path(frontend_dir or PROJECT_ROOT / "frontend")

    @app.middleware("http")
    async def private_app_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
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
