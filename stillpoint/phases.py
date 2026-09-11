from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def stage_key(task_id: str, phase: str, *, agent_id: str = "", input_fingerprint: str = "") -> str:
    raw = f"{task_id}|{phase}|{agent_id}|{input_fingerprint}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    parts = [task_id, phase]
    if agent_id:
        parts.append(agent_id)
    parts.append(digest)
    return ":".join(parts)


def fingerprint(*parts: object) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TaskCheckpoints:
    planning_done: bool = False
    contributors_done: tuple[str, ...] = ()
    primary_done: bool = False
    review_done: bool = False
    revision_done: bool = False
    review_final_done: bool = False
    primary_output: str = ""
    review_output: str = ""
    revision_output: str = ""
    input_fingerprint: str = ""

    def can_reuse_contributor(self, agent_id: str) -> bool:
        return agent_id in self.contributors_done

    def can_reuse_primary(self) -> bool:
        return self.primary_done and bool(self.primary_output)

    def can_reuse_review(self) -> bool:
        return self.review_done and bool(self.review_output)


def checkpoints_from_runs(runs: list[dict], *, expected_fingerprint: str = "") -> TaskCheckpoints:
    contributors: list[str] = []
    planning = primary = review = revision = review_final = False
    primary_output = review_output = revision_output = ""
    stored_fp = ""
    for row in runs:
        phase = row.get("phase") or ""
        agent_id = row.get("agent_id") or ""
        summary = row.get("input_summary") or ""
        if summary.startswith("fp:"):
            stored_fp = summary[3:].split("|", 1)[0][:64]
        if phase in {"planning", "planning_fallback", "resume_planning", "resume_planning_fallback"}:
            planning = True
        elif phase == "contribution" and agent_id and agent_id not in contributors:
            contributors.append(agent_id)
        elif phase in {"primary", "resume_primary"}:
            primary = True
            primary_output = row.get("output") or primary_output
        elif phase == "revision":
            revision = True
            revision_output = row.get("output") or revision_output
        elif phase == "review":
            review = True
            review_output = row.get("output") or review_output
        elif phase == "review_final":
            review_final = True
            review_output = row.get("output") or review_output
    if expected_fingerprint and stored_fp and stored_fp != expected_fingerprint:
        return TaskCheckpoints()
    return TaskCheckpoints(
        planning_done=planning,
        contributors_done=tuple(contributors),
        primary_done=primary,
        review_done=review,
        revision_done=revision,
        review_final_done=review_final,
        primary_output=primary_output,
        review_output=review_output,
        revision_output=revision_output,
        input_fingerprint=expected_fingerprint,
    )
