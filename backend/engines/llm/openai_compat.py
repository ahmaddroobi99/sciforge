"""
OpenAI-compatible chat-completions provider: xAI (Grok), OpenAI and local Ollama.
JSON mode plus the schema in the system prompt, validated with Pydantic, with one repair round.
"""
import json
import re
from typing import Any, Dict, List, Optional, Type

import httpx
from pydantic import ValidationError

from backend.engines.llm.base import LLMError, T

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


class OpenAICompatibleProvider:
    def __init__(self, name: str, base_url: str, api_key: str, model: str, timeout: float = 600.0,
                 http: Optional[httpx.Client] = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.http = http or httpx.Client(timeout=timeout)

    def generate(self, *, system: str, user: str, schema: Type[T], max_tokens: int) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": f"{system}\n\nReply with ONLY a JSON object that validates against this JSON Schema:\n{schema_json}"},
            {"role": "user", "content": user},
        ]
        content = self._chat(messages, max_tokens)
        try:
            return schema.model_validate_json(_FENCE.sub("", content))
        except ValidationError as e:
            messages += [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"That JSON failed validation:\n{e}\nReply with the corrected JSON object only."},
            ]
        content = self._chat(messages, max_tokens)
        try:
            return schema.model_validate_json(_FENCE.sub("", content))
        except ValidationError as e:
            raise LLMError(f"output failed schema validation after one repair ({e.error_count()} errors)")

    def _chat(self, messages: List[Dict[str, str]], max_tokens: int) -> str:
        # OpenAI's current models take max_completion_tokens; xAI and Ollama take max_tokens.
        limit_key = "max_completion_tokens" if self.name == "openai" else "max_tokens"
        body = {
            "model": self.model,
            "messages": messages,
            limit_key: max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            r = self.http.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
        except httpx.HTTPError as e:
            raise LLMError(f"network error calling {self.name}: {e}")
        if r.status_code != 200:
            raise LLMError(f"{self.name} HTTP {r.status_code}: {_error_message(r)}")

        choice = r.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise LLMError(f"output truncated at {limit_key}={max_tokens}")
        return choice["message"].get("content") or ""


def _error_message(r: httpx.Response) -> str:
    try:
        data: Any = r.json()
    except ValueError:
        return r.text[:300]
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get("message", err))[:300]
    return str(err or data)[:300]
