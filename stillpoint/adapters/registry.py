from __future__ import annotations

from ..contracts.models import ActionRequest, ActionResult
from .base import NullActionAdapter


class ActionAdapterRegistry:
    def __init__(self, adapters=None):
        self._adapters=[]
        for adapter in adapters or []: self.register(adapter)
    def register(self, adapter):
        if not getattr(adapter,"name",""): raise ValueError("adapter must have a name")
        if any(a.name==adapter.name for a in self._adapters): raise ValueError(f"duplicate adapter: {adapter.name}")
        self._adapters.append(adapter); return adapter
    def resolve(self, request: ActionRequest):
        for adapter in self._adapters:
            if request.action_type in getattr(adapter,"action_types",()) and adapter.can_execute(request): return adapter
        return NullActionAdapter()
    def execute(self, request: ActionRequest) -> ActionResult:
        return self.resolve(request).execute(request)


class DryRunActionAdapter:
    name="dry_run"
    action_types=("send_email","publish","social_post","spend","sign","delete","other_external")
    def can_execute(self,request): return True
    def execute(self,request):
        # This proves dispatch wiring only. A dry run is deliberately not external evidence.
        return ActionResult(action_id=request.action_id,status="succeeded",evidence=[],adapter=self.name,external_id="dry-run")
