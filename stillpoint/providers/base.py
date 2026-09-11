from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..capabilities import ToolRequest


@dataclass
class GenerateRequest:
    system: str
    prompt: str
    model: str
    tools: list[ToolRequest] = field(default_factory=list)
    effort: str = "medium"
    max_output_tokens: int | None = None
    cache_key: str | None = None
    json_schema: dict[str, Any] | None = None
    json_schema_name: str = "result"
    task_id: str | None = None
    phase: str | None = None


@dataclass
class ProviderResult:
    text: str
    model: str
    citations: list[str] = field(default_factory=list)
    annotation_urls: list[str] = field(default_factory=list)
    model_mentioned_urls: list[str] = field(default_factory=list)
    raw: dict | None = None
    provider_response_id: str | None = None
    usage: dict[str, Any] | None = None
    status: str = "completed"
    truncated: bool = False


class IncompleteResponseError(RuntimeError):
    def __init__(self, message: str, *, partial_text: str = "", provider_response_id: str | None = None):
        super().__init__(message)
        self.partial_text = partial_text
        self.provider_response_id = provider_response_id


class InProgressResponseError(RuntimeError):
    def __init__(self, message: str, *, provider_response_id: str | None = None, raw: dict | None = None):
        super().__init__(message)
        self.provider_response_id = provider_response_id
        self.raw = raw


class Provider(Protocol):
    def generate(self, *, system: str, prompt: str, model: str, tools=None, **kwargs) -> ProviderResult:
        ...
