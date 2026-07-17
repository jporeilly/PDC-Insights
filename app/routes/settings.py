"""Settings endpoints — read and update the live configuration.

  GET  /api/settings   → current config for the form (never the password)
  POST /api/settings   → apply + persist changes, then run against real data

Saving changes the PDC/LLM connection and writes .env, so it needs 'admin'.
Reading is 'viewer'. After a successful POST the new config is live immediately
(the PDC client re-authenticates and the LLM provider is rebuilt), so a
subsequent snapshot/recommend/chat call hits the real instance.
"""
import requests
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..config import PDCConfig, apply_settings, public_settings, settings
from ..pdc_client import PDCClient, PDCError, decode_jwt
from ..security import Principal, audit
from ._auth import json_body, require

router = APIRouter(prefix="/api", tags=["settings"])

_ALLOWED = {"pdc": {"base_url", "version", "username", "password", "cache_ttl",
                    "verify_tls", "auth_method", "kc_realm", "kc_client"},
            "llm": {"provider", "model", "base_url", "json_mode"}}


@router.get("/settings")
def get_settings(principal: Principal = Depends(require("viewer"))):
    return public_settings()


@router.post("/settings")
async def save_settings(request: Request,
                        principal: Principal = Depends(require("admin"))):
    body = await json_body(request)
    # Keep only known fields (don't let arbitrary keys reach the env / .env).
    clean = {}
    if "demo" in body:
        clean["demo"] = bool(body["demo"])
    for section, allowed in _ALLOWED.items():
        if isinstance(body.get(section), dict):
            picked = {k: v for k, v in body[section].items() if k in allowed
                      and not (k == "password" and v in ("", None))}  # blank ⇒ keep existing
            if picked:
                clean[section] = picked
    if not clean:
        return JSONResponse({"error": "no recognised settings in request"}, status_code=400)

    apply_settings(clean)
    # Audit without leaking secrets: log which fields changed, not their values.
    fields = sorted([f"{s}.{k}" for s in ("pdc", "llm") for k in clean.get(s, {})]
                    + (["demo"] if "demo" in clean else []))
    audit(principal, "settings_update", target=",".join(fields))
    return {"saved": True, "settings": public_settings()}


@router.post("/settings/test-pdc")
async def test_pdc(request: Request,
                   principal: Principal = Depends(require("viewer"))):
    """Actually attempt PDC authentication and report the real outcome.

    Exercises the *same* auth path the app uses at runtime (Keycloak-first with
    the /auth fallback, per auth_method), against the values in the request — so
    you can verify before saving — falling back to the saved config for anything
    omitted (a blank password means "use the stored one"). On success it decodes
    the issued JWT to show who it's for and confirms a read-only call accepts it.
    Returns a specific reason on failure — bad creds, wrong realm/version, TLS,
    or an unreachable host — instead of silently degrading to demo data.
    """
    body = await json_body(request, silent=True)
    base = (body.get("base_url") or settings.pdc.base_url or "").rstrip("/")
    version = body.get("version") or settings.pdc.version or "v3"
    username = body.get("username") or settings.pdc.username
    password = body.get("password") or settings.pdc.password
    if not base:
        return {"ok": False, "error": "No PDC Base URL set."}
    if not (username and password):
        return {"ok": False, "error": "Username and password are required."}

    # Throwaway client built from the submitted values; no fixed bearer so it
    # genuinely authenticates with the credentials under test.
    probe_cfg = PDCConfig(
        base_url=base, version=version, username=username, password=password,
        bearer_token="", verify_tls=settings.pdc.verify_tls,
        auth_method=body.get("auth_method") or settings.pdc.auth_method,
        kc_realm=body.get("kc_realm") or settings.pdc.kc_realm,
        kc_client=body.get("kc_client") or settings.pdc.kc_client,
        cf_access_id=settings.pdc.cf_access_id,
        cf_access_secret=settings.pdc.cf_access_secret,
    )
    probe = PDCClient(cfg=probe_cfg)

    try:
        token = probe.token()
    except requests.exceptions.SSLError:
        return {"ok": False,
                "error": "TLS/SSL error — certificate not trusted. (Self-signed? set PDC_VERIFY_TLS=false in .env.)"}
    except requests.exceptions.ConnectTimeout:
        return {"ok": False, "error": f"Timed out connecting to {base} — host/port reachable?"}
    except requests.exceptions.ConnectionError:
        return {"ok": False,
                "error": f"Cannot reach {base} — DNS or connection refused. Check the URL is the PDC host (and any port)."}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        if code in (401, 403):
            return {"ok": False, "status": code,
                    "error": "Authentication failed (401/403) — check the username and password."}
        if code == 404:
            return {"ok": False, "status": 404,
                    "error": f"404 during auth — check the Keycloak realm '{probe_cfg.kc_realm}', the Base URL, or the API version."}
        return {"ok": False, "status": code, "error": f"PDC returned HTTP {code} during auth."}
    except PDCError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Unexpected error: {exc}"}

    ident = decode_jwt(token)
    who = ident.get("username") or username
    roles = ident.get("roles", [])

    # Confirm the token is actually accepted by a read-only call.
    try:
        probe.facets("*", {"sensitivity": []})
        return {"ok": True, "user": who, "roles": roles,
                "detail": f"Authenticated to {base} as {who}; read accepted ({version})."}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        return {"ok": True, "user": who, "roles": roles,
                "detail": f"Token issued for {who}, but a read returned HTTP {code} — check API version ({version}) or account permissions."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "user": who, "roles": roles,
                "detail": f"Token issued for {who}, but the read check failed: {exc}"}
