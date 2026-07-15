"""MCP-side glue for the shared security model.

- InsightsTokenVerifier validates bearer tokens on the HTTP transport using the
  same app.security.authenticate() the web app uses.
- current_principal() recovers the caller inside a tool (HTTP: from the verified
  access token; stdio/local: the default principal).
- build_auth() assembles the FastMCP auth settings when INSIGHTS_AUTH is set.
"""
from __future__ import annotations

import logging
import os

from app.security import (Principal, ROLE_SCOPES, authenticate, default_principal,
                          guard as _guard)

log = logging.getLogger("insights.mcp.security")


def _enabled() -> bool:
    return os.getenv("INSIGHTS_AUTH", "none").strip().lower() != "none"


# ── token verifier (HTTP transport) ──────────────────────────
def make_token_verifier():
    """Return a TokenVerifier instance, or None if the SDK lacks the hook."""
    try:
        from mcp.server.auth.provider import AccessToken, TokenVerifier
    except Exception as exc:  # noqa: BLE001
        log.warning("MCP auth provider unavailable: %s", exc)
        return None

    class InsightsTokenVerifier(TokenVerifier):
        async def verify_token(self, token: str):
            try:
                p = authenticate(f"Bearer {token}")
            except Exception:  # noqa: BLE001
                return None
            return AccessToken(token=token, client_id=p.id, scopes=p.scopes,
                               subject=p.id,
                               claims={"role": p.role, "name": p.name, "source": p.source})

    return InsightsTokenVerifier()


def build_auth():
    """(token_verifier, auth_settings) for FastMCP, or (None, None) if disabled."""
    if not _enabled():
        return None, None
    verifier = make_token_verifier()
    if verifier is None:
        return None, None
    try:
        from mcp.server.auth.settings import AuthSettings
        settings = AuthSettings(
            issuer_url=os.getenv("INSIGHTS_AUTH_ISSUER", "https://catalog-insights.local"),
            resource_server_url=os.getenv("INSIGHTS_MCP_URL", "http://localhost:8765"),
            required_scopes=["catalog:read"],
        )
        return verifier, settings
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not build AuthSettings (%s); running without transport auth", exc)
        return verifier, None


# ── per-tool principal + guard ───────────────────────────────
def current_principal() -> Principal:
    """The caller inside a tool. HTTP: from the verified token; else default."""
    if _enabled():
        try:
            from mcp.server.auth.middleware.auth_context import get_access_token
            tok = get_access_token()
            if tok is not None:
                role = (tok.claims or {}).get("role", "viewer")
                name = (tok.claims or {}).get("name", tok.subject or "unknown")
                return Principal(id=tok.subject or name, name=name, role=role,
                                 source="jwt", claims=tok.claims or {})
        except Exception as exc:  # noqa: BLE001
            log.debug("no access token in context: %s", exc)
    return default_principal()


def guard(role: str, action: str, target: str | None = None) -> Principal:
    """Authorize the current caller for an action and audit it. Raises on deny."""
    p = current_principal()
    _guard(p, role, action, target)   # raises ForbiddenError if insufficient
    return p


def gated(role: str):
    """Decorator: gate a tool on a role, returning a clean error on denial."""
    import functools
    import json as _json

    from app.security import ForbiddenError

    def deco(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                guard(role, fn.__name__)
            except ForbiddenError as exc:
                return _json.dumps({"error": "forbidden", "detail": str(exc)})
            return fn(*args, **kwargs)
        return wrapped
    return deco
