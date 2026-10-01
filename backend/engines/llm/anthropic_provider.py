"""
Claude provider (official Anthropic SDK).
Structured output constrains the response to the Pydantic schema; streaming keeps long
lecture plans (plus adaptive thinking) clear of HTTP timeouts. The schema goes in
output_config.format rather than the SDK's output_format helper, because the helper parses
each text block as it closes - before stop_reason is known - so a refusal or a max_tokens
cut would surface as a misleading JSON error.
"""
from typing import Any, Dict, Optional, Type

import anthropic
from pydantic import ValidationError

from backend.engines.llm.base import LLMError, T

# Models that accept the server-side refusal fallback (array form, beta 2026-06-01).
_FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1"}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, effort: str = "high", timeout: float = 600.0, client: Optional[anthropic.Anthropic] = None):
        self.model = model
        self.effort = effort
        # Credentials resolve from ANTHROPIC_API_KEY (or an `ant auth login` profile).
        self.client = client or anthropic.Anthropic(timeout=timeout)

    def generate(self, *, system: str, user: str, schema: Type[T], max_tokens: int) -> T:
        output_config: Dict[str, Any] = {"format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}}
        extra: Dict[str, Any] = {}
        if not self.model.startswith("claude-haiku"):  # Haiku 4.5 predates adaptive thinking / effort
            extra["thinking"] = {"type": "adaptive"}
            output_config["effort"] = self.effort
        if self.model in _FALLBACK_MODELS:
            extra["betas"] = ["server-side-fallback-2026-06-01"]
            extra["fallbacks"] = [{"model": "claude-opus-4-8"}]

        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,
                **extra,
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AuthenticationError:
            raise LLMError("authentication failed - check ANTHROPIC_API_KEY")
        except anthropic.PermissionDeniedError as e:
            raise LLMError(f"permission denied: {e.message}")
        except anthropic.NotFoundError:
            raise LLMError(f"model '{self.model}' not found - check SCIFORGE_LLM_MODEL")
        except anthropic.RateLimitError:
            raise LLMError("rate limited - retry later")
        except anthropic.APIStatusError as e:
            raise LLMError(f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            raise LLMError("network error - could not reach the Anthropic API")

        if message.stop_reason == "refusal":
            category = message.stop_details.category if message.stop_details else None
            raise LLMError(f"model declined the request (category: {category})")
        if message.stop_reason == "max_tokens":
            raise LLMError(f"output truncated at max_tokens={max_tokens}")

        # After a fallback switch, only text from the model that finished the turn is the answer.
        blocks = message.content
        start = max((i for i, b in enumerate(blocks) if b.type == "fallback"), default=-1) + 1
        text = "".join(b.text for b in blocks[start:] if b.type == "text")
        try:
            return schema.model_validate_json(text)
        except ValidationError as e:
            raise LLMError(f"output failed schema validation ({e.error_count()} errors)")
