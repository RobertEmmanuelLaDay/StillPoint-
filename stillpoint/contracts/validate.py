from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CONTRIBUTOR_IDS, WorkPlan

SCHEMA_PATH = Path(__file__).with_name("work_plan.schema.json")

BOOLS = {"research_required", "review_required", "approval_required"}


def load_work_plan_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _expect_type(value: Any, typ, field: str) -> None:
    if not isinstance(value, typ):
        raise ValueError(f"{field} must be {typ.__name__}, got {type(value).__name__}")


def validate_work_plan_dict(raw: Any) -> WorkPlan:
    if not isinstance(raw, dict):
        raise ValueError("work plan must be an object")
    schema = load_work_plan_schema()
    props = schema["properties"]
    missing = [k for k in schema["required"] if k not in raw]
    if missing:
        raise ValueError(f"work plan missing fields: {missing}")
    extra = [k for k in raw if k not in props]
    if extra:
        raise ValueError(f"work plan unknown fields: {extra}")

    primary = raw["primary"]
    _expect_type(primary, str, "primary")
    if primary not in props["primary"]["enum"]:
        raise ValueError(f"invalid primary: {primary}")

    contributors = raw["contributors"]
    _expect_type(contributors, list, "contributors")
    if len(contributors) > 3:
        raise ValueError("max 3 contributors")
    seen: list[str] = []
    for i, item in enumerate(contributors):
        prefix = f"contributors[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} must be an object")
        extra_c = [k for k in item if k not in {"id", "reason", "capabilities", "before"}]
        if extra_c:
            raise ValueError(f"{prefix} unknown fields: {extra_c}")
        for key in ("id", "reason", "capabilities", "before"):
            if key not in item:
                raise ValueError(f"{prefix} missing {key}")
        cid = item["id"]
        _expect_type(cid, str, f"{prefix}.id")
        if cid not in CONTRIBUTOR_IDS:
            raise ValueError(f"{prefix}.id invalid: {cid}")
        if cid == primary:
            raise ValueError("primary cannot also be a contributor")
        if cid in seen:
            raise ValueError(f"duplicate contributor: {cid}")
        seen.append(cid)
        _expect_type(item["reason"], str, f"{prefix}.reason")
        if not (8 <= len(item["reason"]) <= 240):
            raise ValueError(f"{prefix}.reason length")
        caps = item["capabilities"]
        _expect_type(caps, list, f"{prefix}.capabilities")
        allowed_caps = props["capabilities"]["items"]["enum"]
        for cap in caps:
            if cap not in allowed_caps:
                raise ValueError(f"{prefix} bad capability: {cap}")
        if item["before"] not in {"primary", "next_contributor"}:
            raise ValueError(f"{prefix}.before invalid")

    caps = raw["capabilities"]
    _expect_type(caps, list, "capabilities")
    for cap in caps:
        if cap not in props["capabilities"]["items"]["enum"]:
            raise ValueError(f"bad capability: {cap}")

    for key in BOOLS:
        if type(raw[key]) is not bool:
            raise ValueError(f"{key} must be a boolean, not {type(raw[key]).__name__}")

    _expect_type(raw["review_reason"], str, "review_reason")
    _expect_type(raw["approval_reason"], str, "approval_reason")
    _expect_type(raw["routing_reason"], str, "routing_reason")
    if not (12 <= len(raw["routing_reason"]) <= 240):
        raise ValueError("routing_reason length")
    if raw["expected_artifact"] not in props["expected_artifact"]["enum"]:
        raise ValueError(f"invalid expected_artifact: {raw['expected_artifact']}")
    if raw["external_action_intent"] not in props["external_action_intent"]["enum"]:
        raise ValueError(f"invalid external_action_intent: {raw['external_action_intent']}")

    return WorkPlan.from_dict(raw)
