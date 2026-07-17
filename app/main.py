"""FastAPI application factory.

The FastAPI port of the old Flask factory: the same /api + /health contract
route-for-route (see app/routes/), the same auth semantics and legacy error
payload shapes, plus interactive API docs at /docs. Every engine module
(catalog, generator, pdc_client, panel_data, llm, …) is unchanged — this file
and app/routes/ are only the web layer.

Run:  uvicorn asgi:app --port 5002   (or ./run.sh / .\\run.ps1 / run.bat)
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .routes import routers
from .routes._auth import ApiError

ROOT = Path(__file__).resolve().parent.parent
# Built React UI (frontend/dist). When present it is served at /, matching the
# FastAPI siblings' dist auto-mount; otherwise the static design mock in
# ui/mock keeps serving, so a source checkout works without Node.
UI_DIST = ROOT / "frontend" / "dist"
MOCK_DIR = ROOT / "ui" / "mock"


def _app_version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


def _file_from(directory: Path, path: str) -> FileResponse:
    """Serve one file from `directory`, refusing path traversal — the FastAPI
    stand-in for Flask's send_from_directory. Missing file -> 404."""
    full = (directory / path).resolve()
    if not str(full).startswith(str(directory.resolve())) or not full.is_file():
        raise StarletteHTTPException(status_code=404, detail="not found")
    return FileResponse(full)


def create_app() -> FastAPI:
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(
        title="Catalog Insights",
        version=_app_version(),
        description=("AI-assisted reporting & dashboards for Pentaho Data Catalog. "
                     "Read-only against PDC; the only write is saving a dashboard "
                     "spec file locally.\n\n[← Back to the app](/)"),
    )

    # Legacy error contract: routes and the auth layer raise ApiError with the
    # exact Flask-era payloads; generic HTTP errors are rendered as
    # {"error": ...} too, so FastAPI's default {"detail": ...} never leaks.
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(exc.payload, status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": "invalid request"}, status_code=400)

    for r in routers:
        app.include_router(r)

    # The original design mock stays reachable for reference at /mock/….
    @app.get("/mock", include_in_schema=False)
    def mock_root():
        return RedirectResponse("/mock/", status_code=308)

    @app.get("/mock/", include_in_schema=False)
    @app.get("/mock/{path:path}", include_in_schema=False)
    def mock(path: str = "index.html"):
        return _file_from(MOCK_DIR, path or "index.html")

    if (UI_DIST / "index.html").is_file():
        # Serve the built React UI. API routes are explicit and registered
        # first, so they always win over the catch-all; anything that isn't a
        # build asset falls through to index.html (SPA routing, e.g. /chat).
        @app.get("/", include_in_schema=False)
        @app.get("/chat", include_in_schema=False)
        def index():
            return FileResponse(UI_DIST / "index.html")

        # Old bookmark compatibility: /ui/… used to serve the mock directly.
        @app.get("/ui/{path:path}", include_in_schema=False)
        def ui(path: str):
            return _file_from(MOCK_DIR, path)

        @app.get("/{path:path}", include_in_schema=False)
        def dist_asset(path: str):
            if (UI_DIST / path).is_file():
                return _file_from(UI_DIST, path)
            return FileResponse(UI_DIST / "index.html")
    else:
        # No build present — fall back to the static mock (previous behaviour).
        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(MOCK_DIR / "index.html")

        @app.get("/ui/{path:path}", include_in_schema=False)
        def ui(path: str):
            return _file_from(MOCK_DIR, path)

        @app.get("/chat", include_in_schema=False)
        def chat_page():
            # The in-app AI dashboard builder (chat window).
            return FileResponse(MOCK_DIR / "chat.html")

    return app


# Note: the app is built on demand via create_app() (see asgi.py), not at
# import time — so importing app.generator / app.pdc_client from the MCP
# server doesn't construct a FastAPI app or register routes.
