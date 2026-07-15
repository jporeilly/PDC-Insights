"""Provider-agnostic LLM access.

The rest of the app only ever calls get_provider().complete(...). Swapping
between an air-gapped local model and a commercial API is therefore an env
change (LLM_PROVIDER), never a code change. Three concrete backends implement
the LLMProvider interface: local (Ollama), commercial (Anthropic/OpenAI), and a
disabled no-op.
"""
from __future__ import annotations

import abc

from ..config import settings


class LLMProvider(abc.ABC):
    """The one interface every backend implements."""

    name: str = "base"

    @abc.abstractmethod
    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        """Return the model's completion as text.

        When json_mode is True the caller expects parseable JSON back; providers
        that support constrained decoding (Ollama format=json, OpenAI
        json_object) should enable it so weaker models can't emit prose.
        """

    def health(self) -> dict:
        """Lightweight reachability check for the Settings > Test button.

        Returns {provider, ok, detail, ...}. Default is "not implemented"; each
        backend overrides with a real probe (e.g. list local models / check key).
        """
        return {"provider": self.name, "ok": False, "detail": "not implemented"}


class DisabledProvider(LLMProvider):
    """Used when LLM_PROVIDER is unset/'disabled'. Generation is off; reads and
    dashboards still work. complete() fails loudly so misconfiguration is obvious."""

    name = "disabled"

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        raise RuntimeError("LLM generation is disabled (set LLM_PROVIDER).")

    def health(self) -> dict:
        return {"provider": self.name, "ok": True, "detail": "AI generation turned off"}


# Memoised so we build (and probe) the chosen provider once per process.
_cache: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the configured provider, constructing it on first use.

    Selection is driven entirely by LLM_PROVIDER: 'local' -> Ollama-compatible,
    'anthropic'/'openai' -> commercial HTTP API, anything else -> disabled.
    """
    global _cache
    if _cache is not None:
        return _cache
    provider = settings.llm.provider
    if provider == "local":
        from .local import LocalProvider
        _cache = LocalProvider()
    elif provider in {"anthropic", "openai"}:
        from .commercial import CommercialProvider
        _cache = CommercialProvider(provider)
    else:
        _cache = DisabledProvider()
    return _cache
