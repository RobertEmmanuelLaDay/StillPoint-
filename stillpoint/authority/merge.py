from __future__ import annotations
from .deterministic import assess_bundle
from .schema import INTENT_TO_FAMILY, AuthorityAssessment, AuthorityBundle
from .semantic import SemanticAuthority

def merge_assessments(*groups):
    by_intent={}; leftovers=[]
    for group in groups:
        for item in group:
            if item.intent=="none":leftovers.append(item);continue
            by_intent.setdefault(item.intent,item)
    assessments=list(by_intent.values()) or leftovers[:1] or [AuthorityAssessment()]
    return AuthorityBundle(assessments)

def merge(deterministic,semantic):return merge_bundles(AuthorityBundle([deterministic]),AuthorityBundle([semantic] if semantic else [])).to_compat()
def merge_bundles(deterministic,semantic):
    if semantic is None or not semantic.assessments:return deterministic
    det_restricted=set(deterministic.restricted_intents)
    extra=[]
    for item in semantic.assessments:
        if item.intent=="none" or item.intent in det_restricted:continue
        extra.append(item)
    return merge_assessments(deterministic.assessments,extra)

def apply_policy_floor(assessment,policy_intent):return apply_policy_floor_bundle(AuthorityBundle([assessment]),policy_intent).to_compat()
def apply_policy_floor_bundle(bundle,policy_intent):
    if not policy_intent or policy_intent=="none" or policy_intent in bundle.restricted_intents:return bundle
    family=INTENT_TO_FAMILY.get(policy_intent,"other_external")
    floor=AuthorityAssessment(family,"execute","unknown",1.0,f"policy floor {policy_intent}","policy")
    return merge_assessments(bundle.assessments,[floor])
def assess_authority(goal,*,semantic=None):return assess_authority_bundle(goal,semantic=semantic).to_compat()
def assess_authority_bundle(goal,*,semantic=None):
    det=assess_bundle(goal); sem=None
    if semantic is not None:
        item=semantic.assess(goal); sem=AuthorityBundle([item] if item else [])
    return merge_bundles(det,sem)
