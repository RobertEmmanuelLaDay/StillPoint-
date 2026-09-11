from __future__ import annotations

from .base import ProviderResult


class MockProvider:
    default_model = "mock"
    def generate(self, *, system: str, prompt: str, model: str, tools=None, **kwargs) -> ProviderResult:
        if "Begin with exactly one judgment word" in prompt:
            return ProviderResult(text="PASS\nMock review: no simulated defect.", model="mock")
        if kwargs.get("json_schema"):
            return ProviderResult(
                text='{"primary":"builder","contributors":[],"capabilities":[],"research_required":false,"review_required":false,"review_reason":"","expected_artifact":"code","external_action_intent":"none","approval_required":false,"approval_reason":"","routing_reason":"Mock structured plan fallback."}',
                model="mock",
            )
        role = "unknown"
        for line in system.splitlines():
            if line.startswith("ROLE:"):
                role = line.removeprefix("ROLE:").strip()
                break
        return ProviderResult(
            text=f"[MOCK OUTPUT — not model-generated work]\nRole: {role}\nRequest received and runtime path executed.",
            model="mock",
        )
