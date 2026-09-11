from __future__ import annotations

from dataclasses import asdict, dataclass, field

FAMILIES = (
    "none",
    "communicate",
    "publish",
    "social",
    "spend",
    "sign",
    "delete",
    "other_external",
)
MODES = (
    "execute",
    "analyze",
    "recommend",
    "draft",
    "prepare",
    "compare",
    "find",
    "return_to_ceo",
    "prohibit",
    "unknown",
)
TARGETS = (
    "ceo",
    "external_person",
    "public",
    "financial",
    "external_system",
    "unknown",
)
FAMILY_TO_INTENT = {
    "none": "none",
    "communicate": "send_email",
    "publish": "publish",
    "social": "social_post",
    "spend": "spend",
    "sign": "sign",
    "delete": "delete",
    "other_external": "other_external",
}
INTENT_TO_FAMILY = {v: k for k, v in FAMILY_TO_INTENT.items()}
RESTRICTED_INTENTS = ("send_email", "publish", "social_post", "spend", "sign", "delete", "other_external")
DISCUSSION_MODES = {
    "analyze", "recommend", "draft", "prepare", "compare", "find", "return_to_ceo", "prohibit",
}

AUTHORITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action_family", "mode", "target", "confidence", "reason"],
    "properties": {
        "action_family": {"type": "string", "enum": list(FAMILIES)},
        "mode": {"type": "string", "enum": list(MODES)},
        "target": {"type": "string", "enum": list(TARGETS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
}


def intent_of(family: str, mode: str) -> str:
    if mode in DISCUSSION_MODES:
        return "none"
    if family == "none":
        return "none"
    if mode in {"execute", "unknown"}:
        return FAMILY_TO_INTENT.get(family, "other_external")
    return "none"


@dataclass
class AuthorityAssessment:
    action_family: str = "none"
    mode: str = "unknown"
    target: str = "unknown"
    confidence: float = 0.0
    reason: str = ""
    source: str = "deterministic"
    clause: str = ""

    @property
    def intent(self) -> str:
        return intent_of(self.action_family, self.mode)

    @property
    def approval_required(self) -> bool:
        return self.intent != "none"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["intent"] = self.intent
        data["approval_required"] = self.approval_required
        return data


@dataclass
class AuthorityBundle:
    assessments: list[AuthorityAssessment] = field(default_factory=list)

    @property
    def restricted(self) -> list[AuthorityAssessment]:
        return [a for a in self.assessments if a.intent != "none"]

    @property
    def restricted_intents(self) -> list[str]:
        out: list[str] = []
        for item in self.restricted:
            if item.intent not in out:
                out.append(item.intent)
        return out

    @property
    def primary_intent(self) -> str:
        intents = self.restricted_intents
        if not intents:
            return "none"
        if len(intents) == 1:
            return intents[0]
        return intents[0]

    @property
    def approval_required(self) -> bool:
        return bool(self.restricted_intents)

    @property
    def reason(self) -> str:
        if not self.assessments:
            return ""
        if not self.restricted:
            return self.assessments[0].reason
        return "; ".join(f"{a.intent}:{a.reason}" for a in self.restricted)

    def to_compat(self) -> AuthorityAssessment:
        if self.restricted:
            return self.restricted[0]
        return self.assessments[0] if self.assessments else AuthorityAssessment()
