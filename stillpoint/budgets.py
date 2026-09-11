from __future__ import annotations

from dataclasses import dataclass, asdict


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetLimits:
    max_model_calls: int | None = None
    max_tool_calls: int | None = None
    max_total_tokens: int | None = None
    max_elapsed_seconds: float | None = None
    max_cost_usd: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

class BudgetedProviderProxy:
    def __init__(self, provider, *, task_id_getter, before_call, after_call):
        self._provider = provider
        self._task_id_getter = task_id_getter
        self._before_call = before_call
        self._after_call = after_call

    def __getattr__(self, name):
        return getattr(self._provider, name)

    def generate(self, **kwargs):
        task_id = kwargs.get("task_id") or self._task_id_getter()
        tools = kwargs.get("tools") or []
        tool_count = len(tools)
        if task_id:
            self._before_call(task_id, tool_count=tool_count)
        result = None
        try:
            result = self._provider.generate(**kwargs)
            return result
        finally:
            if task_id:
                usage = getattr(result, "usage", None) if result is not None else None
                self._after_call(task_id, usage=usage or {}, tool_count=tool_count)
