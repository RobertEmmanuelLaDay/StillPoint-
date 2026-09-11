from __future__ import annotations

import re

from .intent import action_intent, approval_reason_for


class CompanyPolicy:
    # Kept for V5 test imports that may reference the names.
    ACTION_PATTERNS = {
        "publish or release publicly": [r"\bpublish\b"],
        "send external communication": [r"\bsend\b"],
        "post to a public account": [r"\btweet\b"],
        "move or commit money": [r"\bspend\b"],
        "accept a binding commitment": [r"\bsign\b"],
        "destructive external change": [r"\bdelete\b"],
    }

    REVIEW_PATTERNS = {
        "publication": [
            r"\bpublication[- ]ready\b",
            r"\bfinal manuscript\b",
            r"\bbook interior\b",
            r"\bcover metadata\b",
        ],
        "public claim": [
            r"\bpress release\b",
            r"\bpublic statement\b",
        ],
        "finance": [
            r"\bbudget\b",
            r"\bpricing\b",
            r"\broyalt",
            r"\bp&l\b",
            r"\bcash (?:flow|runway)\b",
            r"\brunway forecast\b",
        ],
        "source integrity": [
            r"\bfact[- ]check\b",
            r"\bverify sources\b",
            r"\bsource integrity\b",
        ],
        "legal/privacy": [
            r"\blegal\b",
            r"\bprivacy\b",
            r"\bpersonal data\b",
        ],
        "canon/locked text": [
            r"\bcanon\b",
            r"\blocked text\b",
            r"\bfinal doctrine\b",
        ],
    }

    def action_intent(self, goal: str) -> str:
        from .authority.gate import authority_intent
        gated, required, _ = authority_intent(goal)
        if required and gated != "none":
            return gated
        overlay = action_intent(goal)
        return overlay if overlay != "none" else gated

    def approval_requirement(self, goal: str) -> tuple[bool, str]:
        intent = self.action_intent(goal)
        if intent == "none":
            return False, ""
        return True, approval_reason_for(intent) or intent

    def review_requirement(self, goal: str) -> tuple[bool, str]:
        reasons: list[str] = []
        for reason, patterns in self.REVIEW_PATTERNS.items():
            if any(re.search(pattern, goal, re.I) for pattern in patterns):
                reasons.append(reason)
        approval, approval_reason = self.approval_requirement(goal)
        if approval and approval_reason and approval_reason not in reasons:
            reasons.append(approval_reason)
        if re.search(r"\$\s*[0-9]", goal) and self.action_intent(goal) == "none":
            if "finance" not in reasons:
                reasons.append("finance")
        if re.search(r"\b(?:contract|agreement)\b", goal, re.I) and self.action_intent(goal) in {"sign", "other_external"}:
            reasons.append("legal/privacy")
        return (bool(reasons), ", ".join(reasons))
