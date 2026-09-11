from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .attachments import render_attachments, select_attachment_context
from .capabilities import capabilities_for_call
from .db import CompanyDB
from .file_loader import read_attachment
from .models import TaskOutcome, TaskStatus, WorkPlan
from .phases import checkpoints_from_runs, fingerprint, stage_key
from .planner import Planner
from .policy import CompanyPolicy
from .prompts import agent_system_prompt, review_prompt, task_prompt
from .registry import AgentRegistry


class CompanyRuntime:
    def __init__(self, *, root: Path, db: CompanyDB, registry: AgentRegistry, provider, default_model: str, smart_routing: bool = True):
        self.root = root
        self.db = db
        self.registry = registry
        self.provider = provider
        self.default_model = default_model
        self.policy = CompanyPolicy()
        self.planner = Planner(registry, self.policy, provider, default_model, smart=smart_routing)

    def _memory_text(self, project: str | None) -> str:
        scopes = ["company"]
        if project:
            scopes.append(f"project:{project}")
        rows = self.db.get_memory(scopes)
        return "\n".join(f"[{row['scope']}] {row['key']}: {row['value']}" for row in rows)

    def _fingerprint(self, goal: str, project: str | None, attachments: list[dict[str, str]]) -> str:
        return fingerprint(goal, project, [(a["name"], a["sha256"]) for a in attachments])

    def _call_agent(
        self,
        task_id: str,
        agent_id: str,
        phase: str,
        goal: str,
        project: str | None,
        contributions: list[tuple[str, str]],
        attachments: list[dict[str, str]],
        plan: WorkPlan,
        correction: str = "",
        input_fp: str = "",
    ) -> str:
        agent = self.registry.get(agent_id)
        model = agent.model or self.default_model
        selected = select_attachment_context(attachments, goal)
        prompt = task_prompt(
            goal=goal,
            project=project,
            memory_text=self._memory_text(project),
            contributions=contributions,
            attachments=selected,
            correction=correction,
        )
        tools = capabilities_for_call(
            agent_id=agent_id,
            plan_capabilities=list(plan.capabilities),
            review_reason=plan.review_reason,
        )
        result = self.provider.generate(
            system=agent_system_prompt(agent),
            prompt=prompt,
            model=model,
            tools=tools,
            task_id=task_id,
            phase=phase,
            effort="high" if agent_id in {"author", "stillpoint", "builder"} else "medium",
        )
        run_id = self.db.add_run(
            task_id,
            agent_id,
            phase,
            result.text,
            model=result.model,
            input_summary=("fp:" + input_fp) if input_fp else goal[:500],
            citations=result.citations,
            provider_response_id=result.provider_response_id or "",
            usage=result.usage,
            stage_key=stage_key(task_id, phase, agent_id=agent_id, input_fingerprint=input_fp),
        )
        if phase in {"primary", "resume_primary", "revision"}:
            sha = hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            self.db.add_artifact(
                task_id=task_id,
                project=project,
                kind=plan.expected_artifact or "other",
                name=f"{phase}.txt",
                sha256=sha,
                produced_by_run_id=run_id,
                phase=phase,
            )
        if result.citations:
            source_block = "\n".join(f"- {url}" for url in result.citations)
            return f"{result.text}\n\nPROVIDER SOURCE URLS:\n{source_block}"
        return result.text

    def _review(self, task_id: str, goal: str, artifact: str, reason: str, plan: WorkPlan, input_fp: str, phase: str = "review") -> str:
        agent = self.registry.get("stillpoint")
        model = agent.model or self.default_model
        tools = capabilities_for_call(agent_id="stillpoint", plan_capabilities=[], review_reason=reason)
        result = self.provider.generate(
            system=agent_system_prompt(agent),
            prompt=review_prompt(goal, artifact, reason),
            model=model,
            tools=tools,
            task_id=task_id,
            phase=phase,
            effort="high",
        )
        self.db.add_run(
            task_id,
            "stillpoint",
            phase,
            result.text,
            model=result.model,
            input_summary=("fp:" + input_fp) if input_fp else goal[:500],
            citations=result.citations,
            provider_response_id=result.provider_response_id or "",
            usage=result.usage,
            stage_key=stage_key(task_id, phase, agent_id="stillpoint", input_fingerprint=input_fp),
        )
        return result.text

    @staticmethod
    def _judgment(review: str) -> str:
        first = review.strip().splitlines()[0].strip().upper() if review.strip() else "CORRECT"
        if first.startswith("PASS"):
            return "PASS"
        if first.startswith("HALT"):
            return "HALT"
        return "CORRECT"

    @staticmethod
    def _plan_from_json(plan_json: str) -> WorkPlan:
        return WorkPlan.from_dict(json.loads(plan_json))

    def _load_saved_attachments(self, task_id: str) -> list[dict[str, str]]:
        attachments: list[dict[str, str]] = []
        for row in self.db.list_task_files(task_id):
            item = read_attachment(row["path"])
            if item["sha256"] != row["sha256"]:
                raise RuntimeError(
                    f"attachment changed since task creation: {row['name']}. "
                    "Start a new task if you intend to use the changed file."
                )
            attachments.append(item)
        return attachments

    def _existing_contributions(self, task_id: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for row in self.db.list_runs(task_id):
            if row["phase"] == "contribution":
                found[row["agent_id"]] = row["output"]
        return found

    def _finish(self, task_id: str, plan: WorkPlan, primary_output: str, review_text: str) -> TaskOutcome:
        if plan.approval_required:
            self.db.update_task(
                task_id,
                status="waiting_approval",
                final_output=primary_output,
                review_output=review_text,
                approval_reason=plan.approval_reason,
            )
            return TaskOutcome(task_id, TaskStatus.WAITING_APPROVAL, plan, primary_output, review_text, plan.approval_reason)
        self.db.update_task(
            task_id,
            status="completed",
            final_output=primary_output,
            review_output=review_text,
            error=None,
        )
        return TaskOutcome(task_id, TaskStatus.COMPLETED, plan, primary_output, review_text)

    def _execute(
        self,
        task_id: str,
        goal: str,
        project: str | None,
        plan: WorkPlan,
        attachments: list[dict[str, str]],
        *,
        reuse_contributions: bool = False,
        resume_note: str = "",
    ) -> TaskOutcome:
        input_fp = self._fingerprint(goal, project, attachments)
        self.db.update_task(task_id, input_fingerprint=input_fp)
        ck = checkpoints_from_runs(self.db.list_runs(task_id), expected_fingerprint=input_fp) if reuse_contributions else None

        contributions: list[tuple[str, str]] = []
        existing = self._existing_contributions(task_id) if reuse_contributions else {}
        for contributor_id in plan.contributors:
            if ck and ck.can_reuse_contributor(contributor_id) and contributor_id in existing:
                output = existing[contributor_id]
            else:
                output = self._call_agent(
                    task_id, contributor_id, "contribution", goal, project, [], attachments, plan, input_fp=input_fp
                )
            contributions.append((self.registry.get(contributor_id).name, output))

        effective_goal = goal
        if resume_note:
            effective_goal += f"\n\nCEO RESUME INSTRUCTION:\n{resume_note}"

        if ck and ck.primary_done and ck.primary_output and not resume_note:
            primary_output = ck.primary_output
        else:
            primary_output = self._call_agent(
                task_id,
                plan.primary,
                "resume_primary" if reuse_contributions else "primary",
                effective_goal,
                project,
                contributions,
                attachments,
                plan,
                input_fp=input_fp,
            )

        review_text = ""
        if plan.review_required and plan.primary != "stillpoint":
            if ck and ck.review_done and ck.review_output and not ck.revision_done:
                review_text = ck.review_output
                judgment = self._judgment(review_text)
            else:
                review_text = self._review(task_id, effective_goal, primary_output, plan.review_reason, plan, input_fp)
                judgment = self._judgment(review_text)
            if judgment == "HALT":
                self.db.update_task(task_id, status="blocked", final_output=primary_output, review_output=review_text)
                return TaskOutcome(task_id, TaskStatus.BLOCKED, plan, primary_output, review_text)
            if judgment == "CORRECT":
                if ck and ck.revision_done and ck.revision_output:
                    primary_output = ck.revision_output
                else:
                    primary_output = self._call_agent(
                        task_id, plan.primary, "revision", effective_goal, project, contributions, attachments, plan,
                        correction=review_text, input_fp=input_fp,
                    )
                if ck and ck.review_final_done and ck.review_output:
                    review_text = ck.review_output
                else:
                    review_text = self._review(
                        task_id, effective_goal, primary_output, "post-correction final review", plan, input_fp,
                        phase="review_final",
                    )
                if self._judgment(review_text) != "PASS":
                    self.db.update_task(task_id, status="blocked", final_output=primary_output, review_output=review_text)
                    return TaskOutcome(task_id, TaskStatus.BLOCKED, plan, primary_output, review_text)

        return self._finish(task_id, plan, primary_output, review_text)

    def submit(self, goal: str, *, project: str | None = None, files: list[str] | None = None) -> TaskOutcome:
        task_id = self.db.create_task(goal, project)
        try:
            plan, planning_output, model_planned, planning_model = self.planner.plan(goal)
            self.db.set_plan(task_id, plan.to_dict())
            if planning_output:
                self.db.add_run(
                    task_id,
                    "orchestra",
                    "planning" if model_planned else "planning_fallback",
                    planning_output,
                    model=planning_model,
                    input_summary=goal[:500],
                )
            attachments = [read_attachment(path) for path in (files or [])]
            for item in attachments:
                self.db.add_task_file(task_id, item["path"], item["name"], item["sha256"])
            return self._execute(task_id, goal, project, plan, attachments)
        except Exception as exc:
            self.db.update_task(task_id, status="failed", error=str(exc))
            raise

    def resume(self, task_id: str, note: str = "") -> TaskOutcome:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        if task["status"] not in {"new", "running", "failed", "blocked"}:
            raise RuntimeError(
                f"task cannot be resumed from status={task['status']}; use approve/reject for waiting approvals"
            )
        if not task.get("plan_json"):
            plan, planning_output, model_planned, planning_model = self.planner.plan(task["goal"])
            self.db.set_plan(task_id, plan.to_dict())
            if planning_output:
                self.db.add_run(
                    task_id, "orchestra",
                    "resume_planning" if model_planned else "resume_planning_fallback",
                    planning_output, model=planning_model, input_summary=task["goal"][:500],
                )
        else:
            plan = self._plan_from_json(task["plan_json"])
        attachments = self._load_saved_attachments(task_id)
        self.db.update_task(task_id, status="running", error=None)
        try:
            return self._execute(
                task_id, task["goal"], task.get("project"), plan, attachments,
                reuse_contributions=True, resume_note=note,
            )
        except Exception as exc:
            self.db.update_task(task_id, status="failed", error=str(exc))
            raise

    def approve(self, task_id: str, note: str = "") -> dict:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        if task["status"] != "waiting_approval":
            raise RuntimeError(f"task is not waiting for approval (status={task['status']})")
        self.db.add_approval(task_id, "approved", note)
        self.db.update_task(task_id, status="ready_for_action", approval_reason="")
        return self.db.get_task(task_id) or {}

    def reject(self, task_id: str, note: str = "") -> dict:
        task = self.db.get_task(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self.db.add_approval(task_id, "rejected", note)
        self.db.update_task(task_id, status="rejected")
        return self.db.get_task(task_id) or {}
