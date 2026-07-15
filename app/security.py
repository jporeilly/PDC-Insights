"""Security model — shared by the web app and the MCP server.

Three concerns, kept separate and transport-agnostic so both front doors
enforce the same rules:

  • authenticate  — who is calling (API key or JWT bearer token)
  • authorize     — may this principal do this (role hierarchy)
  • audit         — record every privileged action

Roles mirror PDC's expert tiers so the model maps onto what the catalog
itself enforces:

  viewer   ~ Analyst         read dashboards, snapshot, search
  steward  ~ Data Steward    + generate and save dashboards
  admin    ~ Admin           + manage settings, read the audit log

The PDC *service account* this app uses should itself be read-only and
scoped in PDC — this layer is defense-in-depth on top of that, never a
replacement for PDC's own access control.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

log = logging.getLogger("insights.security")
_audit = logging.getLogger("insights.audit")

# ── roles ────────────────────────────────────────────────────
ROLES = {"viewer": 0, "steward": 1, "admin": 2}
ROLE_SCOPES = {
    "viewer": ["catalog:read"],
    "steward": ["catalog:read", "catalog:write"],
    "admin": ["catalog:read", "catalog:write", "catalog:admin"],
}


@dataclass
class Principal:
    id: str
    name: str
    role: str = "viewer"
    source: str = "anonymous"   # apikey | jwt | default
    claims: dict = field(default_factory=dict)

    @property
    def scopes(self) -> list[str]:
        return ROLE_SCOPES.get(self.role, [])

    def at_least(self, required: str) -> bool:
        return ROLES.get(self.role, -1) >= ROLES.get(required, 99)


class AuthError(Exception):
    """No valid credential (→ 401)."""


class ForbiddenError(Exception):
    """Valid credential, insufficient role (→ 403)."""


# ── configuration ────────────────────────────────────────────
def _mode() -> str:
    # none | apikey | jwt
    return os.getenv("INSIGHTS_AUTH", "none").strip().lower()


def _default_role() -> str:
    # role assumed when auth is disabled (local/stdio dev). Default admin so
    # local development isn't hobbled; production MUST set INSIGHTS_AUTH.
    return os.getenv("INSIGHTS_DEFAULT_ROLE", "admin").strip().lower()


def default_principal() -> Principal:
    return Principal(id="local", name="local-dev", role=_default_role(), source="default")


# ── API-key store ────────────────────────────────────────────
# INSIGHTS_API_KEYS = "key1:alice:admin,key2:bob:steward,key3:carol:viewer"
def _api_keys() -> dict[str, Principal]:
    out: dict[str, Principal] = {}
    raw = os.getenv("INSIGHTS_API_KEYS", "").strip()
    for entry in filter(None, (e.strip() for e in raw.split(","))):
        parts = entry.split(":")
        if len(parts) >= 3:
            key, name, role = parts[0], parts[1], parts[2]
            out[key] = Principal(id=name, name=name, role=role, source="apikey")
    return out


def _from_api_key(token: str) -> Principal | None:
    return _api_keys().get(token)


# ── JWT verification (optional) ──────────────────────────────
def _from_jwt(token: str) -> Principal | None:
    """Verify a bearer JWT and map a claim to a role.

    Configure either a shared secret (INSIGHTS_JWT_SECRET) or a JWKS URL
    (INSIGHTS_JWT_JWKS_URL). The role is read from INSIGHTS_JWT_ROLE_CLAIM
    (default 'role'); map external role names with INSIGHTS_JWT_ROLE_MAP.
    """
    try:
        import jwt  # PyJWT
    except ImportError:
        log.error("JWT auth requested but PyJWT is not installed")
        return None

    secret = os.getenv("INSIGHTS_JWT_SECRET", "")
    jwks_url = os.getenv("INSIGHTS_JWT_JWKS_URL", "")
    audience = os.getenv("INSIGHTS_JWT_AUDIENCE") or None
    issuer = os.getenv("INSIGHTS_JWT_ISSUER") or None
    try:
        if jwks_url:
            signing_key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, signing_key, algorithms=["RS256", "ES256"],
                                audience=audience, issuer=issuer)
        elif secret:
            claims = jwt.decode(token, secret, algorithms=["HS256"],
                                audience=audience, issuer=issuer)
        else:
            log.error("JWT auth requested but no secret or JWKS URL configured")
            return None
    except Exception as exc:  # noqa: BLE001
        log.warning("JWT validation failed: %s", exc)
        return None

    claim = os.getenv("INSIGHTS_JWT_ROLE_CLAIM", "role")
    raw_role = claims.get(claim, "viewer")
    if isinstance(raw_role, list):
        raw_role = raw_role[0] if raw_role else "viewer"
    role = _role_map().get(str(raw_role).lower(), str(raw_role).lower())
    if role not in ROLES:
        role = "viewer"
    subject = claims.get("sub", "unknown")
    return Principal(id=subject, name=claims.get("name", subject),
                     role=role, source="jwt", claims=claims)


def _role_map() -> dict[str, str]:
    # INSIGHTS_JWT_ROLE_MAP = "Data Steward:steward,Administrator:admin,Analyst:viewer"
    out: dict[str, str] = {}
    for entry in filter(None, (e.strip() for e in os.getenv("INSIGHTS_JWT_ROLE_MAP", "").split(","))):
        if ":" in entry:
            ext, internal = entry.split(":", 1)
            out[ext.strip().lower()] = internal.strip().lower()
    return out


# ── authenticate ─────────────────────────────────────────────
def authenticate(authorization: str | None) -> Principal:
    """Resolve a principal from an Authorization header value.

    Raises AuthError if auth is enabled and no valid credential is present.
    When auth is disabled, returns the default (local) principal.
    """
    mode = _mode()
    if mode == "none":
        return default_principal()

    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise AuthError("missing bearer token")

    principal = _from_api_key(token) if mode == "apikey" else _from_jwt(token)
    if principal is None:
        raise AuthError("invalid or expired credential")
    return principal


# ── authorize ────────────────────────────────────────────────
def authorize(principal: Principal, required: str) -> None:
    if not principal.at_least(required):
        raise ForbiddenError(f"requires role '{required}', principal has '{principal.role}'")


# ── audit ────────────────────────────────────────────────────
def _audit_configured() -> bool:
    return not getattr(_audit, "_configured", False)


def _configure_audit() -> None:
    path = os.getenv("INSIGHTS_AUDIT_LOG", "").strip()
    if path:
        h = logging.FileHandler(path)
        h.setFormatter(logging.Formatter("%(message)s"))
        _audit.addHandler(h)
    _audit.setLevel(logging.INFO)
    _audit._configured = True  # type: ignore[attr-defined]


def audit(principal: Principal, action: str, target: str | None = None,
          status: str = "ok", **extra) -> None:
    """Emit one structured audit record per privileged action."""
    if _audit_configured():
        _configure_audit()
    record = {"ts": round(time.time(), 3), "principal": principal.id,
              "role": principal.role, "source": principal.source,
              "action": action, "target": target, "status": status}
    record.update(extra)
    _audit.info(json.dumps(record))


def guard(principal: Principal, required: str, action: str, target: str | None = None):
    """authorize + audit in one call. Audits the denial too."""
    try:
        authorize(principal, required)
    except ForbiddenError:
        audit(principal, action, target, status="denied", required=required)
        raise
    audit(principal, action, target, status="ok")
