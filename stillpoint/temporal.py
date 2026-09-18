from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

CLAIM_STATUSES = {"current", "expired", "superseded", "historical", "retracted"}
TRUTH_STATES = {"unknown", "supported", "contradicted"}
CLAIM_KINDS = {"observation", "assertion", "classification", "prediction", "historical"}
EVIDENCE_RELATIONS = {"supports", "weakens", "contradicts", "supersedes"}
WARRANT_STATUSES = {"active", "review_required", "expired", "revoked", "completed", "superseded", "released"}
WARRANT_BASIS_TYPES = {"ceo_instruction", "policy", "contract", "statute", "delegation", "system_rule", "manual_review"}
FORBIDDEN_WARRANT_BASIS_TYPES = {"prediction", "claim", "confidence"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aware(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


class TemporalAuthorityLedger:
    """Durable temporal claims, evidence, warrants, re-entry, and release.

    Claims are information. Warrants are authority. The ledger deliberately keeps
    them in different tables and requires an explicit warrant before an action can
    be authorized.
    """

    def __init__(self, db):
        self.db = db

    @property
    def conn(self):
        return self.db._connection()

    def record_claim(
        self,
        *,
        subject: str,
        predicate: str,
        value: Any,
        domain: str,
        source: str,
        observed_at: str | None = None,
        asserted_at: str | None = None,
        effective_from: str | None = None,
        effective_until: str | None = None,
        confidence: float | None = None,
        truth_state: str = "unknown",
        claim_kind: str = "assertion",
        subject_mode: str = "unspecified",
        expires_at: str | None = None,
        review_conditions: list[str] | None = None,
        provenance: dict[str, Any] | None = None,
        supersedes_claim_id: str | None = None,
        claim_id: str | None = None,
    ) -> str:
        if not subject or not predicate or not domain or not source:
            raise ValueError("subject, predicate, domain, and source are required")
        if truth_state not in TRUTH_STATES:
            raise ValueError(f"invalid truth_state: {truth_state}")
        if claim_kind not in CLAIM_KINDS:
            raise ValueError(f"invalid claim_kind: {claim_kind}")
        if subject_mode not in {"dynamic", "static", "unspecified"}:
            raise ValueError(f"invalid subject_mode: {subject_mode}")
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1")
        asserted_at = asserted_at or _now()
        observed_at = observed_at or asserted_at
        for label, value_at in (
            ("observed_at", observed_at),
            ("asserted_at", asserted_at),
            ("effective_from", effective_from),
            ("effective_until", effective_until),
            ("expires_at", expires_at),
        ):
            if value_at and not _aware(value_at):
                raise ValueError(f"{label} must be timezone-aware")
        if effective_from and effective_until and _aware(effective_until) <= _aware(effective_from):
            raise ValueError("effective_until must be after effective_from")
        claim_id = claim_id or uuid.uuid4().hex[:20]
        conn = self.conn
        try:
            conn.execute("BEGIN IMMEDIATE")
            if supersedes_claim_id:
                prior = conn.execute("SELECT * FROM temporal_claims WHERE id=?", (supersedes_claim_id,)).fetchone()
                if not prior:
                    raise KeyError(supersedes_claim_id)
                if prior["subject"] != subject or prior["domain"] != domain:
                    raise ValueError("superseding claim must remain in the same subject and domain")
                conn.execute(
                    "UPDATE temporal_claims SET status='superseded',updated_at=? WHERE id=?",
                    (_now(), supersedes_claim_id),
                )
            conn.execute(
                """INSERT INTO temporal_claims
                (id,subject,predicate,value_json,domain,source,observed_at,asserted_at,effective_from,
                 effective_until,confidence,truth_state,claim_kind,subject_mode,status,
                 supersedes_claim_id,expires_at,review_conditions_json,provenance_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    claim_id,
                    subject,
                    predicate,
                    _json(value),
                    domain,
                    source,
                    observed_at,
                    asserted_at,
                    effective_from,
                    effective_until,
                    confidence,
                    truth_state,
                    claim_kind,
                    subject_mode,
                    "current",
                    supersedes_claim_id,
                    expires_at,
                    _json(review_conditions or []),
                    _json(provenance or {}),
                    _now(),
                    _now(),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        if supersedes_claim_id:
            self._mark_claim_warrants_review(supersedes_claim_id, "supporting claim was superseded")
        return claim_id

    def _refresh_claim(self, claim_id: str, now_iso: str | None = None) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM temporal_claims WHERE id=?", (claim_id,)).fetchone()
        if not row:
            raise KeyError(claim_id)
        data = dict(row)
        now = _aware(now_iso or _now())
        expires = _aware(data.get("expires_at"))
        effective_until = _aware(data.get("effective_until"))
        if data["status"] == "current" and now and ((expires and now >= expires) or (effective_until and now >= effective_until)):
            self.conn.execute("UPDATE temporal_claims SET status='expired',updated_at=? WHERE id=?", (_now(), claim_id))
            self.conn.commit()
            data["status"] = "expired"
        return data

    def get_claim(self, claim_id: str, *, now_iso: str | None = None) -> dict[str, Any]:
        return self._refresh_claim(claim_id, now_iso)

    def list_claims(self, *, subject: str | None = None, domain: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM temporal_claims WHERE 1=1"
        args: list[Any] = []
        if subject is not None:
            sql += " AND subject=?"
            args.append(subject)
        if domain is not None:
            sql += " AND domain=?"
            args.append(domain)
        sql += " ORDER BY created_at,id"
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def record_evidence(
        self,
        *,
        subject: str,
        domain: str,
        source: str,
        payload: Any,
        observed_at: str | None = None,
        provenance: dict[str, Any] | None = None,
        evidence_id: str | None = None,
    ) -> str:
        observed_at = observed_at or _now()
        if not _aware(observed_at):
            raise ValueError("observed_at must be timezone-aware")
        evidence_id = evidence_id or uuid.uuid4().hex[:20]
        self.conn.execute(
            """INSERT INTO temporal_evidence
            (id,subject,domain,source,observed_at,payload_json,provenance_json,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (evidence_id, subject, domain, source, observed_at, _json(payload), _json(provenance or {}), _now()),
        )
        self.conn.commit()
        return evidence_id

    def link_evidence(self, claim_id: str, evidence_id: str, relation: str, note: str = "") -> None:
        if relation not in EVIDENCE_RELATIONS:
            raise ValueError(f"invalid evidence relation: {relation}")
        claim = self.conn.execute("SELECT * FROM temporal_claims WHERE id=?", (claim_id,)).fetchone()
        evidence = self.conn.execute("SELECT * FROM temporal_evidence WHERE id=?", (evidence_id,)).fetchone()
        if not claim:
            raise KeyError(claim_id)
        if not evidence:
            raise KeyError(evidence_id)
        if claim["subject"] != evidence["subject"]:
            raise ValueError("evidence subject does not match claim subject")
        self.conn.execute(
            "INSERT OR REPLACE INTO temporal_claim_evidence(claim_id,evidence_id,relation,note,created_at) VALUES(?,?,?,?,?)",
            (claim_id, evidence_id, relation, note, _now()),
        )
        self.conn.commit()
        if relation in {"weakens", "contradicts", "supersedes"}:
            self._mark_claim_warrants_review(claim_id, f"new evidence {relation} supporting claim")

    def list_evidence(self, *, subject: str | None = None, domain: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM temporal_evidence WHERE 1=1"
        args: list[Any] = []
        if subject is not None:
            sql += " AND subject=?"
            args.append(subject)
        if domain is not None:
            sql += " AND domain=?"
            args.append(domain)
        sql += " ORDER BY created_at,id"
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def issue_warrant(
        self,
        *,
        subject: str,
        domain: str,
        authorized_actions: list[str],
        scope: list[str],
        basis_type: str,
        basis: str,
        issued_by: str,
        claim_ids: list[str] | None = None,
        claim_bridge: str = "",
        issued_at: str | None = None,
        effective_from: str | None = None,
        expires_at: str | None = None,
        completion_condition: str = "",
        provenance: dict[str, Any] | None = None,
        supersedes_warrant_id: str | None = None,
        warrant_id: str | None = None,
    ) -> str:
        if basis_type in FORBIDDEN_WARRANT_BASIS_TYPES or basis_type not in WARRANT_BASIS_TYPES:
            raise ValueError("information, prediction, confidence, or a bare claim cannot self-authorize a warrant")
        if not subject or not domain or not basis or not issued_by:
            raise ValueError("subject, domain, basis, and issued_by are required")
        if not authorized_actions:
            raise ValueError("warrant requires at least one authorized action")
        if any(not isinstance(item, str) or not item.strip() for item in authorized_actions):
            raise ValueError("authorized actions must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in scope):
            raise ValueError("scope entries must be non-empty strings")
        issued_at = issued_at or _now()
        effective_from = effective_from or issued_at
        if not _aware(issued_at) or not _aware(effective_from) or (expires_at and not _aware(expires_at)):
            raise ValueError("warrant timestamps must be timezone-aware")
        if expires_at and _aware(expires_at) <= _aware(effective_from):
            raise ValueError("expires_at must be after effective_from")
        claim_ids = list(dict.fromkeys(claim_ids or []))
        for claim_id in claim_ids:
            claim = self._refresh_claim(claim_id, issued_at)
            if claim["status"] not in {"current", "historical"}:
                raise ValueError(f"claim {claim_id} is not current support")
            if claim["domain"] != domain and not claim_bridge.strip():
                raise ValueError("cross-domain claim use requires an explicit bridge")
        warrant_id = warrant_id or uuid.uuid4().hex[:20]
        conn = self.conn
        try:
            conn.execute("BEGIN IMMEDIATE")
            if supersedes_warrant_id:
                prior = conn.execute("SELECT id FROM temporal_warrants WHERE id=?", (supersedes_warrant_id,)).fetchone()
                if not prior:
                    raise KeyError(supersedes_warrant_id)
                conn.execute(
                    "UPDATE temporal_warrants SET status='superseded',updated_at=? WHERE id=?",
                    (_now(), supersedes_warrant_id),
                )
            conn.execute(
                """INSERT INTO temporal_warrants
                (id,subject,domain,authorized_actions_json,scope_json,basis_type,basis,issued_by,
                 claim_ids_json,claim_bridge,issued_at,effective_from,expires_at,completion_condition,
                 status,supersedes_warrant_id,review_reason,provenance_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    warrant_id,
                    subject,
                    domain,
                    _json(list(dict.fromkeys(authorized_actions))),
                    _json(list(dict.fromkeys(scope))),
                    basis_type,
                    basis,
                    issued_by,
                    _json(claim_ids),
                    claim_bridge,
                    issued_at,
                    effective_from,
                    expires_at,
                    completion_condition,
                    "active",
                    supersedes_warrant_id,
                    "",
                    _json(provenance or {}),
                    _now(),
                    _now(),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return warrant_id

    def get_warrant(self, warrant_id: str, *, now_iso: str | None = None) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM temporal_warrants WHERE id=?", (warrant_id,)).fetchone()
        if not row:
            raise KeyError(warrant_id)
        data = dict(row)
        now = _aware(now_iso or _now())
        expires = _aware(data.get("expires_at"))
        if data["status"] in {"active", "review_required"} and now and expires and now >= expires:
            self.conn.execute(
                "UPDATE temporal_warrants SET status='expired',updated_at=? WHERE id=?",
                (_now(), warrant_id),
            )
            self.conn.commit()
            data["status"] = "expired"
        return data

    def list_warrants(self, *, subject: str | None = None, domain: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM temporal_warrants WHERE 1=1"
        args: list[Any] = []
        if subject is not None:
            sql += " AND subject=?"
            args.append(subject)
        if domain is not None:
            sql += " AND domain=?"
            args.append(domain)
        sql += " ORDER BY created_at,id"
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def bind_action_warrant(self, action_id: str, warrant_id: str) -> None:
        if not self.conn.execute("SELECT 1 FROM action_requests WHERE id=?", (action_id,)).fetchone():
            raise KeyError(action_id)
        self.get_warrant(warrant_id)
        self.conn.execute(
            "INSERT OR IGNORE INTO temporal_action_warrants(action_id,warrant_id,bound_at) VALUES(?,?,?)",
            (action_id, warrant_id, _now()),
        )
        self.conn.commit()

    def list_action_warrants(self, action_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT w.* FROM temporal_action_warrants aw
               JOIN temporal_warrants w ON w.id=aw.warrant_id
               WHERE aw.action_id=? ORDER BY aw.bound_at,w.id""",
            (action_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def warrant_authorizes(
        self,
        warrant_id: str,
        *,
        action_type: str,
        domain: str,
        scope: list[str],
        now_iso: str | None = None,
    ) -> bool:
        warrant = self.get_warrant(warrant_id, now_iso=now_iso)
        if warrant["status"] != "active":
            return False
        now = _aware(now_iso or _now())
        effective_from = _aware(warrant["effective_from"])
        if not now or not effective_from or now < effective_from:
            return False
        if warrant["domain"] != domain:
            return False
        if action_type not in _load(warrant["authorized_actions_json"], []):
            return False
        allowed_scope = set(_load(warrant["scope_json"], []))
        return set(scope).issubset(allowed_scope)

    def authorize_action(
        self,
        action_id: str,
        action_type: str,
        domain: str,
        scope: list[str],
        *,
        now_iso: str | None = None,
    ) -> dict[str, Any]:
        bindings = self.list_action_warrants(action_id)
        if not bindings:
            raise PermissionError("action has no explicit temporal warrant")
        for warrant in reversed(bindings):
            if self.warrant_authorizes(
                warrant["id"], action_type=action_type, domain=domain, scope=scope, now_iso=now_iso
            ):
                return self.get_warrant(warrant["id"], now_iso=now_iso)
        raise PermissionError("no current scope-bound warrant authorizes this action")

    def ensure_runtime_warrant(
        self,
        *,
        action_id: str,
        task_id: str,
        action_type: str,
        target: str,
        scope: list[str],
        authority_revision: str,
        issued_at: str,
        expires_at: str,
    ) -> str:
        bindings = self.list_action_warrants(action_id)
        for warrant in reversed(bindings):
            provenance = _load(warrant.get("provenance_json"), {})
            if (
                provenance.get("authority_revision") == authority_revision
                and warrant["status"] in {"active", "review_required"}
            ):
                return warrant["id"]
        warrant_id = self.issue_warrant(
            subject=target,
            domain="external_action",
            authorized_actions=[action_type],
            scope=scope,
            basis_type="ceo_instruction",
            basis="restricted action derived from current CEO request and company policy",
            issued_by="stillpoint-runtime",
            issued_at=issued_at,
            effective_from=issued_at,
            expires_at=expires_at,
            completion_condition="exact authorized action completed with required external evidence",
            provenance={"task_id": task_id, "action_id": action_id, "authority_revision": authority_revision},
        )
        self.bind_action_warrant(action_id, warrant_id)
        return warrant_id

    def _mark_claim_warrants_review(self, claim_id: str, reason: str) -> None:
        for row in self.conn.execute(
            "SELECT id,claim_ids_json,status FROM temporal_warrants WHERE status='active'"
        ).fetchall():
            if claim_id in _load(row["claim_ids_json"], []):
                self.conn.execute(
                    "UPDATE temporal_warrants SET status='review_required',review_reason=?,updated_at=? WHERE id=?",
                    (reason, _now(), row["id"]),
                )
        self.conn.commit()

    def mark_action_warrants_review_required(self, action_id: str, *, reason: str) -> None:
        for warrant in self.list_action_warrants(action_id):
            if warrant["status"] == "active":
                self.conn.execute(
                    "UPDATE temporal_warrants SET status='review_required',review_reason=?,updated_at=? WHERE id=?",
                    (reason, _now(), warrant["id"]),
                )
        self.conn.commit()

    def revoke_warrant(self, warrant_id: str, reason: str = "") -> None:
        self._end_warrant(warrant_id, "revoked", reason)

    def complete_warrant(self, warrant_id: str) -> None:
        self._end_warrant(warrant_id, "completed", "")

    def complete_action_warrant(self, action_id: str) -> None:
        for warrant in self.list_action_warrants(action_id):
            if warrant["status"] == "active":
                self.complete_warrant(warrant["id"])

    def _end_warrant(self, warrant_id: str, status: str, reason: str) -> None:
        if status not in {"revoked", "completed", "superseded"}:
            raise ValueError(status)
        warrant = self.get_warrant(warrant_id)
        if warrant["status"] not in {"active", "review_required"}:
            return
        self.conn.execute(
            "UPDATE temporal_warrants SET status=?,review_reason=?,updated_at=? WHERE id=?",
            (status, reason, _now(), warrant_id),
        )
        self.conn.commit()

    def release_warrant(self, warrant_id: str, reason: str = "") -> None:
        warrant = self.get_warrant(warrant_id)
        if warrant["status"] in {"active", "review_required"}:
            raise ValueError("active authority must complete, expire, revoke, or be superseded before release")
        if warrant["status"] == "released":
            return
        self.conn.execute(
            "UPDATE temporal_warrants SET status='released',review_reason=?,updated_at=? WHERE id=?",
            (reason, _now(), warrant_id),
        )
        self.conn.commit()

    def open_reentry(
        self,
        *,
        subject: str,
        domain: str,
        reason: str,
        prior_warrant_id: str | None = None,
        trigger_evidence_id: str | None = None,
    ) -> str:
        if prior_warrant_id:
            self.get_warrant(prior_warrant_id)
        if trigger_evidence_id and not self.conn.execute(
            "SELECT 1 FROM temporal_evidence WHERE id=?", (trigger_evidence_id,)
        ).fetchone():
            raise KeyError(trigger_evidence_id)
        evaluation_id = uuid.uuid4().hex[:20]
        self.conn.execute(
            """INSERT INTO temporal_evaluations
            (id,subject,domain,reason,trigger_evidence_id,prior_warrant_id,status,disposition,
             rationale,new_warrant_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,'open','','','',?,?)""",
            (
                evaluation_id,
                subject,
                domain,
                reason,
                trigger_evidence_id,
                prior_warrant_id,
                _now(),
                _now(),
            ),
        )
        self.conn.commit()
        return evaluation_id

    def resolve_reentry(
        self,
        evaluation_id: str,
        *,
        disposition: str,
        rationale: str,
        new_warrant_id: str | None = None,
    ) -> None:
        if not self.conn.execute("SELECT 1 FROM temporal_evaluations WHERE id=?", (evaluation_id,)).fetchone():
            raise KeyError(evaluation_id)
        if new_warrant_id:
            self.get_warrant(new_warrant_id)
        self.conn.execute(
            """UPDATE temporal_evaluations
               SET status='closed',disposition=?,rationale=?,new_warrant_id=?,updated_at=?
               WHERE id=?""",
            (disposition, rationale, new_warrant_id or "", _now(), evaluation_id),
        )
        self.conn.commit()

    def list_reentries(self, *, subject: str | None = None) -> list[dict[str, Any]]:
        if subject is None:
            rows = self.conn.execute("SELECT * FROM temporal_evaluations ORDER BY created_at,id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM temporal_evaluations WHERE subject=? ORDER BY created_at,id", (subject,)
            ).fetchall()
        return [dict(row) for row in rows]
