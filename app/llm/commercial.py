"""Commercial provider: Anthropic Messages API or OpenAI Chat Completions.

Stronger structured output than a small local model, but metadata leaves the
environment and you pay per token — so for a governance product this is opt-in,
selected via LLM_PROVIDER=anthropic|openai. One class handles both by branching
on the flavour, since only the request/response shapes differ.
"""
from __future__ import annotations

import requests

from ..config import settings
from .provider import LLMProvider


class CommercialProvider(LLMProvider):
    def __init__(self, flavour: str, cfg=settings.llm):
        # flavour is "anthropic" or "openai"; it also becomes the provider name
        # reported by health() and audit.
        self.name = flavour
        self.cfg = cfg

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        """Dispatch to the right API shape and return the text completion."""
        if self.name == "anthropic":
            return self._anthropic(system, user)
        return self._openai(system, user, json_mode)

    def _anthropic(self, system: str, user: str) -> str:
        """Anthropic Messages API: system is a top-level field; text lives in
        content blocks, which we concatenate."""
        resp = requests.post(
            f"{self.cfg.base_url.rstrip('/')}/v1/messages",
            headers={"x-api-key": self.cfg.api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": self.cfg.model, "max_tokens": self.cfg.max_tokens,
                  "system": system, "messages": [{"role": "user", "content": user}]},
            timeout=self.cfg.timeout,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    def _openai(self, system: str, user: str, json_mode: bool) -> str:
        """OpenAI-compatible Chat Completions. response_format=json_object asks
        for strict JSON when json_mode is on."""
        body = {"model": self.cfg.model, "max_tokens": self.cfg.max_tokens,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        resp = requests.post(
            f"{self.cfg.base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.cfg.api_key}"},
            json=body, timeout=self.cfg.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def health(self) -> dict:
        """We can't cheaply verify a key without spending tokens, so just report
        whether one is present."""
        ok = bool(self.cfg.api_key)
        return {"provider": self.name, "ok": ok, "model": self.cfg.model,
                "detail": "API key present" if ok else "missing LLM_API_KEY"}
