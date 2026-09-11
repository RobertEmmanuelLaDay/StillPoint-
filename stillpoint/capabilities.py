from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

CAP_WEB_RESEARCH = "web_research"
CAP_X_RESEARCH = "x_research"
CAP_CODE_EXECUTION = "code_execution"
CAP_STRUCTURED_OUTPUT = "structured_output"



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
    """Compatibility shim; xAI mapping is implemented in the xAI provider layer."""
    from .providers.xai_tools import to_xai_tools as _provider_to_xai_tools
    return _provider_to_xai_tools(tools)


SOURCE_REVIEW_MARKERS = ("source integrity", "citation", "fact-check", "fact check", "sources")


def tool_request_to_dict(request: ToolRequest) -> dict:
    return {
        "capability": request.capability,
        "allowed_domains": list(request.allowed_domains),
        "excluded_domains": list(request.excluded_domains),
        "allowed_x_handles": list(request.allowed_x_handles),
        "excluded_x_handles": list(request.excluded_x_handles),
        "from_date": request.from_date,
        "to_date": request.to_date,
    }


def tool_request_from_dict(raw: dict) -> ToolRequest:
    capability = str(raw.get("capability") or "")
    if capability == CAP_WEB_RESEARCH:
        return web_research(
            allowed_domains=list(raw.get("allowed_domains") or []),
            excluded_domains=list(raw.get("excluded_domains") or []),
        )
    if capability == CAP_X_RESEARCH:
        return x_research(
            from_date=raw.get("from_date"),
            to_date=raw.get("to_date"),
            allowed_x_handles=list(raw.get("allowed_x_handles") or []),
            excluded_x_handles=list(raw.get("excluded_x_handles") or []),
            require_date_window=False,
        )
    if capability == CAP_CODE_EXECUTION:
        return code_execution()
    if capability == CAP_STRUCTURED_OUTPUT:
        return ToolRequest(capability=CAP_STRUCTURED_OUTPUT)
    raise ValueError(f"unknown capability: {capability}")


def capabilities_for_call(
    *,
    agent_id: str,
    plan_capabilities: list[str],
    agent_capabilities: list[str] | None = None,
    review_reason: str = "",
    scoped_requests: list[dict] | None = None,
) -> list[ToolRequest]:
    """Request-scoped semantic capabilities. Roles do not permanently own tools."""
    caps = list(agent_capabilities if agent_capabilities is not None else plan_capabilities)
    if agent_id == "stillpoint":
        if any(m in (review_reason or "").lower() for m in SOURCE_REVIEW_MARKERS):
            return [web_research()]
        return []
    if agent_id in {"author", "orchestra"}:
        return []

    if scoped_requests is not None:
        requested = [tool_request_from_dict(r) for r in scoped_requests]
        allowed_by_role = {
            "research": {CAP_WEB_RESEARCH, CAP_X_RESEARCH},
            "press": {CAP_WEB_RESEARCH},
            "signal": {CAP_WEB_RESEARCH, CAP_X_RESEARCH},
            "ledger": {CAP_WEB_RESEARCH, CAP_CODE_EXECUTION},
            "builder": {CAP_WEB_RESEARCH, CAP_CODE_EXECUTION},
        }.get(agent_id, set())
        return [r for r in requested if r.capability in allowed_by_role and r.capability in caps]

    out: list[ToolRequest] = []
    if CAP_WEB_RESEARCH in caps and agent_id in {"research", "press", "signal", "ledger", "builder"}:
        out.append(web_research())
    if CAP_X_RESEARCH in caps and agent_id in {"signal", "research"}:
        out.append(x_research(from_date=(date.today() - timedelta(days=30)).isoformat()))
    if CAP_CODE_EXECUTION in caps and agent_id in {"ledger", "builder"}:
        out.append(code_execution())
    return out
