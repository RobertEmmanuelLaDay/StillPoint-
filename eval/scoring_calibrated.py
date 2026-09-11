from __future__ import annotations

from dataclasses import dataclass

from normalize import canonical_set


@dataclass
class CheckResult:
    name: str
    status: str
    expected: object = None
    actual: object = None
    reason: str = ""


def score_tools_calibrated(expected_caps: list[str], forbidden_tools: list[str], actual_tools: list[str]) -> CheckResult:
    expected = canonical_set(expected_caps)
    forbidden = canonical_set(forbidden_tools)
    actual = canonical_set(actual_tools)
    banned = [t for t in actual if t in forbidden]
    missing = [t for t in expected if t not in actual]
    extra = [t for t in actual if t not in expected]
    if banned:
        return CheckResult("tools", "fail", expected, actual, f"forbidden tools granted: {banned}")
    if missing:
        return CheckResult("tools", "fail", expected, actual, f"missing required capabilities/tools: {missing}")
    if extra:
        return CheckResult("tools", "fail", expected, actual, f"unnecessary tools: {extra}")
    return CheckResult("tools", "pass", expected, actual)
