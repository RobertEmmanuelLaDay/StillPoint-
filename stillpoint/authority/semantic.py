from __future__ import annotations

import json

from .schema import AUTHORITY_SCHEMA, AuthorityAssessment, FAMILIES, MODES, TARGETS

SYSTEM = (
    "Classify a CEO request for external-action authority only. "
    "Return JSON. Do not invent facts. Tools are forbidden."
)


def parse_semantic(raw: object) -> AuthorityAssessment | None:
    if not isinstance(raw, dict):
        return None
    extra = [k for k in raw if k not in AUTHORITY_SCHEMA["properties"]]
    if extra:
        return None
    for key in AUTHORITY_SCHEMA["required"]:
        if key not in raw:
            return None
    family = raw.get("action_family")
    mode = raw.get("mode")
    target = raw.get("target")
    if family not in FAMILIES or mode not in MODES or target not in TARGETS:
        return None
    if type(raw.get("reason")) is not str:
        return None
    conf = raw.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        return None
    conf_f = float(conf)
    if conf_f < 0.0 or conf_f > 1.0:
        return None
    return AuthorityAssessment(family, mode, target, conf_f, raw["reason"], "semantic")


class SemanticAuthority:
    def __init__(self, provider=None, model: str = "grok-4.6"):
        self.provider = provider
        self.model = model

    def assess(self, goal: str) -> AuthorityAssessment | None:
        if self.provider is None:
            return None
        try:
            result = self.provider.generate(
                system=SYSTEM,
                prompt=f"CEO REQUEST:\n{goal}",
                model=self.model,
                tools=[],
                effort="low",
                json_schema=AUTHORITY_SCHEMA,
                json_schema_name="authority_assessment",
            )
            raw = json.loads(result.text)
        except Exception:
            return None
        return parse_semantic(raw)
