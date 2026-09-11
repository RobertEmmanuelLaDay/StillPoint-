from __future__ import annotations

import hashlib
import json
import re

from .authority.gate import authority_bundle
from .intent import approval_reason_for


class CompanyPolicy:
    REVIEW_PATTERNS = {
        "publication": [r"\bpublication[- ]ready\b", r"\bfinal manuscript\b", r"\bbook interior\b", r"\bcover metadata\b"],
        "public claim": [r"\bpress release\b", r"\bpublic statement\b"],
        "finance": [r"\bbudget\b", r"\bpricing\b", r"\broyalt", r"\bp&l\b", r"\bcash (?:flow|runway)\b", r"\brunway forecast\b"],
        "source integrity": [r"\bfact[- ]check\b", r"\bverify sources\b", r"\bsource integrity\b"],
        "legal/privacy": [r"\blegal\b", r"\bprivacy\b", r"\bpersonal data\b", r"\bcontract\b", r"\bagreement\b"],
        "canon/locked text": [r"\bcanon\b", r"\blocked text\b", r"\bfinal doctrine\b"],
    }
    REVIEW_ACTIONS = {"publish", "social_post", "spend", "sign", "delete", "other_external"}

    def __init__(self, provider=None, authority_model: str | None = None):
        self.provider = provider
        self.authority_model = authority_model
        self._authority_cache: dict[str, object] = {}

    def authority(self, goal: str):
        if goal not in self._authority_cache:
            self._authority_cache[goal] = authority_bundle(goal, provider=self.provider, model=self.authority_model)
        return self._authority_cache[goal]

    def action_intents(self, goal: str) -> list[str]:
        return self.authority(goal).restricted_intents

    def action_intent(self, goal: str) -> str:
        return self.authority(goal).primary_intent

    def authority_revision(self, goal: str) -> str:
        bundle = self.authority(goal)
        canonical = [a.to_dict() for a in bundle.assessments]
        return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

    def approval_requirement(self, goal: str):
        actions = self.action_intents(goal)
        if not actions:
            return False, ""
        reasons = [approval_reason_for(a) or a for a in actions]
        return True, ", ".join(dict.fromkeys(reasons))

    def review_requirement(self, goal: str):
        reasons: list[str] = []
        for reason, patterns in self.REVIEW_PATTERNS.items():
            if any(re.search(p, goal, re.I) for p in patterns):
                reasons.append(reason)

        actions = self.action_intents(goal)
        # External communication still requires CEO approval, but routine sending is not
        # automatically a Still Point review. Consequential/public/financial/legal/destructive
        # execution is.
        for action in actions:
            if action in self.REVIEW_ACTIONS:
                reason = approval_reason_for(action) or action
                if reason not in reasons:
                    reasons.append(reason)

        if re.search(r"\$\s*[0-9]", goal) and "finance" not in reasons:
            reasons.append("finance")

        return bool(reasons), ", ".join(reasons)
