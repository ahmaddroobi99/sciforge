"""
SciForge LLM provider contract.
"""
from typing import Protocol, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """A provider call failed or returned output that does not validate against the schema."""


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, *, system: str, user: str, schema: Type[T], max_tokens: int) -> T:
        """Returns a validated instance of `schema` or raises LLMError."""
        ...
