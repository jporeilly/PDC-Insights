"""Thin client over the PDC public REST API.

This module is the *only* place in the codebase that talks HTTP to Pentaho
Data Catalog. Everything else (the web routes, the generator, the MCP tools,
the recommender) goes through this client, so there is exactly one spot to
reason about authentication, caching, and PDC's quirks.

Design rules baked in here:

* READ-ONLY.  Reporting only needs to read. We deliberately expose no method
  that mutates the catalog, which keeps the security blast radius tiny: even a
  fully compromised caller can't change PDC through this app (see SECURITY.md).

* API IS THE CONTRACT.  PDC stores data in OpenSearch (search/facets), MongoDB
  (operational metadata; FerretDB/Postgres in PDC 11), and a BIDB. We never
  touch those engines directly — only the public REST API, which shields us
  from PDC's internal storage changes across versions.

Endpoints used (all under {base}/api/public/{version}):
  POST /auth              -> bearer token (a short-lived JWT)
  POST /search            -> paginated asset rows
  POST /search/facets     -> pre-aggregated counts  ← the dashboard workhorse
  POST /entities/filter   -> full entity attributes (cursor-paginated)
  GET  /data-sources      -> connected sources / scan inventory

Trust-score note: READING trust scores via search/facets works on every tested
build. TRIGGERING a recalculation through the public API is version-dependent,
so this client intentionally exposes no "calculate" call (see PDC-CONNECTOR.md).
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .config import settings

# PDC's standard trust-score banding. Reused by trust_distribution() and mirrored
# in the UI's "trust spectrum". Ranges are inclusive: 0–50, 51–75, 76–100.
_TRUST_BUCKETS = [
    ("Untrusted", 0, 50),
    ("Trusted", 51, 75),
    ("Highly Trusted", 76, 100),
]


class PDCError(RuntimeError):
    """Raised for PDC-specific problems (missing creds, malformed auth reply).

    HTTP-level failures surface as requests.HTTPError via raise_for_status();
    this is for the cases the HTTP layer can't express on its own.
    """


def decode_jwt(token: str) -> dict:
    """Display-only decode of a JWT payload (NOT signature-verified).

    Best-effort and never raises: returns the few claims worth confirming after
    auth — who the token is for and what roles/expiry it carries. Used by the
    Settings 'Test connection' result; never for authorization decisions.
    """
    import base64
    import json
    import time as _time

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # pad base64url
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    roles = (claims.get("realm_access") or {}).get("roles") or []
    exp = claims.get("exp")
    out = {
        "username": claims.get("preferred_username") or claims.get("sub") or "",
        "name": claims.get("name") or "",
        "roles": roles,
        "is_admin": any(str(r).lower() in ("admin", "system_administrator") for r in roles),
        "exp": exp,
    }
    if isinstance(exp, (int, float)):
        out["expires_in_s"] = max(0, int(exp - _time.time()))
    return out


class PDCClient:
    """Stateful client holding a cached bearer token and a small response cache.

    One module-level instance (`client`, created at the bottom) is shared by the
    whole process. It is safe to share because the only mutable state is the
    token and the TTL cache, both of which tolerate concurrent overwrite
    (last-write-wins) under the threaded gunicorn workers we run.
    """

    def __init__(self, cfg=settings.pdc):
        self.cfg = cfg
        # If a long-lived token was supplied in config, seed it; otherwise we'll
        # fetch one lazily on first use via token().
        self._token: str | None = cfg.bearer_token or None
        # cache_key -> (stored_at_epoch, payload). Bounded only by the number of
        # distinct queries; fine for a reporting workload. TTL from PDC_CACHE_TTL.
        self._cache: dict[str, tuple[float, Any]] = {}

    # ── auth ─────────────────────────────────────────────────
    def token(self) -> str:
        """Return a valid bearer token, fetching one if we don't have it.

        PDC delegates auth to Keycloak (OIDC). `auth_method` selects the path:
        "keycloak" hits the realm token endpoint directly; "pdc" uses the legacy
        /api/public/<v>/auth wrapper; "auto" (default) tries Keycloak first and
        falls back to the wrapper. We fall back on an HTTP error or a missing
        token (wrong realm/client, or an instance that only exposes the wrapper),
        but let transport errors (TLS/DNS/timeout) propagate so the caller can
        report them precisely. The token is cached; _request() clears it on a 401
        so the next call re-authenticates (PDC JWTs are short-lived, no refresh).
        """
        if self._token:
            return self._token
        if not (self.cfg.username and self.cfg.password):
            raise PDCError("No PDC credentials configured")

        method = (self.cfg.auth_method or "auto").lower()
        if method == "pdc":
            self._token = self._legacy_auth()
        elif method == "keycloak":
            self._token = self._keycloak_auth()
        else:  # auto
            try:
                self._token = self._keycloak_auth()
            except (PDCError, requests.exceptions.HTTPError) as e_kc:
                try:
                    self._token = self._legacy_auth()
                except (PDCError, requests.exceptions.HTTPError) as e_pdc:
                    raise PDCError(f"Keycloak auth failed: {e_kc} | "
                                   f"/auth fallback failed: {e_pdc}")
        if not self._token:
            raise PDCError("Authentication succeeded but no token was returned")
        return self._token

    def _keycloak_auth(self) -> str:
        """Resource-owner-password grant against the Keycloak realm token
        endpoint; reads the JWT from the top-level access_token (data.access_token
        on some proxies)."""
        url = self.cfg.keycloak_token_url
        resp = requests.post(
            url,
            data={"grant_type": "password", "client_id": self.cfg.kc_client,
                  "username": self.cfg.username, "password": self.cfg.password,
                  "scope": "openid"},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     **self.cfg.cf_headers},
            verify=self.cfg.verify_tls, timeout=30,
        )
        resp.raise_for_status()
        body = self._json_or_error(resp, f"Keycloak token endpoint ({url})")
        tok = body.get("access_token") or (body.get("data") or {}).get("access_token")
        if not tok:
            raise PDCError(f"Keycloak returned no access_token "
                           f"(realm '{self.cfg.kc_realm}', client '{self.cfg.kc_client}'). "
                           f"Is Direct Access Grants enabled on the client?")
        return tok

    def _legacy_auth(self) -> str:
        """Legacy path: POST /api/public/<v>/auth (form-encoded) -> data.accessToken.
        Some instances return 200 with no token here — that's why auto exists."""
        url = f"{self.cfg.api_root}/auth"
        resp = requests.post(
            url,
            data={  # form-encoded, NOT json=
                "username": self.cfg.username,
                "password": self.cfg.password,
                "client_id": self.cfg.kc_client,
                "grant_type": "password",
                "scope": "openid profile email",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     **self.cfg.cf_headers},
            verify=self.cfg.verify_tls,
            timeout=30,
        )
        resp.raise_for_status()
        body = self._json_or_error(resp, f"PDC auth endpoint ({url})")
        data = body.get("data", {}) if isinstance(body, dict) else {}
        # accessToken is the documented field; tolerate older shapes just in case.
        tok = data.get("accessToken") or data.get("token")
        if not tok:
            raise PDCError("Auth succeeded but no accessToken in response")
        return tok

    @staticmethod
    def _json_or_error(resp: requests.Response, where: str) -> dict:
        """Parse a JSON body, turning a non-JSON reply into a clear PDCError.

        A 2xx HTML/text body almost always means the request reached the web
        UI / a reverse proxy instead of the API (e.g. an SPA catch-all), which
        otherwise surfaces only as 'Expecting value: line 1 column 1'.
        """
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            ctype = resp.headers.get("content-type", "?")
            text = resp.text or ""
            snippet = " ".join(text.split())[:160]
            low = text.lower()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}

            # Where did we actually land? A POST that Access intercepts is 302'd
            # to the team login on *.cloudflareaccess.com (or /cdn-cgi/access),
            # which requests follows — so the final URL / redirect chain is the
            # most reliable tell, even when the body is an opaque JS shell.
            final = getattr(resp, "url", "") or ""
            chain = " ".join([final] + [r.headers.get("location", "") for r in
                                        getattr(resp, "history", [])]).lower()
            access = ("cloudflareaccess.com" in chain or "/cdn-cgi/access" in chain
                      or "cf-access" in low or "cloudflareaccess.com" in low)
            edge = "cloudflare" in hdrs.get("server", "").lower() or "cf-ray" in hdrs
            challenge = (hdrs.get("cf-mitigated")
                         or "cf_authorization" in hdrs.get("set-cookie", "").lower()
                         or any(m in low for m in ("just a moment", "cf-browser-verification",
                                                   "attention required", "/cdn-cgi/challenge",
                                                   "enable javascript and cookies")))
            landed = f" Landed on: {final}." if final and final not in where else ""

            if access:
                raise PDCError(
                    f"{where} was intercepted by Cloudflare Access — the request was "
                    f"redirected to the Access login instead of reaching the API.{landed} "
                    f"The service token isn't being accepted yet: set "
                    f"PDC_CF_ACCESS_CLIENT_ID / PDC_CF_ACCESS_CLIENT_SECRET, AND in "
                    f"Cloudflare Zero Trust → Access → the application covering /keycloak "
                    f"and /api, add a policy with action 'Service Auth' that includes this "
                    f"service token. (Token 'Last Seen: Not Seen Yet' = no policy accepts "
                    f"it yet.) Body starts: {snippet!r}")
            if challenge or edge:
                raise PDCError(
                    f"{where} was intercepted by Cloudflare — it returned a challenge page "
                    f"(HTTP {resp.status_code}, {ctype}, cf-ray={hdrs.get('cf-ray','?')}), "
                    f"not the API.{landed} A browser passes this; an API client can't. Fix: "
                    f"a Cloudflare Access service token (PDC_CF_ACCESS_CLIENT_ID / "
                    f"PDC_CF_ACCESS_CLIENT_SECRET) with a matching Service Auth policy, or "
                    f"a WAF/Bot-Fight skip rule for /keycloak/* and /api/public/*, or point "
                    f"PDC_BASE_URL / PDC_KC_BASE at an internal address that bypasses "
                    f"Cloudflare. Body starts: {snippet!r}")
            raise PDCError(
                f"{where} returned a non-JSON {resp.status_code} response "
                f"(content-type: {ctype}). This usually means the request hit the "
                f"web UI/proxy rather than the API — check the Base URL and that "
                f"/keycloak is exposed on this host (or set PDC_KC_BASE/PDC_KC_REALM). "
                f"Body starts: {snippet!r}")

    def _headers(self) -> dict[str, str]:
        """Standard auth + JSON headers for every PDC call (plus any Cloudflare
        Access service-token headers needed to pass a tunnel in front of PDC)."""
        return {"Authorization": f"Bearer {self.token()}",
                "Content-Type": "application/json",
                **self.cfg.cf_headers}

    # ── low-level request plumbing ───────────────────────────
    def _post(self, path: str, body: dict, cache_key: str | None = None) -> dict:
        """POST helper with an optional read-through TTL cache.

        Facet/snapshot reads are the same a few times per dashboard load, so a
        short TTL cache (PDC_CACHE_TTL seconds) noticeably cuts PDC round-trips.
        Pass cache_key only for idempotent reads that are safe to serve stale.
        """
        if cache_key and self.cfg.cache_ttl:
            hit = self._cache.get(cache_key)
            if hit and (time.time() - hit[0]) < self.cfg.cache_ttl:
                return hit[1]  # fresh enough — skip the network
        data = self._request("post", path, json=body)
        if cache_key and self.cfg.cache_ttl:
            self._cache[cache_key] = (time.time(), data)
        return data

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Send a request, re-authenticating once on 401.

        PDC's JWTs are short-lived and there is no refresh token, so a token we
        cached earlier may have expired mid-session. On the first 401 we drop the
        cached token (forcing token() to re-auth with credentials) and retry
        once. We skip the retry when a fixed bearer token was configured, since
        re-auth wouldn't help in that case.
        """
        url = f"{self.cfg.api_root}{path}"
        for attempt in (1, 2):
            resp = requests.request(method, url, headers=self._headers(),
                                    verify=self.cfg.verify_tls, timeout=60, **kwargs)
            if resp.status_code == 401 and attempt == 1 and not self.cfg.bearer_token:
                self._token = None  # expired/invalid — force re-auth and retry
                continue
            resp.raise_for_status()
            return resp.json()
        # Both attempts 401'd: raise the second response's error for the caller.
        resp.raise_for_status()
        return resp.json()

    # ── reads ────────────────────────────────────────────────
    def facets(self, term: str = "*", facets: dict | None = None) -> list[dict]:
        """Return pre-aggregated counts for a query — the dashboard workhorse.

        Shape: [{ key, options: [{ name, value, count }] }]. Because PDC does the
        aggregation in OpenSearch, one call yields a ready-to-plot series with no
        client-side grouping. `facets` constrains the query (e.g. {"type":["TABLE"]}).
        Cached per (term, facets).
        """
        body = {"searchTerm": term, "searchFacets": facets or {}}
        # Stable cache key: sort the facet items so equivalent filters collide.
        key = f"facets::{term}::{sorted((facets or {}).items())}"
        return self._post("/search/facets", body, cache_key=key).get("data", [])

    def search(self, term: str = "*", facets: dict | None = None,
               page: int = 1, per_page: int = 30) -> dict:
        """Paginated asset rows (the full /search response, incl. pageInfo).

        Not cached: row-level results vary by page and are less hot than facets.
        Returns the raw payload so callers can read totalMatchCount from pageInfo.
        """
        body = {"searchTerm": term, "searchFacets": facets or {},
                "page": page, "perPage": per_page}
        return self._post("/search", body)

    def entities(self, filters: dict, size: int = 500, extended: bool = True):
        """Yield full entity records, transparently following cursor pagination.

        /entities/filter returns large result sets in pages keyed by an opaque
        cursor. This generator hides that: it keeps fetching and yielding until
        PDC stops returning a cursor. `extended=True` asks for the full attribute
        set (qualityScore, trustScore, sensitivity, owners, PII discoveries, …).
        Use it when you need per-asset detail rather than facet counts.
        """
        cursor = None
        while True:
            params = f"?size={size}&extended={str(extended).lower()}"
            if cursor:
                params += f"&cursor={cursor}"
            data = self._post(f"/entities/filter{params}", {"filters": filters})
            yield from data.get("data", [])
            cursor = data.get("cursorInfo", {}).get("cursor")
            if not cursor:  # no further pages
                break

    def trust_distribution(self, term: str = "*") -> list[dict]:
        """Count assets in each trust band — a small convenience over search().

        Runs one tiny (per_page=1) search per band and reads the total match
        count, so we get the three-bucket distribution without pulling any rows.
        Returns [{name, count}] in Untrusted/Trusted/Highly-Trusted order.
        """
        rows = []
        for label, lo, hi in _TRUST_BUCKETS:
            res = self.search(term, {"trustScore": [lo, hi]}, per_page=1)
            rows.append({"name": label,
                         "count": res.get("pageInfo", {}).get("totalMatchCount", 0)})
        return rows

    # ── data sources / connections ───────────────────────────
    # Catalog root entity types — the schemas/sources PDC has scanned. The public
    # API has NO list-all GET /data-sources (only POST /data-sources/by-ids), so
    # we enumerate roots via /entities/filter, the same way the Glossary Generator
    # does against this PDC.
    _ROOT_TYPES = ["SCHEMA", "DATA_SOURCE", "DATASOURCE", "DATABASE", "RESOURCE", "DIRECTORY"]
    # Facet keys a build might use to label the source dimension (fallback path).
    _SOURCE_FACET_KEYS = ("dataSource", "dataSourceName", "resource", "rootResource",
                          "source", "datasource")

    def data_sources(self) -> list[dict]:
        """List connected data sources (the connection/scan inventory).

        Primary path: enumerate catalog roots via POST /entities/filter. Fallback:
        if that yields nothing, read the data-source facet for names+counts. Either
        way returns dicts with name/type/assetCount/lastScanAt; never raises — an
        empty list just means "no live sources found", which the snapshot treats as
        a (noted) demo fallback rather than a crash.
        """
        out: list[dict] = []
        seen: set[str] = set()
        try:
            for e in self.entities({"types": self._ROOT_TYPES}, size=500, extended=True):
                fq = str(e.get("fqdn") or "")
                name = e.get("name") or e.get("fqdnDisplay") or fq
                key = fq or name
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append({
                    "name": name,
                    "type": e.get("type") or "",
                    # asset/scan fields vary by build; best-effort, may be None.
                    "assetCount": e.get("assetCount") or e.get("childCount")
                    or e.get("descendantCount"),
                    "lastScanAt": e.get("lastScanAt") or e.get("lastIngestAt")
                    or e.get("lastScanTime"),
                })
        except Exception:  # noqa: BLE001 — fall through to the facet path
            out = []

        if out:
            return out

        # Fallback: derive source names from a facet (names + counts only).
        try:
            for f in self.facets("*", {}):
                if f.get("key") in self._SOURCE_FACET_KEYS:
                    for o in f.get("options", []):
                        nm = o.get("name")
                        if nm and nm not in seen:
                            seen.add(nm)
                            out.append({"name": nm, "type": "",
                                        "assetCount": o.get("count"), "lastScanAt": None})
                    break
        except Exception:  # noqa: BLE001
            pass
        return out


# Process-wide singleton. Importing `client` everywhere keeps a single token +
# cache rather than re-authenticating per call site.
client = PDCClient()
