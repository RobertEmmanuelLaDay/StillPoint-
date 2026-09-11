from __future__ import annotations
import re
from .clauses import split_clauses
from .schema import AuthorityAssessment, AuthorityBundle, DISCUSSION_MODES
_WORD=r"(?<![a-z0-9]){0}(?![a-z0-9])"
_DISCUSSION_OPENERS=("analyze","analyse","recommend","compare","draft","prepare","find","identify","should","whether","if","what","give")

def _has(text,*terms):
    lowered=text.lower()
    for term in terms:
        if " " in term:
            if term in lowered:return True
        elif re.search(_WORD.format(re.escape(term)),lowered):return True
    return False

def assess(goal): return assess_bundle(goal).to_compat()
def assess_bundle(goal):
    clauses=split_clauses(goal)
    if not clauses:return AuthorityBundle([AuthorityAssessment(reason="empty")])
    return AuthorityBundle([_assess_clause(c) for c in clauses])

def _assess_clause(text):
    mode=_mode(text); family=_family(text); target=_target(text,family)
    if mode=="return_to_ceo": return AuthorityAssessment("none","return_to_ceo","ceo",0.9,"ceo delivery","deterministic",text)
    if mode=="prohibit": return AuthorityAssessment(family if family!="none" else "none","prohibit",target,0.9,"clause prohibition","deterministic",text)
    if mode in DISCUSSION_MODES:return AuthorityAssessment(family,mode,target,0.85,f"mode={mode}","deterministic",text)
    if family!="none" and mode in {"execute","unknown"}:return AuthorityAssessment(family,"execute",target,0.86,f"execute {family}","deterministic",text)
    if _fail_closed(text,mode,family,target):return AuthorityAssessment("other_external","execute",target if target!="unknown" else "unknown",0.55,"unresolved external imperative","deterministic",text)
    return AuthorityAssessment("none",mode,target,0.5,"no restricted action in clause","deterministic",text)

def _fail_closed(text,mode,family,target):
    if family!="none" or mode in DISCUSSION_MODES:return False
    if target not in {"external_person","public","financial","external_system"} and not _structural_external(text):return False
    return _structural_imperative(text)

def _structural_imperative(text):
    stripped=text.strip()
    if not stripped:return False
    if re.match(r"^(please|kindly)\b",stripped,re.I): return True
    first=re.split(r"\s+",stripped,maxsplit=1)[0].lower().strip(".,!?")
    if not first or not first.isalpha() or first in _DISCUSSION_OPENERS:return False
    # Descriptive/copular clauses are not imperatives.
    if re.search(r"\b(?:is|are|was|were|has|have|had|seems|appears|contains|costs)\b", stripped, re.I): return False
    # Unknown verbs fail closed only when phrased as command-like bare infinitives.
    return bool(re.match(r"^(?:please\s+|kindly\s+)?[a-z]+(?:\s+|$)", stripped, re.I))

def _structural_external(text):
    return bool(_external_recipient(text) or _has(text,"publicly","production","offsite","repository","database") or "$" in text)

def _mode(text):
    # A discussion/draft verb followed by an explicit execution command in the same
    # clause is execution authority for that commanded action.
    if re.search(r"^\s*(?:draft|compose|sketch|prepare|assemble|analyze|analyse|recommend|compare|find|identify)\b.*\b(?:and|then)\s+(?:send|email|transmit|deliver|forward|publish|release|buy|spend|pay|purchase|sign|initial|execute|delete|wipe|destroy|upload|post|tweet)\b", text, re.I):
        return "execute"
    if re.search(r"\bdo not\b|\bdon't\b",text,re.I):return "prohibit"
    if _has(text,"send me","give me","back to me") and not _external_recipient(text):return "return_to_ceo"
    if re.search(r"\bhand .{0,40}\bback to me\b",text,re.I):return "return_to_ceo"
    if _has(text,"analyze","analyse","whether we should","should we","what would happen if"):return "analyze"
    if _has(text,"recommend","recommendation only","recommendation"):return "recommend"
    if re.match(r"^\s*(?:draft|compose|sketch)\b",text,re.I) or re.search(r"\b(?:draft|compose|sketch)\s+(?:an?|the|this|possible)\b",text,re.I):return "draft"
    if _has(text,"prepare","assemble","for possible"):return "prepare"
    if _has(text,"compare"):return "compare"
    if _has(text,"find","find out","look up","identify","scan","cite","may eventually","might wipe","might delete"):return "find"
    if _looks_known_imperative(text) or _structural_imperative(text):return "execute"
    return "unknown"

def _family(text):
    if _has(text,"wipe","destroy","delete","drop") and _has(text,"database","repo","repository","production","account","site","records","files"):return "delete"
    if _has(text,"sign","initial","execute the agreement","execute agreement","accept the terms") and _has(text,"contract","agreement","terms","this","the"):return "sign"
    if _has(text,"spend","buy","purchase","pay","transfer","place the","ad buy","place an order") and ("$" in text.lower() or _has(text,"usd","funds","money","subscription","order","buy","purchase","spend","ad","invoice")):return "spend"
    if _has(text,"tweet","post this to","post it on"):return "social"
    if _has(text,"publish","go live","list publicly","release publicly","upload and publish"):return "publish"
    if _has(text,"make") and _has(text,"live"):return "publish"
    if _has(text,"release") and _has(text,"kdp","amazon","paperback","book","publicly","listing"):return "publish"
    if _has(text,"send","email","transmit","forward","deliver","hand"):return "communicate"
    return "none"

def _external_recipient(text):
    if re.search(r"\bto (?:the )?(?:publisher|printer|secretary|principal|school|counsel|designer|vendor|them|him|her)\b", text, re.I):
        return True
    if re.search(r"\bto\s+[A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+)?\b", text) and not re.search(r"\bto me\b", text, re.I):
        return True
    if re.search(r"\bto\s+[^\s@]+@[^\s@]+\.[^\s@]+", text, re.I):
        return True
    return False

def _target(text,family):
    if _has(text,"send me","give me","to me","back to me"):return "ceo"
    if family=="publish" or _has(text,"publicly","kdp","amazon"):return "public"
    if family=="spend" or "$" in text:return "financial"
    if family=="delete" or _has(text,"database","repository","production"):return "external_system"
    if _external_recipient(text):return "external_person"
    return "unknown"

def _looks_known_imperative(text):
    return bool(re.match(r"^(send|email|transmit|deliver|forward|hand|publish|release|buy|spend|pay|purchase|sign|initial|execute|delete|wipe|destroy|upload|place|list|make)\b",text.strip(),re.I))
