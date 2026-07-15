"""Configuration, loaded once from the environment.

One place to read every setting, so the PDC client, the LLM providers, the
security layer, and the routes all share the same source of truth instead of
scattering os.getenv() calls. Settings are frozen dataclasses populated from the
environment at import time (see .env.example for the full list and docs).

Note: security/auth settings are intentionally read directly from os.getenv()
inside app.security (not mirrored here), so security behaviour is governed in one
self-contained module.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    """Parse a boolean env var, accepting the usual truthy spellings."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _clean_base(base_url: str) -> str:
    """The PDC server root, robust to a base that already includes a Keycloak
    realm/token path or an /api/public/vN suffix (a common paste mistake). The
    code appends those paths itself, so without this a pasted realm URL produces
    a doubled URL like .../keycloak/realms/pdc/keycloak/realms/pdc/... -> 404."""
    b = (base_url or "").strip().rstrip("/")
    b = re.sub(r"/protocol/openid-connect/token/?$", "", b, flags=re.I)
    b = re.sub(r"/(?:auth|keycloak)/realms/[^/]+.*$", "", b, flags=re.I)
    b = re.sub(r"/api/public/v\d+.*$", "", b, flags=re.I)
    b = re.sub(r"/keycloak/?$", "", b, flags=re.I)
    return b.rstrip("/")


@dataclass(frozen=True)
class Brand:
    """White-label knobs so the product can be renamed per delivery, mirroring
    the Glossary Generator's GLOSSARY_* pattern."""
    name: str = os.getenv("INSIGHTS_BRAND_NAME", "Catalog Insights")
    product: str = os.getenv("INSIGHTS_BRAND_PRODUCT", "Pentaho Data Catalog")
    accent: str = os.getenv("INSIGHTS_BRAND_ACCENT", "#0F766E")


@dataclass(frozen=True)
class PDCConfig:
    """Everything needed to reach and authenticate to a PDC instance."""
    base_url: str = os.getenv("PDC_BASE_URL", "")
    version: str = os.getenv("PDC_API_VERSION", "v3")
    username: str = os.getenv("PDC_USERNAME", "")
    password: str = os.getenv("PDC_PASSWORD", "")
    # Optional long-lived token instead of user/pass (disables 401 re-auth retry).
    bearer_token: str = os.getenv("PDC_BEARER_TOKEN", "")
    verify_tls: bool = _bool("PDC_VERIFY_TLS", True)
    # Seconds to cache idempotent reads (facets/snapshot). 0 disables caching.
    cache_ttl: int = int(os.getenv("PDC_CACHE_TTL", "300"))
    # ── auth strategy ──────────────────────────────────────────────────────
    # PDC delegates authentication to Keycloak (OIDC). "keycloak" hits the realm
    # token endpoint directly (reliable on every instance); "pdc" uses the legacy
    # /api/public/<v>/auth wrapper; "auto" (default) tries Keycloak first and
    # falls back to the wrapper. The wrapper returns 200-but-no-token on some
    # instances, which is what "auto" routes around.
    auth_method: str = os.getenv("PDC_AUTH_METHOD", "auto")
    kc_realm: str = os.getenv("PDC_KC_REALM", "pdc")
    kc_client: str = os.getenv("PDC_KC_CLIENT_ID", "pdc-client")
    # Optional explicit Keycloak base; default derives {server_root}/keycloak.
    kc_base: str = os.getenv("PDC_KC_BASE", "")
    # Cloudflare Access service token. When PDC sits behind Cloudflare Access (or
    # Bot Fight), a browser passes the challenge but an API client can't and gets
    # an HTML interstitial instead of JSON. These headers let the client through
    # without a browser; create a service token in Cloudflare Zero Trust.
    cf_access_id: str = os.getenv("PDC_CF_ACCESS_CLIENT_ID", "")
    cf_access_secret: str = os.getenv("PDC_CF_ACCESS_CLIENT_SECRET", "")

    @property
    def cf_headers(self) -> dict:
        """Cloudflare Access service-token headers, or {} if not configured."""
        if self.cf_access_id and self.cf_access_secret:
            return {"CF-Access-Client-Id": self.cf_access_id,
                    "CF-Access-Client-Secret": self.cf_access_secret}
        return {}

    @property
    def server_root(self) -> str:
        """PDC server root (scheme+host[:port]), paste-robust. See _clean_base."""
        return _clean_base(self.base_url)

    @property
    def api_root(self) -> str:
        """The versioned API base, e.g. https://pdc.host/api/public/v3."""
        return f"{self.server_root}/api/public/{self.version}"

    @property
    def keycloak_token_url(self) -> str:
        """Realm token endpoint, e.g. https://pdc.host/keycloak/realms/pdc/
        protocol/openid-connect/token."""
        base = (self.kc_base or f"{self.server_root}/keycloak").rstrip("/")
        return f"{base}/realms/{self.kc_realm}/protocol/openid-connect/token"


@dataclass(frozen=True)
class LLMConfig:
    """Provider-agnostic LLM settings. `provider` selects the backend; the rest
    are interpreted by whichever provider is chosen (see app/llm/)."""
    provider: str = os.getenv("LLM_PROVIDER", "local").lower()
    model: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    api_key: str = os.getenv("LLM_API_KEY", "")
    # Constrain output to valid JSON (Ollama format=json / OpenAI json_object).
    json_mode: bool = _bool("LLM_JSON_MODE", True)
    timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))
    # Hard ceiling so a runaway prompt can't drain a metered account.
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))


