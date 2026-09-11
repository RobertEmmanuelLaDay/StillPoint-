from __future__ import annotations

import re

_SPLIT = re.compile(
    r"(?<=[.!?])\s+|(?:\n+)|(?:;\s+)|(?:\s+and then\s+)|(?:\s+but then\s+)|(?:,\s+then\s+)",
    re.I,
)


def split_clauses(goal: str) -> list[str]:
    text = (goal or "").strip()
    if not text:
        return []
    parts = [p.strip(" \t-") for p in _SPLIT.split(text) if p and p.strip()]
    return parts or [text]
