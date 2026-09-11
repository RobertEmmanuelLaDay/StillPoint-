from __future__ import annotations

import re
from collections import defaultdict

from .intent import action_intent
from .models import WorkPlan
from .policy import CompanyPolicy
from .registry import AgentRegistry


def has_term(text: str, term: str) -> bool:
    """Word/phrase match. 'app' does not match 'approved'; 'media' does not match 'metadata'."""
    if not term:
        return False
    lowered = text.lower()
    needle = term.lower()
    if " " in needle:
        return needle in lowered
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered) is not None


class Router:
    KEYWORDS: dict[str, tuple[str, ...]] = {
        "author": (
            "chapter", "essay", "manuscript", "rewrite", "speech", "script", "prose",
            "story", "book text", "voice", "paragraph", "typo", "subtitle", "comma",
            "preface", "notes",
        ),
        "press": (
            "kdp", "epub", "isbn", "book interior", "metadata", "publishing", "publishable",
            "edition", "typeset", "front matter", "back matter", "book wrap", "print run files",
        ),
        "signal": (
            "marketing", "pr", "press release", "social", "outreach", "campaign",
            "audience", "speaking", "one-sheet", "newsletter", "launch copy", "email",
            "letter", "announcement",
        ),
        "ledger": (
            "budget", "cost", "price", "pricing", "revenue", "royalty", "cash", "p&l", "profit",
            "finance", "financial", "expense", "runway", "forecast", "cfo", "margin",
            "purchase", "economics",
        ),
        "research": (
            "research", "find out", "verify", "verified", "citation", "evidence", "latest",
            "current", "fact check", "fact-check", "look up", "investigate", "official sources",
        ),
        "builder": (
            "code", "runtime", "api", "automation", "software", "repo",
            "python", "javascript", "database", "cli", "mcp", "integration", "unit tests",
            "function", "migration",
        ),
        "stillpoint": (
            "audit", "review final", "adversarial review", "contradiction",
            "integrity review", "risk review",
        ),
    }

    def __init__(self, registry: AgentRegistry, policy: CompanyPolicy):
        self.registry = registry
        self.policy = policy

    def _scores(self, goal: str) -> dict[str, int]:
        scores: dict[str, int] = defaultdict(int)
        for agent_id, terms in self.KEYWORDS.items():
            if agent_id not in self.registry.ids():
                continue
            for term in terms:
                if has_term(goal, term):
                    scores[agent_id] += 3 if " " in term else 1
        return dict(scores)

    def _capabilities(self, goal: str, primary: str) -> tuple[list[str], bool]:
        caps: list[str] = []
        research = False
        if has_term(goal, "look up") or has_term(goal, "current") or has_term(goal, "latest"):
            research = True
        if has_term(goal, "official sources") or has_term(goal, "fact-check") or has_term(goal, "fact check"):
            research = True
        if has_term(goal, "verify") or has_term(goal, "verified") or has_term(goal, "research"):
            research = True
        if research:
            caps.append("web_research")
        if has_term(goal, "on x") or has_term(goal, "twitter") or has_term(goal, "x posts") or has_term(goal, "public posts"):
            caps.append("x_research")
            research = True
        if primary in {"builder", "ledger"} and (
            has_term(goal, "python") or has_term(goal, "code") or has_term(goal, "sha-256")
            or has_term(goal, "function") or has_term(goal, "unit tests") or has_term(goal, "cli")
        ):
            caps.append("code_execution")
        return list(dict.fromkeys(caps)), research

    def _primary(self, goal: str, scores: dict[str, int]) -> str:
        intent = action_intent(goal)
        if has_term(goal, "audit") or has_term(goal, "integrity review") or has_term(goal, "adversarial review"):
            return "stillpoint"
        if has_term(goal, "python") or has_term(goal, "unit tests") or has_term(goal, "api") or has_term(goal, "cli"):
            if not (has_term(goal, "chapter") or has_term(goal, "manuscript") or has_term(goal, "essay")):
                return "builder"
        if intent in {"spend", "sign"} or has_term(goal, "budget") or has_term(goal, "runway") or has_term(goal, "economics"):
            if not has_term(goal, "kdp"):
                return "ledger"
        if re.search(r"\$\s*[0-9]", goal) or has_term(goal, "purchase"):
            return "ledger"
        if intent == "send_email":
            return "signal"
        if re.search(r"\bsend me\b", goal, re.I) and (
            has_term(goal, "draft") or has_term(goal, "chapter") or has_term(goal, "manuscript")
        ):
            return "author"
        if (
            has_term(goal, "kdp") or has_term(goal, "isbn") or has_term(goal, "epub")
            or has_term(goal, "book interior") or has_term(goal, "publication-ready")
            or has_term(goal, "publication ready") or has_term(goal, "publishing")
        ):
            return "press"
        if has_term(goal, "email") or has_term(goal, "outreach") or has_term(goal, "press release") or has_term(goal, "letter"):
            return "signal"
        if has_term(goal, "chapter") or has_term(goal, "manuscript") or has_term(goal, "typo") or has_term(goal, "subtitle") or has_term(goal, "comma") or has_term(goal, "voice"):
            return "author"
        if has_term(goal, "look up") or has_term(goal, "fact-check") or has_term(goal, "fact check"):
            return "research"
        ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        if ranked and ranked[0][1] > 0:
            return ranked[0][0]
        return "orchestra"

    def _contributors(self, goal: str, primary: str, scores: dict[str, int], research_required: bool) -> list[str]:
        out: list[str] = []
        if primary == "press" and (has_term(goal, "manuscript") or has_term(goal, "chapter")):
            out.append("author")
        if research_required and primary != "research":
            out.append("research")
        if primary == "builder" and research_required:
            if "research" not in out:
                out.append("research")
        # Do not add a department just because a token appeared.
        return [c for c in out if c != primary][:3]

    def plan(self, goal: str) -> WorkPlan:
        scores = self._scores(goal)
        primary = self._primary(goal, scores)
        intent = self.policy.action_intent(goal)
        caps, research_required = self._capabilities(goal, primary)
        contributors = self._contributors(goal, primary, scores, research_required)
        review_required, review_reason = self.policy.review_requirement(goal)
        approval_required, approval_reason = self.policy.approval_requirement(goal)
        if primary == "stillpoint":
            review_required = False
            review_reason = ""
        return WorkPlan(
            primary=primary,
            contributors=contributors,
            review_required=review_required,
            review_reason=review_reason,
            approval_required=approval_required,
            approval_reason=approval_reason,
            routing_reason="intent/function match" if scores else "executive triage",
            capabilities=caps,
            research_required=research_required,
            external_action_intent=intent,
        )
