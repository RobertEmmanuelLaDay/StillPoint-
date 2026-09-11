from __future__ import annotations

import re

_SPLIT = re.compile(
    r"(?<=[.!?])\s+|(?:\n+)|(?:;\s+)|(?:\s+and then\s+)|(?:\s+but then\s+)|(?:,\s+then\s+)|"
    r"(?:\s+and\s+(?=(?:send|email|transmit|deliver|forward|publish|release|buy|spend|pay|purchase|sign|initial|execute|delete|wipe|destroy|upload|post|tweet)\b))",
    re.I,
)


def split_clauses(goal: str) -> list[str]:
    text = (goal or "").strip()
    if not text:
        return []
    parts = [p.strip(" \t-") for p in _SPLIT.split(text) if p and p.strip()]
    return parts or [text]
