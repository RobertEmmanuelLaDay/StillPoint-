# compatibility only; consequential authority lives in stillpoint.authority
from __future__ import annotations
from .authority.deterministic import assess_bundle

def action_intent(goal:str)->str:
    return assess_bundle(goal).primary_intent

def approval_reason_for(intent:str)->str:
    return {"send_email":"send external communication","publish":"publish or release publicly","social_post":"post to a public account","spend":"move or commit money","sign":"accept a binding commitment","delete":"destructive external change","other_external":"external action","none":""}.get(intent,"")
