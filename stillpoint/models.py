from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    NEW = "new"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    READY_FOR_ACTION = "ready_for_action"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    function: str
    mission: str
    owns: list[str]
    does_not_own: list[str]
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    enabled: bool = True


@dataclass
class WorkPlan:
    primary: str
    contributors: list[str] = field(default_factory=list)
    review_required: bool = False
    review_reason: str = ""
    approval_required: bool = False
    approval_reason: str = ""
    routing_reason: str = ""
    capabilities: list[str] = field(default_factory=list)
    research_required: bool = False
    expected_artifact: str = "other"
    external_action_intent: str = "none"
    contributor_specs: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkPlan":
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in allowed})


@dataclass
class AgentRun:
    agent_id: str
    phase: str
    output: str
    model: str = ""
    citations: list[str] = field(default_factory=list)


@dataclass
class TaskOutcome:
    task_id: str
    status: TaskStatus
    plan: WorkPlan
    final_output: str
    review: str = ""
    approval_reason: str = ""
