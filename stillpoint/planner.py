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
            reason = reason + " (normalized)"
        raw["routing_reason"] = reason
        return raw

    def _apply_policy(self, plan: WorkPlan, goal: str) -> WorkPlan:
        review_required, review_reason = self.policy.review_requirement(goal)
        approval_required, approval_reason = self.policy.approval_requirement(goal)
        if review_required:
            plan.review_required = True
            if review_reason and review_reason not in plan.review_reason:
                plan.review_reason = ", ".join(x for x in [plan.review_reason, review_reason] if x)
        if approval_required:
            plan.approval_required = True
            if approval_reason:
                plan.approval_reason = approval_reason
        if plan.primary == "stillpoint":
            plan.review_required = False
            plan.review_reason = ""
        intent = self.policy.action_intent(goal)
        if intent != "none" or not approval_required:
            plan.external_action_intent = intent
        return plan

    def plan(self, goal: str) -> tuple[WorkPlan, str, bool, str]:
        baseline = self.fallback.plan(goal)
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
            raw = self._normalize_legacy_plan(self._extract_json(result.text))
            contract = validate_work_plan_dict(raw)
            plan = WorkPlan(
                primary=contract.primary,
                contributors=contract.contributor_ids(),
                review_required=contract.review_required,
                review_reason=contract.review_reason,
                approval_required=contract.approval_required,
                approval_reason=contract.approval_reason,
                routing_reason=contract.routing_reason,
                capabilities=list(contract.capabilities),
                research_required=contract.research_required,
                expected_artifact=contract.expected_artifact,
                external_action_intent=contract.external_action_intent,
                contributor_specs=contract.to_runtime_dict()["contributor_specs"],
            )
            if contract.research_required and "research" not in plan.contributors and plan.primary != "research":
                if len(plan.contributors) < 3:
                    plan.contributors.append("research")
            plan = self._apply_policy(plan, goal)
            return plan, result.text, True, result.model
        except Exception as exc:
            baseline.routing_reason = f"deterministic fallback ({type(exc).__name__})"
            return self._apply_policy(baseline, goal), str(exc), False, "deterministic"
