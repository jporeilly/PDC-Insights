"""POST /api/chat — conversational dashboard builder.

Backs the in-app chat window: takes the conversation (and the spec built so far),
returns a short assistant reply plus the updated spec to preview. Uses the LLM
generator when a provider is configured, and a deterministic offline builder
otherwise so the chat works without a model. Building needs 'viewer'; saving the
result goes through POST /api/dashboards which needs 'steward'.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..catalog import QUERY_CATALOG
from ..chat_build import conversation_prompt, demo_build, summarize
from ..config import settings
from ..generator import generate
from ..security import Principal, audit
from ._auth import json_body, require

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(request: Request, principal: Principal = Depends(require("viewer"))):
    """One turn of the dashboard-building conversation.

    Request JSON:
        messages: [{role, content}, ...]  the chat so far (required)
        spec:     the dashboard built so far, if any (enables refinement —
                  "make panel 2 a line chart" edits this rather than starting over)
        section:  the active Analytics section, so the build is pinned to it
    Response JSON: {reply, spec, valid, errors, engine?} — `reply` is a short
    human summary for the transcript; `spec` is previewed and, on the user's
    request, saved via POST /api/dashboards (which re-validates and needs steward).
    """
    body = await json_body(request)
    messages = body.get("messages", [])
    spec = body.get("spec")                 # current spec to refine, or None for a fresh build
    section = body.get("section") or None   # pin the dashboard to this section if given
    if not messages:
        return JSONResponse({"error": "messages required"}, status_code=400)

    # The most recent user line is the active instruction; the demo builder works
    # off it directly, while the LLM path also gets earlier turns for context.
    instruction = next((m.get("content", "") for m in reversed(messages)
                        if m.get("role") == "user"), "")

    # Two build paths, same output shape, so the UI doesn't care which ran:
    if settings.llm.provider == "disabled":
        result = demo_build(instruction, spec, section)     # no model configured at all
    else:
        try:
            # LLM path: fold the conversation + current spec + section into one
            # grounded instruction; generate() validates and repairs once.
            result = generate(conversation_prompt(messages, spec, section), QUERY_CATALOG)
        except Exception:                                   # model unreachable mid-call
            # Degrade gracefully rather than error the chat — fall back to the
            # deterministic builder and flag it so the reply says "offline draft".
            result = demo_build(instruction, spec, section)
            result["engine"] = "demo"

    result["reply"] = summarize(result)     # transcript-friendly summary of what was built
    # Audit the build (who asked for what, and whether it validated).
    audit(principal, "chat_build", target=instruction[:80], valid=result.get("valid"))
    return result
