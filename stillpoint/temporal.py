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
                if prior["subject"] != subject or prior["domain"] != domain or prior["predicate"] != predicate:
                    raise ValueError("superseding claim must remain on the same subject, domain, and predicate")
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

    def link_evidence(self, claim_id: str, evidence_id: str, relation: str, note: str = "") -> list[str]:
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
        if claim["domain"] != evidence["domain"]:
            raise ValueError("evidence domain does not match claim domain")
        self.conn.execute(
            "INSERT OR REPLACE INTO temporal_claim_evidence(claim_id,evidence_id,relation,note,created_at) VALUES(?,?,?,?,?)",
            (claim_id, evidence_id, relation, note, _now()),
        )
        self.conn.commit()
        affected=[]
        if relation in {"weakens", "contradicts", "supersedes"}:
            affected=self._mark_claim_warrants_review(claim_id, f"new evidence {relation} supporting claim")
        return affected

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        row=self.conn.execute("SELECT * FROM temporal_evidence WHERE id=?", (evidence_id,)).fetchone()
        if not row:raise KeyError(evidence_id)
        return dict(row)

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
                prior = conn.execute("SELECT id,status FROM temporal_warrants WHERE id=?", (supersedes_warrant_id,)).fetchone()
                if not prior:
                    raise KeyError(supersedes_warrant_id)
                if prior["status"] in {"active", "review_required"}:
                    at = _now()
                    conn.execute(
                        "UPDATE temporal_warrants SET status='superseded',updated_at=? WHERE id=?",
                        (at, supersedes_warrant_id),
                    )
                    conn.execute(
                        "INSERT INTO temporal_warrant_events(id,warrant_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?,?)",
                        (uuid.uuid4().hex[:20], supersedes_warrant_id, prior["status"], "superseded", "superseded by new warrant", at),
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
            conn.execute(
                "INSERT INTO temporal_warrant_events(id,warrant_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex[:20], warrant_id, "", "active", "warrant issued", _now()),
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
            self._transition_warrant(warrant_id, "expired", "warrant expired")
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
        for claim_id in _load(warrant["claim_ids_json"], []):
            claim = self._refresh_claim(claim_id, now_iso)
            if claim["status"] not in {"current", "historical"}:
                self._transition_warrant(warrant_id, "review_required", f"supporting claim {claim_id} is no longer current")
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

    def authorization_still_current(
        self,
        warrant_id: str,
        *,
        expected_updated_at: str,
        action_type: str,
        domain: str,
        scope: list[str],
        now_iso: str | None = None,
    ) -> bool:
        warrant = self.get_warrant(warrant_id, now_iso=now_iso)
        if warrant["updated_at"] != expected_updated_at:
            return False
        return self.warrant_authorizes(
            warrant_id, action_type=action_type, domain=domain, scope=scope, now_iso=now_iso
        )

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
            if provenance.get("authority_revision") == authority_revision:
                # A terminal warrant is a receipt, not permission to mint the same authority again.
                # A new authority revision must create a new action/warrant cycle.
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

    def warrant_ids_for_claim(self, claim_id: str, *, statuses: set[str] | None = None) -> list[str]:
        rows=self.conn.execute("SELECT id,claim_ids_json,status FROM temporal_warrants ORDER BY created_at,id").fetchall()
        out=[]
        for row in rows:
            if claim_id in _load(row["claim_ids_json"], []) and (statuses is None or row["status"] in statuses):
                out.append(row["id"])
        return out

    def action_ids_for_warrants(self, warrant_ids: list[str]) -> list[str]:
        if not warrant_ids:return []
        placeholders=",".join("?" for _ in warrant_ids)
        rows=self.conn.execute(
            f"SELECT DISTINCT action_id FROM temporal_action_warrants WHERE warrant_id IN ({placeholders}) ORDER BY action_id",
            warrant_ids,
        ).fetchall()
        return [str(row["action_id"]) for row in rows]

    def action_ids_for_claim(self, claim_id: str, *, statuses: set[str] | None = None) -> list[str]:
        return self.action_ids_for_warrants(self.warrant_ids_for_claim(claim_id,statuses=statuses))

    def _mark_claim_warrants_review(self, claim_id: str, reason: str) -> list[str]:
        affected=[]
        for row in self.conn.execute(
            "SELECT id,claim_ids_json,status FROM temporal_warrants WHERE status='active'"
        ).fetchall():
            if claim_id in _load(row["claim_ids_json"], []):
                self._transition_warrant(row["id"], "review_required", reason)
                affected.append(str(row["id"]))
        return affected

    def _open_dynamic_terminal_reentries(self, claim_id: str, evidence_id: str, relation: str) -> list[str]:
        claim=self.get_claim(claim_id)
        if claim["subject_mode"]!="dynamic" or relation not in {"weakens","contradicts","supersedes"}:
            return []
        terminal={"completed","released","superseded"}
        opened=[]
        for warrant_id in self.warrant_ids_for_claim(claim_id,statuses=terminal):
            exists=self.conn.execute(
                "SELECT id FROM temporal_evaluations WHERE prior_warrant_id=? AND trigger_evidence_id=? AND status='open'",
                (warrant_id,evidence_id),
            ).fetchone()
            if exists:
                opened.append(str(exists["id"]));continue
            opened.append(self.open_reentry(
                subject=claim["subject"],domain=claim["domain"],
                reason=f"dynamic subject received material evidence: {relation}",
                prior_warrant_id=warrant_id,trigger_evidence_id=evidence_id,
            ))
        return opened

    def ingest_evidence(
        self,
        *,
        subject: str,
        domain: str,
        source: str,
        payload: Any,
        links: list[dict[str, str]] | None = None,
        observed_at: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence_id=self.record_evidence(
            subject=subject,domain=domain,source=source,payload=payload,
            observed_at=observed_at,provenance=provenance,
        )
        review_warrants=[]
        reentries=[]
        for link in links or []:
            claim_id=str(link.get("claim_id") or "")
            relation=str(link.get("relation") or "")
            note=str(link.get("note") or "")
            if not claim_id or not relation:
                raise ValueError("evidence links require claim_id and relation")
            review_warrants.extend(self.link_evidence(claim_id,evidence_id,relation,note))
            reentries.extend(self._open_dynamic_terminal_reentries(claim_id,evidence_id,relation))
        review_warrants=list(dict.fromkeys(review_warrants))
        reentries=list(dict.fromkeys(reentries))
        return {
            "evidence_id":evidence_id,
            "review_warrant_ids":review_warrants,
            "review_action_ids":self.action_ids_for_warrants(review_warrants),
            "reentry_ids":reentries,
        }

    def attach_claims_to_action_warrant(
        self,
        action_id: str,
        claim_ids: list[str],
        *,
        claim_bridge: str = "",
        basis: str = "operator-bound current evidence",
        issued_by: str = "stillpoint-operator",
    ) -> str:
        action=self.conn.execute("SELECT * FROM action_requests WHERE id=?", (action_id,)).fetchone()
        if not action:raise KeyError(action_id)
        if action["status"] in {"completed","stale","failed"}:
            raise ValueError(f"cannot rebind terminal action status={action['status']}")
        side_effect=self.conn.execute(
            "SELECT adapter FROM action_results WHERE action_id=? AND adapter<>'' AND adapter<>'null' AND adapter NOT LIKE 'dry_run%' LIMIT 1",
            (action_id,),
        ).fetchone()
        if side_effect:
            raise ValueError("cannot change factual warrant after a real adapter dispatch")
        bindings=self.list_action_warrants(action_id)
        if not bindings:raise ValueError("action has no existing temporal warrant")
        prior=bindings[-1]
        if prior["status"] not in {"active","review_required"}:
            raise ValueError(f"existing temporal warrant is not replaceable: {prior['status']}")
        provenance=_load(prior.get("provenance_json"),{})
        provenance["claim_binding"]="explicit"
        new_id=self.issue_warrant(
            subject=prior["subject"],
            domain=prior["domain"],
            authorized_actions=_load(prior["authorized_actions_json"],[]),
            scope=_load(prior["scope_json"],[]),
            basis_type="manual_review",
            basis=basis,
            issued_by=issued_by,
            claim_ids=list(dict.fromkeys(claim_ids)),
            claim_bridge=claim_bridge,
            issued_at=_now(),
            effective_from=_now(),
            expires_at=prior.get("expires_at"),
            completion_condition=prior.get("completion_condition") or "",
            provenance=provenance,
            supersedes_warrant_id=prior["id"],
        )
        self.bind_action_warrant(action_id,new_id)
        return new_id

    def mark_action_warrants_review_required(self, action_id: str, *, reason: str) -> None:
        for warrant in self.list_action_warrants(action_id):
            if warrant["status"] == "active":
                self._transition_warrant(warrant["id"], "review_required", reason)

    def revoke_warrant(self, warrant_id: str, reason: str = "") -> None:
        self._end_warrant(warrant_id, "revoked", reason)

    def complete_warrant(self, warrant_id: str) -> None:
        self._end_warrant(warrant_id, "completed", "")

    def complete_action_warrant(self, action_id: str) -> None:
        for warrant in self.list_action_warrants(action_id):
            if warrant["status"] == "active":
                self.complete_warrant(warrant["id"])

    def _transition_warrant(self, warrant_id: str, status: str, reason: str = "") -> None:
        if status not in WARRANT_STATUSES:
            raise ValueError(status)
        row = self.conn.execute("SELECT status FROM temporal_warrants WHERE id=?", (warrant_id,)).fetchone()
        if not row:
            raise KeyError(warrant_id)
        prior = row["status"]
        if prior == status:
            return
        at = _now()
        self.conn.execute(
            "UPDATE temporal_warrants SET status=?,review_reason=?,updated_at=? WHERE id=?",
            (status, reason, at, warrant_id),
        )
        self.conn.execute(
            "INSERT INTO temporal_warrant_events(id,warrant_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?,?)",
            (uuid.uuid4().hex[:20], warrant_id, prior, status, reason, at),
        )
        self.conn.commit()

    def list_warrant_events(self, warrant_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM temporal_warrant_events WHERE warrant_id=? ORDER BY created_at,id", (warrant_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def _end_warrant(self, warrant_id: str, status: str, reason: str) -> None:
        if status not in {"revoked", "completed", "superseded"}:
            raise ValueError(status)
        warrant = self.get_warrant(warrant_id)
        if warrant["status"] not in {"active", "review_required"}:
            return
        self._transition_warrant(warrant_id, status, reason)

    def release_warrant(self, warrant_id: str, reason: str = "") -> None:
        warrant = self.get_warrant(warrant_id)
        if warrant["status"] in {"active", "review_required"}:
            raise ValueError("active authority must complete, expire, revoke, or be superseded before release")
        if warrant["status"] == "released":
            return
        self._transition_warrant(warrant_id, "released", reason)

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
