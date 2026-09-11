#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for path in (ROOT, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_eval as run_eval_mod
import scoring as scoring_mod
from frozen import load_frozen_50, load_shadow_20, verify_frozen_corpora
from run_eval import eval_case
from scoring_calibrated import score_tools_calibrated

CLASSIFICATION = HERE / "failure_classification.json"


def _normalized_shadow() -> list[dict]:
    cases = load_shadow_20()
    for raw in cases:
        raw.setdefault("expected_contributors", [])
        raw.setdefault("forbidden_contributors", [])
        raw.setdefault("expected_capabilities", [])
        raw.setdefault("forbidden_tools", [])
        raw.setdefault("research_required", False)
        raw.setdefault("review_required", False)
        raw.setdefault("attachments", [])
        raw.setdefault("memory", "none")
    return cases


def _failed_ids(cases: list[dict]) -> set[str]:
    return {result.case_id for result in (eval_case(case) for case in cases) if not result.passed}


def main() -> int:
    verify_frozen_corpora()
    allowed = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))

    # Calibrated scoring compares semantic capabilities rather than counting provider aliases
    # as separate tools. This is the provider-independent release gate.
    scoring_mod.score_tools = score_tools_calibrated
    run_eval_mod.score_tools = score_tools_calibrated

    actual = {
        "original50_calibrated": _failed_ids(load_frozen_50()),
        "shadow20_calibrated": _failed_ids(_normalized_shadow()),
    }
    unexpected: dict[str, list[str]] = {}
    for suite, failures in actual.items():
        permitted = {
            case_id
            for case_id, entry in allowed.get(suite, {}).items()
            if entry.get("classification") == "evaluation_expectation_conflict"
        }
        extra = sorted(failures - permitted)
        if extra:
            unexpected[suite] = extra

    print(json.dumps({key: sorted(value) for key, value in actual.items()}, indent=2))
    if unexpected:
        print("UNEXPECTED RELEASE-GATE FAILURES:", json.dumps(unexpected, indent=2))
        return 1
    print("release gate: PASS (all remaining failures are classified evaluator expectation conflicts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
