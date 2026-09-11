from __future__ import annotations

from .deterministic import assess_bundle
from .schema import INTENT_TO_FAMILY, AuthorityAssessment, AuthorityBundle
from .semantic import SemanticAuthority


def merge_assessments(*groups: list[AuthorityAssessment]) -> AuthorityBundle:
    by_intent: dict[str, AuthorityAssessment] = {}
    leftovers: list[AuthorityAssessment] = []
    for group in groups:
        for item in group:
            if item.intent == "none":
                leftovers.append(item)
                continue
            prior = by_intent.get(item.intent)
            if prior is None:
                by_intent[item.intent] = item
    assessments = list(by_intent.values()) or leftovers[:1] or [AuthorityAssessment()]
    if by_intent and leftovers:
        assessments = list(by_intent.values())
    return AuthorityBundle(assessments)


def merge(deterministic: AuthorityAssessment, semantic: AuthorityAssessment | None) -> AuthorityAssessment:
    bundle = merge_bundles(
        AuthorityBundle([deterministic]),
        AuthorityBundle([semantic] if semantic else []),
    )
    return bundle.to_compat()


def merge_bundles(deterministic: AuthorityBundle, semantic: AuthorityBundle | None) -> AuthorityBundle:
    if semantic is None or not semantic.assessments:
        return deterministic
    det_restricted = set(deterministic.restricted_intents)
    extra: list[AuthorityAssessment] = []
    for item in semantic.assessments:
        if item.intent == "none":
            continue
        if item.intent in det_restricted:
            continue
        if not det_restricted:
            extra.append(item)
        else:
            extra.append(item)
    return merge_assessments(deterministic.assessments, extra)


def apply_policy_floor(assessment: AuthorityAssessment, policy_intent: str) -> AuthorityAssessment:
    return apply_policy_floor_bundle(AuthorityBundle([assessment]), policy_intent).to_compat()


def apply_policy_floor_bundle(bundle: AuthorityBundle, policy_intent: str) -> AuthorityBundle:
    if not policy_intent or policy_intent == "none":
        return bundle
    if policy_intent in bundle.restricted_intents:
        return bundle
    family = INTENT_TO_FAMILY.get(policy_intent, "other_external")
    floor = AuthorityAssessment(
        action_family=family,
        mode="execute",
        target="unknown",
        confidence=1.0,
        reason=f"policy floor {policy_intent}",
        source="policy",
    )
    return merge_assessments(bundle.assessments, [floor])


def assess_authority(goal: str, *, semantic: SemanticAuthority | None = None) -> AuthorityAssessment:
    return assess_authority_bundle(goal, semantic=semantic).to_compat()


def assess_authority_bundle(goal: str, *, semantic: SemanticAuthority | None = None) -> AuthorityBundle:
    det = assess_bundle(goal)
    sem = None
    if semantic is not None:
        item = semantic.assess(goal)
        sem = AuthorityBundle([item] if item else [])
    return merge_bundles(det, sem)
