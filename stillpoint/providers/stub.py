from __future__ import annotations

import json
from .base import ProviderResult


class NeutralStubProvider:
    """Provider-neutral deterministic stub used to prove core code does not require xAI."""
    default_model = "neutral-stub"

    def generate(self, *, system: str, prompt: str, model: str, tools=None, **kwargs) -> ProviderResult:
        if kwargs.get("json_schema_name") == "authority_assessment":
            return ProviderResult(
                text=json.dumps({
                    "action_family": "none",
                    "mode": "unknown",
                    "target": "unknown",
                    "confidence": 0.5,
                    "reason": "neutral stub",
                }),
                model=model or self.default_model,
                provider_response_id="neutral-authority",
                usage={"total_tokens": 1},
            )
        if kwargs.get("json_schema"):
            return ProviderResult(
                text=json.dumps({
                    "primary": "orchestra", "contributors": [], "capabilities": [],
                    "research_required": False, "review_required": False, "review_reason": "",
                    "expected_artifact": "plan", "external_action_intent": "none",
                    "approval_required": False, "approval_reason": "",
                    "routing_reason": "Neutral provider structured routing.",
                }),
                model=model or self.default_model,
                provider_response_id="neutral-plan",
                usage={"total_tokens": 2},
            )
        return ProviderResult(
            text="neutral provider output",
            model=model or self.default_model,
            provider_response_id="neutral-run",
            usage={"total_tokens": 3},
        )
