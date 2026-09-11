from __future__ import annotations
from .merge import assess_authority_bundle
from .semantic import SemanticAuthority

def authority_bundle(goal: str, *, provider=None, model: str|None=None):
    semantic=SemanticAuthority(provider,model=model) if provider is not None else None
    return assess_authority_bundle(goal,semantic=semantic)
def authority_intent(goal: str, *, provider=None, model: str|None=None):
    bundle=authority_bundle(goal,provider=provider,model=model)
    return bundle.primary_intent,bundle.approval_required,bundle.reason
def authority_actions(goal: str, *, provider=None, model: str|None=None):
    return authority_bundle(goal,provider=provider,model=model).restricted_intents
