"""FastAPI glue for the shared security model.

`require(role)` is the dependency form of the old Flask decorator: it resolves
the caller from the Authorization header, enforces the role, audits allow and
deny, and hands the Principal to the route. Error payloads keep the legacy
Flask shapes ({"error": "unauthorized"/"forbidden", "detail": ...}) — the
ApiError handler in app.main turns them into responses, so FastAPI's default
{"detail": ...} shape never leaks to a client.
"""
import json

from fastapi import Request

from ..security import AuthError, ForbiddenError, Principal, audit, authenticate, authorize


class ApiError(Exception):
    """Carry a legacy-shaped JSON payload + HTTP status out of a dependency
    or route; app.main registers the handler that renders it verbatim."""

    def __init__(self, status: int, payload: dict):
        super().__init__(payload.get("error", "error"))
        self.status = status
        self.payload = payload


def require(role: str):
    """Dependency that gates a route on a minimum role, auditing allow and deny."""
    async def dep(request: Request) -> Principal:
        try:
            principal = authenticate(request.headers.get("Authorization"))
        except AuthError as exc:
            raise ApiError(401, {"error": "unauthorized", "detail": str(exc)})
        action = f"{request.method} {request.url.path}"
        try:
            authorize(principal, role)
        except ForbiddenError as exc:
            audit(principal, action, status="denied", required=role)
            raise ApiError(403, {"error": "forbidden", "detail": str(exc)})
        audit(principal, action, status="ok")
        return principal
    return dep


async def json_body(request: Request, silent: bool = False) -> dict:
    """Parse the request body as JSON regardless of Content-Type — the FastAPI
    equivalent of Flask's request.get_json(force=True) (and, with silent=True,
    of get_json(silent=True): {} instead of a 400 on a missing/bad body).
    Mirrors the old `... or {}` idiom, so a JSON null/empty body becomes {}."""
    raw = await request.body()
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 — empty or malformed body
        if silent:
            return {}
        raise ApiError(400, {"error": "invalid JSON body"})
    return data or {}