@dataclass(frozen=True)
class Settings:
    """Top-level settings aggregate. `field(default_factory=...)` builds each
    sub-config lazily so a frozen dataclass can still nest other dataclasses."""
    host: str = os.getenv("INSIGHTS_HOST", "0.0.0.0")
    port: int = int(os.getenv("INSIGHTS_PORT", "8660"))
    log_level: str = os.getenv("INSIGHTS_LOG_LEVEL", "INFO")
    brand: Brand = field(default_factory=Brand)
    pdc: PDCConfig = field(default_factory=PDCConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


# Import this everywhere; it reflects the environment as of process start.
settings = Settings()


# ── runtime updates (Settings page: save + run against real data) ──
# Map (section, field) -> the .env / environment variable it persists to.
_ENV_KEYS = {
    ("pdc", "base_url"): "PDC_BASE_URL", ("pdc", "version"): "PDC_API_VERSION",
    ("pdc", "username"): "PDC_USERNAME", ("pdc", "password"): "PDC_PASSWORD",
    ("pdc", "cache_ttl"): "PDC_CACHE_TTL", ("pdc", "verify_tls"): "PDC_VERIFY_TLS",
    ("pdc", "auth_method"): "PDC_AUTH_METHOD", ("pdc", "kc_realm"): "PDC_KC_REALM",
    ("pdc", "kc_client"): "PDC_KC_CLIENT_ID",
    ("llm", "provider"): "LLM_PROVIDER", ("llm", "model"): "LLM_MODEL",
    ("llm", "base_url"): "LLM_BASE_URL", ("llm", "json_mode"): "LLM_JSON_MODE",
}


def _coerce(current, value):
    """Cast an incoming JSON value to match the existing field's type."""
    if isinstance(current, bool):
        return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(value)
    return "" if value is None else str(value)


def apply_settings(payload: dict, persist: bool = True) -> dict:
    """Apply Settings-page changes in place and (optionally) persist to .env.

    Mutates the live `settings.pdc` / `settings.llm` objects (so every module
    that reads `settings.x` sees the change without a restart), updates the
    matching environment variables, writes them through to .env so they survive a
    restart, and resets the PDC client token + LLM provider caches so the next
    request uses the new configuration. Returns the env keys that changed.
    """
    changed: dict[str, str] = {}

    # Demo toggle is read from the environment live by catalog._demo().
    if "demo" in payload:
        os.environ["INSIGHTS_DEMO"] = "true" if payload["demo"] else "false"
        changed["INSIGHTS_DEMO"] = os.environ["INSIGHTS_DEMO"]

    for section in ("pdc", "llm"):
        sub = getattr(settings, section)
        for key, val in (payload.get(section) or {}).items():
            if not hasattr(sub, key):
                continue
            casted = _coerce(getattr(sub, key), val)
            object.__setattr__(sub, key, casted)        # bypass frozen for the controlled path
            env_key = _ENV_KEYS.get((section, key))
            if env_key:
                env_val = str(casted).lower() if isinstance(casted, bool) else str(casted)
                os.environ[env_key] = env_val
                changed[env_key] = env_val

    if persist:
        _write_env(changed)
    _reset_runtime()
    return changed


def _reset_runtime() -> None:
    """Drop cached state so new settings take effect on the next request."""
    try:
        from .llm import provider as _p
        _p._cache = None                                 # rebuild provider with new llm config
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import pdc_client as _pc
        _pc.client._token = _pc.client.cfg.bearer_token or None   # re-auth with new creds/host
        _pc.client._cache.clear()                        # drop stale cached reads
    except Exception:  # noqa: BLE001
        pass


def _write_env(kv: dict, path: str = ".env") -> None:
    """Upsert key=value lines into .env, preserving the rest of the file."""
    if not kv:
        return
    from pathlib import Path
    p = Path(path)
    lines = p.read_text().splitlines() if p.exists() else []
    seen, out = set(), []
    for ln in lines:
        head = ln.split("=", 1)[0].strip()
        if head in kv:
            out.append(f"{head}={kv[head]}"); seen.add(head)
        else:
            out.append(ln)
    out.extend(f"{k}={v}" for k, v in kv.items() if k not in seen)
    p.write_text("\n".join(out) + "\n")


def public_settings() -> dict:
    """Current settings for the UI form — never includes the PDC password."""
    return {
        "demo": _bool("INSIGHTS_DEMO", False),
        "pdc": {"base_url": settings.pdc.base_url, "version": settings.pdc.version,
                "username": settings.pdc.username, "has_password": bool(settings.pdc.password),
                "cache_ttl": settings.pdc.cache_ttl, "verify_tls": settings.pdc.verify_tls,
                "auth_method": settings.pdc.auth_method, "kc_realm": settings.pdc.kc_realm,
                "kc_client": settings.pdc.kc_client},
        "llm": {"provider": settings.llm.provider, "model": settings.llm.model,
                "base_url": settings.llm.base_url, "json_mode": settings.llm.json_mode},
    }
