#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for p in (ROOT, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import scoring as scoring_mod
import run_eval as run_eval_mod
from frozen import load_frozen_50, load_shadow_20, verify_frozen_corpora
from run_eval import eval_case, render_md
from scoring import aggregate
from scoring_calibrated import score_tools_calibrated

OUT = HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)
_ORIGINAL_SCORE_TOOLS = scoring_mod.score_tools


def normalize_shadow(cases):
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


def run_cases(cases, label: str, calibrated: bool):
    impl = score_tools_calibrated if calibrated else _ORIGINAL_SCORE_TOOLS
    scoring_mod.score_tools = impl
    run_eval_mod.score_tools = impl
    results = [eval_case(c) for c in cases]
    agg = aggregate(results)
    payload = {"label": label, "calibrated": calibrated, "aggregate": agg, "results": [r.to_dict() for r in results]}
    stem = "calibrated" if calibrated else "raw"
    (OUT / f"{label}_{stem}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT / f"{label}_{stem}.md").write_text(render_md(agg, results), encoding="utf-8")
    return agg


def main():
    verify_frozen_corpora()
    reports = {}
    reports["original50_raw"] = run_cases(load_frozen_50(), "original50", False)
    reports["original50_calibrated"] = run_cases(load_frozen_50(), "original50", True)
    shadow = normalize_shadow(load_shadow_20())
    reports["shadow20_raw"] = run_cases(shadow, "shadow20", False)
    reports["shadow20_calibrated"] = run_cases(shadow, "shadow20", True)
    summary = {k: {"pass": v["pass_count"], "fail": v["fail_count"], "score": v["total_score"]} for k, v in reports.items()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
