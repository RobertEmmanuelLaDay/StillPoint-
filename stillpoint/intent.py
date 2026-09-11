"""Separate requested work from external-action intent from approval."""

from __future__ import annotations

import re

INTENTS = (
    "none",
    "send_email",
    "publish",
    "social_post",
    "spend",
    "sign",
    "delete",
    "other_external",
)

_CEO_DELIVERY = re.compile(
    r"\b(?:send|email|give|return|bring)\s+me\b",
    re.I,
)
_NEGATE_ACT = re.compile(
    r"\bdo not\s+(buy|purchase|spend|pay|send|publish|upload|sign|delete|post|tweet)\b",
    re.I,
)
_ANALYSIS = re.compile(
    r"\b(?:analyze|analyse|evaluat(?:e|ion)|recommend(?:ation)?|whether we should|should we|compare|forecast what)\b",
    re.I,
)
_DRAFT_ONLY = re.compile(
    r"\b(?:draft|prepare|prep)\s+(?:an?|the|this|our)\b",
    re.I,
)
_AND_ACT = re.compile(
    r"\b(?:and|then)\s+(send|publish|upload|buy|purchase|spend|sign|delete|post)\b",
    re.I,
)


def _has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.I) is not None


def action_intent(goal: str) -> str:
    text = goal or ""
    if _NEGATE_ACT.search(text):
        # Explicit prohibition wins unless a different act is also commanded.
        prohibited = {m.group(1).lower() for m in _NEGATE_ACT.finditer(text)}
    else:
        prohibited = set()

    raw = _raw_intent(text)
    if raw == "spend" and ({"buy", "purchase", "spend", "pay"} & prohibited):
        return "none"
    if raw == "send_email" and ("send" in prohibited):
        return "none"
    if raw == "publish" and ({"publish", "upload"} & prohibited):
        return "none"
    if raw == "sign" and ("sign" in prohibited):
        return "none"
    if raw == "delete" and ("delete" in prohibited):
        return "none"
    if raw == "social_post" and ({"post", "tweet"} & prohibited):
        return "none"

    discussion = bool(_ANALYSIS.search(text) or (_DRAFT_ONLY.search(text) and not _AND_ACT.search(text)))
    if discussion and not _AND_ACT.search(text):
        return "none"
    return raw


def _raw_intent(text: str) -> str:
    if _has(text, r"\bdelete\b") and _has(text, r"\b(?:database|account|repo|repository|site|records?|files?)\b"):
        if _has(text, r"\b(?:find|list|candidate)\b") and not _has(text, r"\bdelete (?:the|this|our)\b"):
            pass
        else:
            return "delete"
    if _has(text, r"\bsign\b") and _has(text, r"\b(?:this|the|contract|agreement|terms)\b"):
        return "sign"
    if _has(text, r"\b(?:publish|go live|put (?:this|it|the .{0,20}) live)\b"):
        return "publish"
    if _has(text, r"\bupload and publish\b") or _has(text, r"\bpublish (?:the |this |our )?(?:book|listing|title)\b"):
        return "publish"
    if _has(text, r"\b(?:tweet|post (?:this|it|the .{0,40}) (?:to|on))\b"):
        return "social_post"
    if _has(text, r"\b(?:spend|buy|purchase|pay|transfer)\b") and _has(
        text, r"(?:\$|usd|[0-9]|this|the |funds|money|subscription)"
    ):
        return "spend"
    if _CEO_DELIVERY.search(text) and not _has(text, r"\bto (?:the )?(?!me\b)[a-z]"):
        return "none"
    if _has(text, r"\b(?:send|email)\b") and _has(text, r"\bto\b") and not _CEO_DELIVERY.search(text):
        return "send_email"
    if _has(text, r"\bsend (?:this|it|the) .{0,60}\b(?:now|out)\b"):
        return "send_email"
    return "none"


def approval_reason_for(intent: str) -> str:
    return {
        "send_email": "send external communication",
        "publish": "publish or release publicly",
        "social_post": "post to a public account",
        "spend": "move or commit money",
        "sign": "accept a binding commitment",
        "delete": "destructive external change",
        "other_external": "external action",
        "none": "",
    }.get(intent, "")
