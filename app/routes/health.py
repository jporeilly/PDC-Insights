"""Liveness + dependency reachability (PDC, LLM)."""
from fastapi import APIRouter, Depends, Request

from ..config import settings
from ..llm import get_provider
from ..security import Principal
from ._auth import require

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    # Public: no auth — used by orchestration health checks.
    return {"status": "ok", "brand": settings.brand.name}


@router.get("/config")
def config(principal: Principal = Depends(require("viewer"))):
    return {
        "brand": {"name": settings.brand.name, "product": settings.brand.product,
                  "accent": settings.brand.accent},
        "pdc": {"base_url": settings.pdc.base_url, "version": settings.pdc.version},
        "llm": {"provider": settings.llm.provider, "model": settings.llm.model},
        "auth": {"mode": __import__("os").getenv("INSIGHTS_AUTH", "none")},
    }


@router.get("/health/llm")
def health_llm(principal: Principal = Depends(require("viewer"))):
    return get_provider().health()


@router.get("/health/pdc")
def health_pdc(principal: Principal = Depends(require("viewer"))):
    """PDC reachability for the UI status dot. Resolves the catalog snapshot:
    live + reachable -> ok/live; demo or live-but-unreachable -> not ok/demo
    (with the fallback note so the footer can explain why)."""
    from ..catalog import catalog_snapshot
    snap = catalog_snapshot()
    demo = snap.get("demo", True)
    return {"ok": not demo, "demo": demo,
            "base_url": settings.pdc.base_url,
            "note": snap.get("note")}


@router.get("/health/pdc/token")
def health_pdc_token(request: Request, principal: Principal = Depends(require("admin"))):
    """Debug: fetch a PDC bearer token through the app's OWN client and show it
    plus its decoded claims and the exact endpoint/headers used. Admin-only —
    it reveals a live token. ?reveal=1 returns the full token; otherwise it's
    truncated. Use this to confirm the app is authenticating as expected.
    """
    from ..config import PDCConfig
    from ..pdc_client import PDCClient, PDCError, decode_jwt

    cfg = PDCConfig()  # reflects the live settings/env
    client = PDCClient(cfg=cfg)
    client._token = None  # force a fresh fetch so we see what's happening now

    info = {
        "keycloak_token_url": cfg.keycloak_token_url,
        "legacy_auth_url": f"{cfg.api_root}/auth",
        "auth_method": cfg.auth_method,
        "verify_tls": cfg.verify_tls,
        "cf_access_enabled": bool(cfg.cf_headers),
    }
    try:
        tok = client.token()
    except PDCError as exc:
        return {"ok": False, "error": str(exc), **info}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", **info}

    reveal = request.query_params.get("reveal") in ("1", "true", "yes")
    ident = decode_jwt(tok)
    return {
        "ok": True,
        "token": tok if reveal else (tok[:24] + "…" + tok[-12:]),
        "token_length": len(tok),
        "identity": ident,        # username, roles, is_admin, exp, expires_in_s
        **info,
    }


@router.get("/health/pdc/probe")
def health_pdc_probe(principal: Principal = Depends(require("admin"))):
    """Debug: run each live read the snapshot depends on and report what came
    back (counts, facet keys, a small sample) or the per-call error. Admin-only.
    Use this to see exactly why Live falls back to demo, without curl.
    """
    from ..config import PDCConfig
    from ..pdc_client import PDCClient

    client = PDCClient(cfg=PDCConfig())
    result: dict = {"base_url": client.cfg.base_url, "version": client.cfg.version}

    # facets
    try:
        f = client.facets("*", {"sensitivity": [], "type": [], "rootIds": []})
        result["facets"] = {"ok": True, "facet_keys": [x.get("key") for x in f],
                            "count": len(f)}
    except Exception as exc:  # noqa: BLE001
        result["facets"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # trust distribution
    try:
        t = client.trust_distribution()
        result["trust"] = {"ok": True, "bands": t}
    except Exception as exc:  # noqa: BLE001
        result["trust"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # data sources (the one that was 404'ing)
    try:
        ds = client.data_sources()
        result["data_sources"] = {"ok": True, "count": len(ds),
                                  "sample": ds[:8]}
    except Exception as exc:  # noqa: BLE001
        result["data_sources"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return result
