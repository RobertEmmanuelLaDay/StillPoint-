from __future__ import annotations

import json
import re

from .contracts.validate import load_work_plan_schema, validate_work_plan_dict
from .models import WorkPlan
from .policy import CompanyPolicy
from .prompts import agent_system_prompt
from .registry import AgentRegistry
from .router import Router

PLANNER_SYSTEM = (
    "You route one CEO request inside StillPoint. Return only a WorkPlan JSON object. "
    "Exactly one primary. Max three contributors. Never include orchestra or stillpoint as contributors. "
    "stillpoint may be primary only for an explicit audit/review."
)


class Planner:
    def __init__(self, registry: AgentRegistry, policy: CompanyPolicy, provider, default_model: str, smart: bool = True):
        self.registry = registry
        self.policy = policy
        self.provider = provider
        self.default_model = default_model
        self.smart = smart
        self.fallback = Router(registry, policy)
        self.last_provenance: dict = {}

    @staticmethod
    def _extract_json(text: str) -> dict:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            if start < 0:
                raise
            obj, _ = json.JSONDecoder().raw_decode(stripped[start:])
        if not isinstance(obj, dict):
            raise ValueError("planner output is not a JSON object")
        return obj

    def _model_prompt(self, goal: str, baseline: WorkPlan) -> str:
        agent_lines = []
        for agent in self.registry.enabled():
            if agent.id == "stillpoint":
                continue
            agent_lines.append(f"- {agent.id}: {agent.function} — {agent.mission}")
        available = "\n".join(agent_lines)
        return (
            f"AVAILABLE FUNCTIONS:\n{available}\n"
            "- stillpoint: Independent quality / integrity review — may own an explicit audit/review.\n\n"
            f"CEO REQUEST:\n{goal}\n\n"
            "DETERMINISTIC BASELINE (hint only):\n"
            f"primary={baseline.primary}; contributors={baseline.contributors}\n"
        )

    @staticmethod
    def _normalize_legacy_plan(raw: dict) -> dict:
        contributors = raw.get("contributors") or []
        if contributors and isinstance(contributors[0], str):
            raw["contributors"] = [
                {"id": cid, "reason": "legacy contributor slot", "capabilities": [], "before": "primary"}
                for cid in contributors
                if cid not in {"orchestra", "stillpoint"}
            ]
        raw.setdefault("capabilities", [])
        raw.setdefault("research_required", False)
        raw.setdefault("review_required", False)
        raw.setdefault("review_reason", "")
        raw.setdefault("expected_artifact", "other")
        raw.setdefault("external_action_intent", "none")
        raw.setdefault("approval_required", False)
        raw.setdefault("approval_reason", "")
        reason = raw.get("routing_reason") or "model routing"
        if len(reason) < 12:
            reason += " (normalized)"
        raw["routing_reason"] = reason
        return raw

    def _apply_policy(self, plan: WorkPlan, goal: str) -> WorkPlan:
        # One authority assessment is the runtime truth source for this plan overlay.
        bundle = self.policy.authority(goal)
        actions = list(bundle.restricted_intents)
        review_required, review_reason = self.policy.review_requirement(goal)

        if review_required:
            plan.review_required = True
            if review_reason and review_reason not in plan.review_reason:
                plan.review_reason = ", ".join(x for x in [plan.review_reason, review_reason] if x)

        plan.restricted_actions = actions
        plan.external_action_intent = actions[0] if actions else "none"
        if actions:
            plan.approval_required = True
            reasons = []
            from .intent import approval_reason_for
            for action in actions:
                reason = approval_reason_for(action) or action
                if reason not in reasons:
                    reasons.append(reason)
            plan.approval_reason = ", ".join(reasons)
        elif not plan.approval_required:
            plan.approval_reason = ""

        plan.authority_revision = self.policy.authority_revision(goal)

        if plan.primary == "stillpoint":
            plan.review_required = False
            plan.review_reason = ""

        # Preserve stage-scoped capabilities. Research contribution owns search by default;
        # the primary does not inherit it merely because the overall task needs research.
        if not plan.primary_capabilities:
            plan.primary_capabilities = list(plan.capabilities)
        if "research" in plan.contributors and plan.primary != "research":
            plan.primary_capabilities = [c for c in plan.primary_capabilities if c not in {"web_research", "x_research"}]
        plan.primary_tool_requests = [r for r in (plan.tool_requests or []) if r.get("capability") in plan.primary_capabilities]
        for spec in plan.contributor_specs:
            if "tool_requests" not in spec:
                spec["tool_requests"] = [r for r in (plan.tool_requests or []) if r.get("capability") in spec.get("capabilities", [])]
        return plan

    def plan(self, goal: str) -> tuple[WorkPlan, str, bool, str]:
        baseline = self.fallback.plan(goal)
        self.last_provenance = {}
        if not self.smart:
            return self._apply_policy(baseline, goal), "", False, "deterministic"

        orchestra = self.registry.get("orchestra")
        model = orchestra.model or self.default_model
        try:
            result = self.provider.generate(
                system=PLANNER_SYSTEM + "\n" + agent_system_prompt(orchestra),
                prompt=self._model_prompt(goal, baseline),
                model=model,
                tools=[],
                effort="low",
                json_schema=load_work_plan_schema(),
                json_schema_name="work_plan",
            )
            self.last_provenance = {
                "provider_response_id": getattr(result, "provider_response_id", None) or "",
                "usage": getattr(result, "usage", None) or {},
                "citations": list(getattr(result, "citations", None) or []),
                "model": getattr(result, "model", model) or model,
                "status": getattr(result, "status", "completed"),
            }
            raw = self._normalize_legacy_plan(self._extract_json(result.text))
            contract = validate_work_plan_dict(raw)
            contributor_specs = contract.to_runtime_dict()["contributor_specs"]
            plan = WorkPlan(
                primary=contract.primary,
                contributors=contract.contributor_ids(),
                review_required=contract.review_required,
                review_reason=contract.review_reason,
                approval_required=contract.approval_required,
                approval_reason=contract.approval_reason,
                routing_reason=contract.routing_reason,
                capabilities=list(contract.capabilities),
                primary_capabilities=list(contract.capabilities),
                research_required=contract.research_required,
                expected_artifact=contract.expected_artifact,
                external_action_intent=contract.external_action_intent,
                contributor_specs=contributor_specs,
            )
            plan.tool_requests = list(getattr(baseline, "tool_requests", []) or [])
            plan.primary_tool_requests = [
                r for r in plan.tool_requests if r.get("capability") in plan.primary_capabilities
            ]
            for spec in plan.contributor_specs:
                spec["tool_requests"] = [
                    r for r in plan.tool_requests if r.get("capability") in spec.get("capabilities", [])
                ]

            if contract.research_required and "research" not in plan.contributors and plan.primary != "research":
                if len(plan.contributors) < 3:
                    plan.contributors.append("research")
                    plan.contributor_specs.append({
                        "id": "research",
                        "reason": "research required by work plan",
                        "capabilities": [c for c in plan.capabilities if c in {"web_research", "x_research"}],
                        "before": "primary",
                    })
            plan = self._apply_policy(plan, goal)
            return plan, result.text, True, result.model
        except Exception as exc:
            baseline.routing_reason = f"deterministic fallback ({type(exc).__name__})"
            return self._apply_policy(baseline, goal), str(exc), False, "deterministic"
