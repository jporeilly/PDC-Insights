"""LLM management endpoints used by the Settings page.

  GET  /api/llm/suggest   → the recommended model for THIS host (GPU/CPU aware)
  GET  /api/llm/models    → models currently installed in the local Ollama
  POST /api/llm/pull      → download a model, streaming progress back to the UI

Pull changes host state (downloads gigabytes), so it needs 'steward'; the reads
need 'viewer'. These only apply to the local (Ollama) provider; for commercial
providers there's nothing to pull.
"""
import json

import requests
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import settings
from ..model_advice import recommend
from ..security import Principal
from ._auth import json_body, require

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/suggest")
def suggest(request: Request, principal: Principal = Depends(require("viewer"))):
    """Recommend a model for this machine, and whether it's already installed.
    Optional ?mode=cpu|gpu forces the CPU/GPU toggle."""
    rec = recommend(request.query_params.get("mode") or None)
    rec["installed"] = rec["model"] in _installed()
    rec["provider"] = settings.llm.provider
    return rec


@router.get("/models")
def models(principal: Principal = Depends(require("viewer"))):
    """List locally installed Ollama models (empty if unreachable)."""
    return {"models": _installed(), "base_url": settings.llm.base_url}


@router.post("/pull")
async def pull(request: Request, principal: Principal = Depends(require("steward"))):
    """Pull a model into the local Ollama, streaming progress to the browser.

    Proxies Ollama's POST /api/pull (newline-delimited JSON). We forward each
    progress line as it arrives so the Settings page can show a live status,
    rather than blocking on a multi-GB download with no feedback.
    """
    model = (await json_body(request)).get("model", "").strip()
    if not model:
        return JSONResponse({"error": "model is required"}, status_code=400)
    base = settings.llm.base_url.rstrip("/")

    def stream():
        try:
            with requests.post(f"{base}/api/pull", json={"name": model, "stream": True},
                               stream=True, timeout=3600) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        yield line + b"\n"   # pass Ollama's NDJSON straight through
        except Exception as exc:  # noqa: BLE001 — surface as a final status line
            yield (json.dumps({"status": "error", "error": str(exc),
                               "hint": "Is Ollama running and reachable at LLM_BASE_URL?"}) + "\n").encode()

    # application/x-ndjson: one JSON object per line, read incrementally by the UI.
    return StreamingResponse(stream(), media_type="application/x-ndjson")


def _installed() -> list[str]:
    """Names of models installed in the local Ollama (best-effort)."""
    try:
        r = requests.get(f"{settings.llm.base_url.rstrip('/')}/api/tags", timeout=5)
        r.raise_for_status()
        return [m.get("name") for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001
        return []
