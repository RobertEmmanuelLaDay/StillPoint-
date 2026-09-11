from __future__ import annotations

from dataclasses import dataclass


CAP_WEB_RESEARCH = "web_research"
CAP_X_RESEARCH = "x_research"
CAP_CODE_EXECUTION = "code_execution"
CAP_STRUCTURED_OUTPUT = "structured_output"

XAI_WEB_SEARCH = "web_search"
XAI_X_SEARCH = "x_search"
XAI_CODE_INTERPRETER = "code_interpreter"  # documented Responses/OpenAI-compatible name


@dataclass(frozen=True)
class ToolRequest:
    capability: str
    allowed_domains: tuple[str, ...] = ()
    excluded_domains: tuple[str, ...] = ()
    allowed_x_handles: tuple[str, ...] = ()
    excluded_x_handles: tuple[str, ...] = ()
    from_date: str | None = None
    to_date: str | None = None


def web_research(*, allowed_domains=None, excluded_domains=None) -> ToolRequest:
    if allowed_domains and excluded_domains:
        raise ValueError("web_research: allowed_domains and excluded_domains are mutually exclusive")
    if allowed_domains and len(allowed_domains) > 5:
        raise ValueError("web_research allowed_domains max 5")
    if excluded_domains and len(excluded_domains) > 5:
        raise ValueError("web_research excluded_domains max 5")
    return ToolRequest(
        capability=CAP_WEB_RESEARCH,
        allowed_domains=tuple(allowed_domains or ()),
        excluded_domains=tuple(excluded_domains or ()),
    )


def x_research(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    allowed_x_handles=None,
    excluded_x_handles=None,
    require_date_window: bool = True,
) -> ToolRequest:
    """
    Date window: StillPoint cost/scope policy when require_date_window=True.
    xAI API does not document from_date as required. Marked policy, not vendor requirement.
    """
    if allowed_x_handles and excluded_x_handles:
        raise ValueError("x_research: allowed and excluded handles are mutually exclusive")
    if allowed_x_handles and len(allowed_x_handles) > 20:
        raise ValueError("x_research allowed_x_handles max 20")
    if excluded_x_handles and len(excluded_x_handles) > 20:
        raise ValueError("x_research excluded_x_handles max 20")
    if require_date_window and not from_date:
        raise ValueError("StillPoint policy: x_research requires from_date")
    return ToolRequest(
        capability=CAP_X_RESEARCH,
        allowed_x_handles=tuple(allowed_x_handles or ()),
        excluded_x_handles=tuple(excluded_x_handles or ()),
        from_date=from_date,
        to_date=to_date,
    )


def code_execution() -> ToolRequest:
    return ToolRequest(capability=CAP_CODE_EXECUTION)


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


SOURCE_REVIEW_MARKERS = ("source integrity", "citation", "fact-check", "fact check", "sources")


def capabilities_for_call(*, agent_id: str, plan_capabilities: list[str], review_reason: str = "") -> list[ToolRequest]:
    """Request-scoped. Roles do not own tools."""
    caps = list(plan_capabilities)
    if agent_id == "stillpoint":
        if any(m in (review_reason or "").lower() for m in SOURCE_REVIEW_MARKERS):
            return [web_research()]
        return []
    if agent_id == "author":
        return []
    if agent_id == "orchestra":
        return []
    out: list[ToolRequest] = []
    if "web_research" in caps and agent_id in {"research", "press", "signal", "ledger", "builder"}:
        out.append(web_research())
    if "x_research" in caps and agent_id in {"signal", "research"}:
        from datetime import date, timedelta
        out.append(x_research(from_date=(date.today() - timedelta(days=30)).isoformat()))
    if "code_execution" in caps and agent_id in {"ledger", "builder"}:
        out.append(code_execution())
    return out
