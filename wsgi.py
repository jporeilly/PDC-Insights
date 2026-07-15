"""WSGI entrypoint.

Loads .env from the project root FIRST, so configuration (PDC_BASE_URL,
PDC_USERNAME/PASSWORD, PDC_VERIFY_TLS, auth method, etc.) is present in the
environment before app.config reads it at import time — no matter which
directory the server is launched from. Real environment variables already set
in the shell win over .env (override=False), so `set VAR=...` still takes
precedence for quick overrides.
"""
from pathlib import Path

from dotenv import load_dotenv

# .env sits next to this file (the project root); load it explicitly by path so
# `waitress-serve wsgi:app` works from any working directory.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from app import create_app  # noqa: E402  (must import after .env is loaded)

app = create_app()
