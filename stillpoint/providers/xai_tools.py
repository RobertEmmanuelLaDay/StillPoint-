"""xAI-specific translation of provider-independent StillPoint tool requests."""
from __future__ import annotations

from ..capabilities import (
    CAP_CODE_EXECUTION,
    CAP_STRUCTURED_OUTPUT,
    CAP_WEB_RESEARCH,
    CAP_X_RESEARCH,
    ToolRequest,
)

XAI_WEB_SEARCH = "web_search"
XAI_X_SEARCH = "x_search"
XAI_CODE_INTERPRETER = "code_interpreter"


def to_xai_tools(tools: list[ToolRequest] | None) -> list[dict]:
    specs: list[dict] = []
    for tool in tools or []:
        if tool.capability == CAP_WEB_RESEARCH:
            spec: dict = {"type": XAI_WEB_SEARCH}
            filters = {}
            if tool.allowed_domains:
                filters["allowed_domains"] = list(tool.allowed_domains)
            if tool.excluded_domains:
                filters["excluded_domains"] = list(tool.excluded_domains)
            if filters:
                spec["filters"] = filters
            specs.append(spec)
        elif tool.capability == CAP_X_RESEARCH:
            spec = {"type": XAI_X_SEARCH}
            if tool.from_date:
                spec["from_date"] = tool.from_date
            if tool.to_date:
                spec["to_date"] = tool.to_date
            if tool.allowed_x_handles:
                spec["allowed_x_handles"] = list(tool.allowed_x_handles)
            if tool.excluded_x_handles:
                spec["excluded_x_handles"] = list(tool.excluded_x_handles)
            specs.append(spec)
        elif tool.capability == CAP_CODE_EXECUTION:
            specs.append({"type": XAI_CODE_INTERPRETER})
        elif tool.capability == CAP_STRUCTURED_OUTPUT:
            continue
        else:
            raise ValueError(f"unknown capability: {tool.capability}")
    return specs
