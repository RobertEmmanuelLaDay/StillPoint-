from __future__ import annotations

import re
from datetime import date, timedelta
from collections import defaultdict

from .models import WorkPlan
from .capabilities import ToolRequest, tool_request_to_dict, web_research, x_research, code_execution


def has_term(text, term):
    if not term:
        return False
    lowered = text.lower()
    needle = term.lower()
    if " " in needle:
        return needle in lowered
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered) is not None


class Router:
    KEYWORDS = {
        "author": ("chapter", "essay", "manuscript", "rewrite", "speech", "script", "prose", "story", "book text", "voice", "paragraph", "typo", "subtitle", "comma", "preface", "notes"),
        "press": ("kdp", "epub", "isbn", "book interior", "metadata", "publishing", "publishable", "edition", "typeset", "front matter", "back matter", "book wrap", "print run files", "paperback", "cover", "book package"),
        "signal": ("marketing", "pr", "press release", "social", "outreach", "campaign", "audience", "speaking", "one-sheet", "newsletter", "launch copy", "email", "letter", "announcement", "note"),
        "ledger": ("budget", "cost", "price", "pricing", "revenue", "royalty", "cash", "p&l", "profit", "finance", "financial", "expense", "runway", "forecast", "cfo", "margin", "purchase", "economics", "contract", "agreement"),
        "research": ("research", "find out", "verify", "verified", "citation", "evidence", "latest", "current", "fact check", "fact-check", "look up", "investigate", "official sources", "scan", "cite"),
        "builder": ("code", "runtime", "api", "automation", "software", "repo", "python", "javascript", "database", "cli", "mcp", "integration", "unit tests", "function", "migration", "implement", "client retry"),
        "stillpoint": ("audit", "review final", "adversarial review", "contradiction", "integrity review", "risk review"),
    }
    ARTIFACT = {"author": "prose", "press": "edition_pack", "signal": "communication_draft", "ledger": "finance_memo", "research": "evidence_packet", "builder": "code", "stillpoint": "review_judgment", "orchestra": "plan"}

    def __init__(self, registry, policy):
        self.registry = registry
        self.policy = policy

    def _scores(self, goal):
        scores = defaultdict(int)
        for aid, terms in self.KEYWORDS.items():
            if aid not in self.registry.ids():
                continue
            for term in terms:
                if has_term(goal, term):
                    scores[aid] += 3 if " " in term else 1
        return dict(scores)

    @staticmethod
    def _builder_delivery(goal: str) -> bool:
        return bool(
            re.search(r"\b(?:implement|build|write|create|fix|debug|refactor|run|execute)\b.{0,60}\b(?:client|code|python|javascript|api|cli|test|tests|function|runtime|software)\b", goal, re.I)
            or re.search(r"\b(?:unit tests?|python|code interpreter|checksum calculation)\b", goal, re.I)
        )

    @staticmethod
    def _research_request(goal: str) -> bool:
        return bool(re.search(r"\b(?:look up|find out|research|investigate|fact[- ]check|verify|scan|what is the current|latest|cite the live)\b", goal, re.I))

    def _capabilities(self, goal, primary):
        caps: list[str] = []
        x_specific = any(has_term(goal, t) for t in ("on x", "twitter", "x posts", "public posts"))
        web_specific = any(has_term(goal, t) for t in ("look up", "current", "latest", "official sources", "fact-check", "fact check", "verify", "verified", "cite the live", "live page"))
        broad_research = has_term(goal, "research") and not x_specific
        research = x_specific or web_specific or broad_research
        if x_specific:
            caps.append("x_research")
        if web_specific or broad_research:
            caps.append("web_research")
        if primary == "builder" and self._builder_delivery(goal):
            caps.append("code_execution")
        return list(dict.fromkeys(caps)), research

    @staticmethod
    def _scoped_requests(goal: str, caps: list[str]) -> list[dict]:
        requests: list[ToolRequest] = []
        iso_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", goal)
        from_date = None
        to_date = None
        if iso_dates:
            from_date = iso_dates[0]
            if len(iso_dates) > 1:
                to_date = iso_dates[1]
        elif re.search(r"\blast week\b", goal, re.I):
            from_date = (date.today() - timedelta(days=7)).isoformat()
        elif re.search(r"\blast month\b", goal, re.I):
            from_date = (date.today() - timedelta(days=30)).isoformat()
        elif re.search(r"\bthis year\b", goal, re.I):
            from_date = date(date.today().year, 1, 1).isoformat()

        for cap in caps:
            if cap == "web_research":
                requests.append(web_research())
            elif cap == "x_research":
                requests.append(x_research(from_date=from_date or (date.today() - timedelta(days=30)).isoformat(), to_date=to_date))
            elif cap == "code_execution":
                requests.append(code_execution())
        return [tool_request_to_dict(r) for r in requests]

    def _primary(self, goal, scores, intent):
        if any(has_term(goal, t) for t in ("audit", "integrity review", "adversarial review")):
            return "stillpoint"

        # A requested implementation owns the deliverable even when research precedes it.
        if self._builder_delivery(goal):
            return "builder"

        # Explicit evidence retrieval owns research, even when the subject happens to be
        # publishing metadata such as KDP/ISBN rules.
        if self._research_request(goal):
            return "research"

        if intent in {"spend", "sign"} or any(has_term(goal, t) for t in ("budget", "runway", "economics", "contract", "agreement")):
            if not has_term(goal, "kdp"):
                return "ledger"
        if re.search(r"\$\s*[0-9]", goal) or has_term(goal, "purchase"):
            return "ledger"
        if intent == "send_email":
            return "signal"
        if re.search(r"\bsend me\b", goal, re.I) and any(has_term(goal, t) for t in ("draft", "chapter", "manuscript")):
            return "author"
        if any(has_term(goal, t) for t in ("kdp", "isbn", "epub", "book interior", "publication-ready", "publication ready", "publishing", "paperback", "cover", "book package")):
            return "press"
        if any(has_term(goal, t) for t in ("email", "outreach", "press release", "letter", "note")):
            return "signal"
        if any(has_term(goal, t) for t in ("chapter", "manuscript", "typo", "subtitle", "comma", "voice")):
            return "author"
        ranked = sorted(scores.items(), key=lambda p: (-p[1], p[0]))
        return ranked[0][0] if ranked and ranked[0][1] > 0 else "orchestra"

    def plan(self, goal):
        bundle = self.policy.authority(goal)
        actions = bundle.restricted_intents
        intent = actions[0] if actions else "none"
        scores = self._scores(goal)
        primary = self._primary(goal, scores, intent)
        caps, research = self._capabilities(goal, primary)

        contributors: list[str] = []
        specs: list[dict] = []
        # Press needs Author only when editorial manuscript work is genuinely part of the
        # publication milestone, not merely because the word "manuscript" occurs.
        if primary == "press" and (
            (has_term(goal, "publication-ready") or has_term(goal, "publication ready"))
            and has_term(goal, "manuscript")
            and (has_term(goal, "verified") or has_term(goal, "requirements"))
        ):
            contributors.append("author")
        if research and primary != "research":
            contributors.append("research")
        contributors = list(dict.fromkeys(c for c in contributors if c != primary))[:3]

        for contributor in contributors:
            contributor_caps: list[str] = []
            if contributor == "research":
                contributor_caps = [c for c in caps if c in {"web_research", "x_research"}]
            specs.append({"id": contributor, "reason": "needed specialist contribution", "capabilities": contributor_caps, "before": "primary"})

        primary_caps = list(caps)
        if "research" in contributors and primary != "research":
            primary_caps = [c for c in primary_caps if c not in {"web_research", "x_research"}]

        scoped_requests = self._scoped_requests(goal, caps)
        primary_requests = [r for r in scoped_requests if r.get("capability") in primary_caps]
        for spec in specs:
            spec["tool_requests"] = [r for r in scoped_requests if r.get("capability") in spec.get("capabilities", [])]

        review, review_reason = self.policy.review_requirement(goal)
        approval, approval_reason = self.policy.approval_requirement(goal)
        if primary == "stillpoint":
            review = False
            review_reason = ""

        return WorkPlan(
            primary=primary,
            contributors=contributors,
            review_required=review,
            review_reason=review_reason,
            approval_required=approval,
            approval_reason=approval_reason,
            routing_reason="intent/function match" if scores else "executive triage",
            capabilities=caps,
            primary_capabilities=primary_caps,
            tool_requests=scoped_requests,
            primary_tool_requests=primary_requests,
            research_required=research,
            expected_artifact=self.ARTIFACT.get(primary, "other"),
            external_action_intent=intent,
            restricted_actions=actions,
            contributor_specs=specs,
            authority_revision=self.policy.authority_revision(goal),
        )
