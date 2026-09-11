from __future__ import annotations
from datetime import datetime, timezone
from typing import Protocol
from ..contracts.models import ActionEvidence, ActionRequest, ActionResult

def _now():return datetime.now(timezone.utc).isoformat()
class NotAuthorized(RuntimeError):pass
class ActionAdapter(Protocol):
    name:str; action_types:tuple[str,...]
    def can_execute(self,request:ActionRequest)->bool:...
    def execute(self,request:ActionRequest)->ActionResult:...
class NullActionAdapter:
    name="null"; action_types=()
    def can_execute(self,request):return False
    def execute(self,request):
        if request.approval_required and not request.permitted(_now()):raise NotAuthorized("missing or expired approval")
        return ActionResult(action_id=request.action_id,status="failed",error="no action adapter registered",adapter=self.name)
def evidence_satisfies(request,evidence):
    if not request.success_criteria:return False
    satisfied={e.satisfies.strip().lower() for e in evidence if e.satisfies.strip()}
    types={e.type.strip().lower() for e in evidence if e.type.strip()}
    for criterion in request.success_criteria:
        token=criterion.strip().lower()
        if token not in satisfied and token not in types:return False
    return True
def runtime_complete(request,result,*,now_iso=None):
    now=now_iso or _now()
    if request.approval_required and not request.permitted(now):return "waiting_approval"
    if not result.adapter or result.adapter=="null" or result.adapter.startswith("dry_run"):return "ready_for_action"
    if result.status=="succeeded" and evidence_satisfies(request,result.evidence):return "completed"
    if result.status=="succeeded":return "failed"
    return result.status
