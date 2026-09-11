"""Compatibility layer. Frozen corpora are not rewritten."""

from __future__ import annotations

PROVIDER_TO_SEMANTIC = {
    "web_search": "web_research",
    "x_search": "x_research",
    "code_interpreter": "code_execution",
}
SEMANTIC = {"web_research", "x_research", "code_execution", "structured_output"}


def canonical_capability(name: str) -> str | None:
    if not name:
        return None
    if name in SEMANTIC:
        return name
    return PROVIDER_TO_SEMANTIC.get(name, f"unknown:{name}")


def canonical_set(names: list[str] | None) -> list[str]:
    out: list[str] = []
    for name in names or []:
        cap = canonical_capability(name)
        if cap and cap not in out:
            out.append(cap)
    return out
