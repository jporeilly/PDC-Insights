"""ASGI entrypoint (uvicorn asgi:app).

Loads .env FIRST, so configuration (PDC_BASE_URL, PDC_USERNAME/PASSWORD,
PDC_VERIFY_TLS, auth method, etc.) is present in the environment before
app.config reads it at import time — no matter which directory the server is
launched from. Real environment variables already set in the shell win over
.env (override=False), so `set VAR=...` still takes precedence for quick
overrides.

Which .env: the state directory's, when INSIGHTS_STATE_DIR is set (a packaged
install — the desktop shell sets it, and the Settings page persists there);
otherwise the one next to this file, exactly as before. The resolution rule
lives in app/paths.py, but importing anything from the app package would read
the environment before .env is loaded — so the explicit-override half of the
rule is applied inline here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_state = os.environ.get("INSIGHTS_STATE_DIR")
_env = (Path(_state) / ".env") if _state else (Path(__file__).resolve().parent / ".env")
load_dotenv(_env, override=False)

from app import create_app  # noqa: E402  (must import after .env is loaded)

app = create_app()
