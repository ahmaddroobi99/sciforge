"""
SciForge LLM Router
The only entry point engines use to call a model. Engines ask for a schema-validated
Pydantic object and get None back when no provider is configured or the call fails,
so they can fall back to their deterministic templates and the pipeline always completes.
"""
import os
from typing import Any, Dict, Optional, Type

from backend import config
from backend.engines.llm.base import LLMProvider, T


class LLMRouter:
    def __init__(self, provider: Optional[LLMProvider] = None, reason: str = ""):
        self.provider = provider
        self.reason = reason  # why no provider is active, shown in /api/health
        self.last_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.provider is not None

    @property
    def label(self) -> str:
        return f"{self.provider.name}:{self.provider.model}" if self.provider else "templates"

    def describe(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "provider": self.provider.name if self.provider else None,
            "model": self.provider.model if self.provider else None,
            "reason": self.reason,
            "last_error": self.last_error,
        }

    def generate(self, task: str, *, system: str, user: str, schema: Type[T], max_tokens: int = 32000) -> Optional[T]:
        if not self.provider:
            return None
        try:
            result = self.provider.generate(system=system, user=user, schema=schema, max_tokens=max_tokens)
        except Exception as e:  # any provider failure degrades to templates instead of failing the compile
            self.last_error = f"{task}: {e}"
            print(f"[SciForge LLM] {self.label} failed on '{task}': {e}")
            return None
        self.last_error = None
        return result


def build_router() -> LLMRouter:
    """Builds the router from SCIFORGE_LLM_* settings and provider API keys (env or .env)."""
    name = config.LLM_PROVIDER
    if name in ("none", "off", "templates"):
        return LLMRouter(reason="disabled by SCIFORGE_LLM_PROVIDER")
    if name == "auto":
        name = next((p for p, env in config.LLM_KEY_ENV.items() if os.getenv(env)), "")
        if not name:
            keys = ", ".join(config.LLM_KEY_ENV.values())
            return LLMRouter(reason=f"no API key found (set one of {keys} in .env)")

    model = config.LLM_MODEL or config.LLM_DEFAULT_MODELS.get(name, "")
    try:
        if name == "anthropic":
            from backend.engines.llm.anthropic_provider import AnthropicProvider
            return LLMRouter(AnthropicProvider(model=model, effort=config.LLM_EFFORT, timeout=config.LLM_TIMEOUT_SEC))

        if name in config.LLM_BASE_URLS:
            from backend.engines.llm.openai_compat import OpenAICompatibleProvider
            key_env = config.LLM_KEY_ENV.get(name)
            api_key = os.getenv(key_env, "") if key_env else "ollama"  # Ollama ignores the key
            if not api_key:
                return LLMRouter(reason=f"{key_env} is not set")
            return LLMRouter(OpenAICompatibleProvider(
                name=name,
                base_url=config.LLM_BASE_URLS[name],
                api_key=api_key,
                model=model,
                timeout=config.LLM_TIMEOUT_SEC,
            ))
    except Exception as e:
        return LLMRouter(reason=f"could not initialise provider '{name}': {e}")

    return LLMRouter(reason=f"unknown provider '{name}'")


_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = build_router()
    return _router
