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

from frozen import load_shadow_20, verify_frozen_corpora
from run_eval import eval_case, render_md
from scoring import aggregate


def load_shadow():
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


def main():
    verify_frozen_corpora()
    results = [eval_case(c) for c in load_shadow()]
    agg = aggregate(results)
    out = HERE / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "shadow.json").write_text(
        json.dumps({"aggregate": agg, "results": [r.to_dict() for r in results]}, indent=2),
        encoding="utf-8",
    )
    (out / "shadow.md").write_text(render_md(agg, results), encoding="utf-8")
    print(json.dumps(agg, indent=2))
    for r in results:
        if not r.passed:
            print(f"FAIL {r.case_id}: {r.failure_reason}")
    return 0 if agg["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
