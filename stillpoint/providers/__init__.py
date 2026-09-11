from __future__ import annotations

from .mock import MockProvider
from .xai import XAIProvider


def make_provider(name: str, timeout_seconds: int = 3600):
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockProvider()
    if normalized == "xai":
        return XAIProvider(timeout_seconds=timeout_seconds)
    raise ValueError(f"unsupported provider: {name}")
