"""Local provider: Ollama (default) or any OpenAI-compatible local server.

Local is the recommended default for a governance tool — catalog and PII
metadata never leave the environment. Smaller local models are unreliable at raw
JSON, so when json_mode is on we use Ollama's native format=json constrained
decoding, which matters more for spec quality than model size.
"""
from __future__ import annotations

import requests

from ..config import settings
from .provider import LLMProvider


class LocalProvider(LLMProvider):
    name = "local"

    def __init__(self, cfg=settings.llm):
        self.cfg = cfg

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        """Call Ollama's /api/chat and return the assistant message text.

        num_predict caps output length (max_tokens). When json_mode is on we set
        format=json so the model is constrained to emit a single JSON value —
        the cheap way to make a 7B model reliably produce a valid spec.
        """
        payload = {
            "model": self.cfg.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"num_predict": self.cfg.max_tokens},
        }
        if json_mode and self.cfg.json_mode:
            payload["format"] = "json"  # Ollama constrained JSON decoding
        resp = requests.post(
            f"{self.cfg.base_url.rstrip('/')}/api/chat",
            json=payload, timeout=self.cfg.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def health(self) -> dict:
        """Probe Ollama by listing installed models (/api/tags)."""
        try:
            r = requests.get(f"{self.cfg.base_url.rstrip('/')}/api/tags", timeout=5)
            r.raise_for_status()
            models = [m.get("name") for m in r.json().get("models", [])]
            return {"provider": self.name, "ok": True, "model": self.cfg.model,
                    "detail": f"{len(models)} model(s) available"}
        except Exception as exc:  # noqa: BLE001 — health must never raise
            return {"provider": self.name, "ok": False, "detail": str(exc)}
