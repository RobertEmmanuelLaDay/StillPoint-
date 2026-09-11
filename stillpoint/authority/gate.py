from __future__ import annotations

from .merge import assess_authority_bundle
from .semantic import SemanticAuthority


def authority_intent(goal: str, *, provider=None) -> tuple[str, bool, str]:
    semantic = SemanticAuthority(provider) if provider is not None else None
    bundle = assess_authority_bundle(goal, semantic=semantic)
    return bundle.primary_intent, bundle.approval_required, bundle.reason


def authority_actions(goal: str, *, provider=None) -> list[str]:
    semantic = SemanticAuthority(provider) if provider is not None else None
    return assess_authority_bundle(goal, semantic=semantic).restricted_intents
