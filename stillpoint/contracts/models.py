from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

AGENT_IDS = ("orchestra", "author", "press", "signal", "ledger", "research", "builder", "stillpoint")
CONTRIBUTOR_IDS = ("author", "press", "signal", "ledger", "research", "builder")
CAPABILITIES = ("web_research", "x_research", "code_execution", "structured_output")


@dataclass
class ContributorSpec:
    id: str
    reason: str
    capabilities: list[str] = field(default_factory=list)
    before: str = "primary"


@dataclass
class WorkPlanContract:
    primary: str
    contributors: list[ContributorSpec]
    capabilities: list[str]
    research_required: bool
    review_required: bool
    review_reason: str
    expected_artifact: str
    external_action_intent: str
    approval_required: bool
    approval_reason: str
    routing_reason: str

    def contributor_ids(self) -> list[str]:
        return [c.id for c in self.contributors]

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary,
            "contributors": self.contributor_ids(),
            "review_required": self.review_required,
            "review_reason": self.review_reason,
            "approval_required": self.approval_required,
            "approval_reason": self.approval_reason,
            "routing_reason": self.routing_reason,
            "capabilities": list(self.capabilities),
            "research_required": self.research_required,
            "expected_artifact": self.expected_artifact,
            "external_action_intent": self.external_action_intent,
            "contributor_specs": [asdict(c) for c in self.contributors],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkPlanContract":
        return cls(
            primary=raw["primary"],
            contributors=[
                ContributorSpec(
                    id=i["id"],
                    reason=i["reason"],
                    capabilities=list(i.get("capabilities") or []),
                    before=i.get("before") or "primary",
                )
                for i in raw["contributors"]
            ],
            capabilities=list(raw["capabilities"]),
            research_required=raw["research_required"],
            review_required=raw["review_required"],
            review_reason=raw["review_reason"],
            expected_artifact=raw["expected_artifact"],
            external_action_intent=raw["external_action_intent"],
            approval_required=raw["approval_required"],
            approval_reason=raw["approval_reason"],
            routing_reason=raw["routing_reason"],
        )


# alias used by validate.py
WorkPlan = WorkPlanContract


@dataclass
class ArtifactRef:
    name: str
    sha256: str
    kind: str = "other"
    media_type: str = "text/plain"


@dataclass
class ActionRequest:
    action_id: str
    task_id: str
    action_type: str
    target: str
    scope: list[str]
    artifact_refs: list[ArtifactRef]
    approval_required: bool
    approval_id: str | None
    expires_at: str
    issued_at: str
    idempotency_key: str
    success_criteria: list[str]
    click_irreversible: bool = False

    def permitted(self, now_iso: str) -> bool:
        if not self.approval_required:
            return True
        if not self.approval_id:
            return False
        return now_iso <= self.expires_at


@dataclass
class ActionEvidence:
    type: str
    sha256: str
    note: str = ""
    satisfies: str = ""


@dataclass
class ActionResult:
    action_id: str
    status: str
    evidence: list[ActionEvidence] = field(default_factory=list)
    external_id: str | None = None
    error: str | None = None
    adapter: str = ""
