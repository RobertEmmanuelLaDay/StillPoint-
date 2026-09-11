from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from ..contracts.models import ActionEvidence, ActionRequest, ActionResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotAuthorized(RuntimeError):
    pass


class ActionAdapter(Protocol):
    name: str
    action_types: tuple[str, ...]

    def can_execute(self, request: ActionRequest) -> bool: ...
    def execute(self, request: ActionRequest) -> ActionResult: ...


class NullActionAdapter:
    name = "null"
    action_types: tuple[str, ...] = ()

    def can_execute(self, request: ActionRequest) -> bool:
        return False

    def execute(self, request: ActionRequest) -> ActionResult:
        if request.approval_required and not request.permitted(_now()):
            raise NotAuthorized("missing or expired approval")
        return ActionResult(
            action_id=request.action_id,
            status="failed",
            error="no action adapter registered",
            adapter=self.name,
        )


def evidence_satisfies(request: ActionRequest, evidence: list[ActionEvidence]) -> bool:
    if not request.success_criteria:
        return False
    notes = {(e.satisfies or e.note or "").lower() for e in evidence}
    types = {e.type.lower() for e in evidence}
    for criterion in request.success_criteria:
        token = criterion.lower()
        if not any(token in n or token in types for n in notes | types):
            return False
    return True


def runtime_complete(request: ActionRequest, result: ActionResult, *, now_iso: str | None = None) -> str:
    now = now_iso or _now()
    if request.approval_required and not request.permitted(now):
        return "waiting_approval"
    if not result.adapter or result.adapter == "null":
        return "ready_for_action"
    if result.status == "succeeded" and evidence_satisfies(request, result.evidence):
        return "completed"
    if result.status == "succeeded":
        return "failed"
    return result.status
