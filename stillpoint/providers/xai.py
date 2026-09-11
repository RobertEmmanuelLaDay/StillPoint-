from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.request import Request

from ..capabilities import ToolRequest
from .xai_tools import to_xai_tools
from .base import GenerateRequest, IncompleteResponseError, InProgressResponseError, ProviderResult

ENDPOINT = "https://api.x.ai/v1/responses"
RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}
MAX_RETRIES = 5
MAX_SLEEP = 30.0
URL_RE = re.compile(r"https?://[^\s)>\"]+", re.I)


class XAIProvider:
    def __init__(
        self,
        timeout_seconds: int = 3600,
        api_key: str | None = None,
        urlopen: Callable | None = None,
        sleep: Callable[[float], None] | None = None,
        default_model: str | None = None,
    ):
        self.default_model = default_model or os.getenv("XAI_MODEL") or "grok-4.6"
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY is not set. Add it to your environment before live execution.")
        self.timeout_seconds = timeout_seconds
        self.endpoint = ENDPOINT
        self._urlopen = urlopen or urllib.request.urlopen
        self._sleep = sleep or time.sleep

    def generate(self, *, system: str, prompt: str, model: str, tools=None, **kwargs) -> ProviderResult:
        request = GenerateRequest(
            system=system,
            prompt=prompt,
            model=model,
            tools=self._coerce_tools(tools),
            effort=str(kwargs.get("effort") or "medium"),
            max_output_tokens=kwargs.get("max_output_tokens"),
            cache_key=kwargs.get("cache_key") or kwargs.get("prompt_cache_key"),
            json_schema=kwargs.get("json_schema"),
            json_schema_name=str(kwargs.get("json_schema_name") or "result"),
            task_id=kwargs.get("task_id"),
            phase=kwargs.get("phase"),
        )
        return self.generate_request(request)

    def generate_request(self, request: GenerateRequest) -> ProviderResult:
        payload = self._payload(request, format_mode="response_format")
        last_error: Exception | None = None
        used_fallback = False
        for attempt in range(MAX_RETRIES):
            http = Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "stillpoint/5.1",
                },
                method="POST",
            )
            try:
                with self._urlopen(http, timeout=self.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return self._result(data, fallback_model=request.model)
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                last_error = RuntimeError(f"xAI HTTP {exc.code}: {err_body[:1000]}")
                # Inferred: if documented response_format is rejected, retry once with text.format.
                if (
                    exc.code == 400
                    and request.json_schema
                    and not used_fallback
                    and "response_format" in err_body.lower()
                ):
                    payload = self._payload(request, format_mode="text.format")
                    used_fallback = True
                    continue
                if exc.code not in RETRYABLE_HTTP:
                    break
                if attempt < MAX_RETRIES - 1:
                    self._sleep(self._retry_delay(exc, attempt))
            except (IncompleteResponseError, InProgressResponseError):
                raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    self._sleep(min(MAX_SLEEP, float(2 ** attempt)))
        raise RuntimeError(f"xAI request failed after retries: {last_error}")

    def _payload(self, request: GenerateRequest, *, format_mode: str) -> dict[str, Any]:
        cache_key = request.cache_key or (f"stillpoint:{request.task_id}" if request.task_id else None)
        payload: dict[str, Any] = {
            "model": request.model,
            "input": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "store": False,
        }
        if cache_key:
            payload["prompt_cache_key"] = cache_key
        if request.effort:
            payload["reasoning"] = {"effort": request.effort}
        if request.max_output_tokens:
            payload["max_output_tokens"] = request.max_output_tokens
        tools = to_xai_tools(request.tools)
        if tools:
            payload["tools"] = tools
        if request.json_schema:
            schema_block = {
                "name": request.json_schema_name,
                "schema": request.json_schema,
                "strict": True,
            }
            if format_mode == "response_format":
                # Documented primary: Structured Outputs guide uses response_format.json_schema
                payload["response_format"] = {"type": "json_schema", "json_schema": schema_block}
            else:
                # Inferred fallback only after documented field is rejected
                payload["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": request.json_schema_name,
                        "schema": request.json_schema,
                        "strict": True,
                    }
                }
        return payload

    @staticmethod
    def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
        header = ""
        if getattr(exc, "headers", None):
            header = exc.headers.get("Retry-After") or ""
        if header:
            try:
                return min(MAX_SLEEP, max(0.0, float(header)))
            except ValueError:
                pass
        return min(MAX_SLEEP, float(2 ** attempt))

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"]
        chunks: list[str] = []
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for content in item.get("content", []) or []:
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        chunks.append(content["text"])
            elif isinstance(item.get("text"), str):
                chunks.append(item["text"])
        if chunks:
            return "\n".join(chunks).strip()
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            if isinstance(message.get("content"), str):
                return message["content"]
        return ""

    @classmethod
    def _extract_citations(cls, data: dict[str, Any]) -> list[str]:
        """V5 compatibility: unique url keys under output (annotations included)."""
        found: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                cls._add_url(found, value.get("url"))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(data.get("output", []))
        return found

    @staticmethod
    def _add_url(found: list[str], url: Any) -> None:
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in found:
            found.append(url)

    @classmethod
    def _provider_citations(cls, data: dict[str, Any]) -> list[str]:
        found: list[str] = []
        top = data.get("citations")
        if isinstance(top, list):
            for item in top:
                if isinstance(item, str):
                    cls._add_url(found, item)
                elif isinstance(item, dict):
                    cls._add_url(found, item.get("url"))
        return found

    @classmethod
    def _annotation_urls(cls, data: dict[str, Any]) -> list[str]:
        found: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if value.get("type") in {"url_citation", "annotation"} or "url" in value:
                    if "url" in value and (
                        value.get("type") in {"url_citation", "annotation"}
                        or "annotations" in str(value.keys())
                    ):
                        cls._add_url(found, value.get("url"))
                if "annotations" in value and isinstance(value["annotations"], list):
                    for ann in value["annotations"]:
                        if isinstance(ann, dict):
                            cls._add_url(found, ann.get("url"))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(data.get("output", []))
        return found

    @classmethod
    def _model_mentioned_urls(cls, text: str, excluded: list[str]) -> list[str]:
        mentioned: list[str] = []
        skip = set(excluded)
        for match in URL_RE.findall(text or ""):
            url = match.rstrip(".,;")
            if url not in skip and url not in mentioned:
                mentioned.append(url)
        return mentioned

    def _result(self, data: dict[str, Any], *, fallback_model: str) -> ProviderResult:
        text = self._extract_text(data)
        status = str(data.get("status") or "completed")
        provider_id = str(data["id"]) if data.get("id") else None
        if status == "incomplete":
            raise IncompleteResponseError(
                "xAI response status=incomplete",
                partial_text=text,
                provider_response_id=provider_id,
            )
        if status == "in_progress":
            raise InProgressResponseError(
                "xAI response status=in_progress",
                provider_response_id=provider_id,
                raw=data,
            )
        if status != "completed":
            raise RuntimeError(f"xAI response not completed (status={status})")
        if not text:
            raise RuntimeError("xAI response contained no readable text output")
        provider_cites = self._provider_citations(data)
        annotation_cites = self._annotation_urls(data)
        # Compatibility: V5 _extract_citations walked annotations. Keep union for .citations
        # when top-level citations is empty so old unique-url test still works via _extract_citations.
        citations = list(provider_cites)
        for url in annotation_cites:
            if url not in citations:
                citations.append(url)
        return ProviderResult(
            text=text,
            model=str(data.get("model") or fallback_model),
            citations=citations,
            annotation_urls=annotation_cites,
            model_mentioned_urls=self._model_mentioned_urls(text, citations),
            raw=data,
            provider_response_id=provider_id,
            usage=dict(data["usage"]) if isinstance(data.get("usage"), dict) else None,
            status=status,
            truncated=bool(data.get("incomplete_details")),
        )

    @staticmethod
    def _coerce_tools(tools) -> list[ToolRequest]:
        if not tools:
            return []
        if isinstance(tools, list) and tools and isinstance(tools[0], ToolRequest):
            return list(tools)
        from ..capabilities import code_execution, web_research
        mapped: list[ToolRequest] = []
        for item in tools or []:
            if item == "web_search":
                mapped.append(web_research())
            elif item == "x_search":
                from ..capabilities import x_research
                mapped.append(x_research(from_date="1970-01-01"))
            elif item in {"code_interpreter", "code_execution"}:
                mapped.append(code_execution())
        return mapped
