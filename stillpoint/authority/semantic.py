from __future__ import annotations
import json
from .schema import AUTHORITY_SCHEMA, AuthorityAssessment, FAMILIES, MODES, TARGETS
SYSTEM="Classify a CEO request for external-action authority only. Return JSON. Do not invent facts. Tools are forbidden."

def parse_semantic(raw):
    if not isinstance(raw,dict):return None
    if any(k not in AUTHORITY_SCHEMA["properties"] for k in raw):return None
    if any(k not in raw for k in AUTHORITY_SCHEMA["required"]):return None
    family=raw.get("action_family");mode=raw.get("mode");target=raw.get("target")
    if family not in FAMILIES or mode not in MODES or target not in TARGETS:return None
    if type(raw.get("reason")) is not str:return None
    conf=raw.get("confidence")
    if isinstance(conf,bool) or not isinstance(conf,(int,float)):return None
    conf=float(conf)
    if not 0<=conf<=1:return None
    return AuthorityAssessment(family,mode,target,conf,raw["reason"],"semantic")

class SemanticAuthority:
    def __init__(self,provider=None,model:str|None=None):self.provider=provider;self.model=model
    def assess(self,goal):
        if self.provider is None:return None
        model=self.model or getattr(self.provider,"default_model",None) or "default"
        try:
            result=self.provider.generate(system=SYSTEM,prompt=f"CEO REQUEST:\n{goal}",model=model,tools=[],effort="low",json_schema=AUTHORITY_SCHEMA,json_schema_name="authority_assessment")
            raw=json.loads(result.text)
        except Exception:return None
        return parse_semantic(raw)
