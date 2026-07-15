"""Flask glue for the shared security model."""
from functools import wraps

from flask import g, jsonify, request

from ..security import AuthError, ForbiddenError, audit, authenticate, authorize


def load_principal() -> None:
    """before_request hook: resolve the caller once per request."""
    try:
        g.principal = authenticate(request.headers.get("Authorization"))
        g.auth_error = None
    except AuthError as exc:
        g.principal = None
        g.auth_error = str(exc)


def require(role: str):
    """Gate a view on a minimum role, auditing allow and deny."""
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            p = getattr(g, "principal", None)
            action = f"{request.method} {request.path}"
            if p is None:
                return jsonify({"error": "unauthorized",
                                "detail": getattr(g, "auth_error", "authentication required")}), 401
            try:
                authorize(p, role)
            except ForbiddenError as exc:
                audit(p, action, status="denied", required=role)
                return jsonify({"error": "forbidden", "detail": str(exc)}), 403
            audit(p, action, status="ok")
            return fn(*args, **kwargs)
        return wrapped
    return deco
