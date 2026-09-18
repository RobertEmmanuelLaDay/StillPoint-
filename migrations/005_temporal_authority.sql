CREATE TABLE IF NOT EXISTS temporal_claims (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value_json TEXT NOT NULL,
    domain TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    asserted_at TEXT NOT NULL,
    effective_from TEXT,
    effective_until TEXT,
    confidence REAL,
    truth_state TEXT NOT NULL,
    claim_kind TEXT NOT NULL,
    subject_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    supersedes_claim_id TEXT,
    expires_at TEXT,
    review_conditions_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(supersedes_claim_id) REFERENCES temporal_claims(id)
);

CREATE TABLE IF NOT EXISTS temporal_evidence (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    domain TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS temporal_claim_evidence (
    claim_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(claim_id,evidence_id),
    FOREIGN KEY(claim_id) REFERENCES temporal_claims(id),
    FOREIGN KEY(evidence_id) REFERENCES temporal_evidence(id)
);

CREATE TABLE IF NOT EXISTS temporal_warrants (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    domain TEXT NOT NULL,
    authorized_actions_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    basis_type TEXT NOT NULL,
    basis TEXT NOT NULL,
    issued_by TEXT NOT NULL,
    claim_ids_json TEXT NOT NULL,
    claim_bridge TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    expires_at TEXT,
    completion_condition TEXT NOT NULL,
    status TEXT NOT NULL,
    supersedes_warrant_id TEXT,
    review_reason TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(supersedes_warrant_id) REFERENCES temporal_warrants(id)
);

CREATE TABLE IF NOT EXISTS temporal_action_warrants (
    action_id TEXT NOT NULL,
    warrant_id TEXT NOT NULL,
    bound_at TEXT NOT NULL,
    PRIMARY KEY(action_id,warrant_id),
    FOREIGN KEY(action_id) REFERENCES action_requests(id),
    FOREIGN KEY(warrant_id) REFERENCES temporal_warrants(id)
);

CREATE TABLE IF NOT EXISTS temporal_evaluations (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    domain TEXT NOT NULL,
    reason TEXT NOT NULL,
    trigger_evidence_id TEXT,
    prior_warrant_id TEXT,
    status TEXT NOT NULL,
    disposition TEXT NOT NULL,
    rationale TEXT NOT NULL,
    new_warrant_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(trigger_evidence_id) REFERENCES temporal_evidence(id),
    FOREIGN KEY(prior_warrant_id) REFERENCES temporal_warrants(id)
);

CREATE INDEX IF NOT EXISTS ix_temporal_claims_subject_domain
ON temporal_claims(subject,domain,status);

CREATE INDEX IF NOT EXISTS ix_temporal_evidence_subject_domain
ON temporal_evidence(subject,domain,observed_at);

CREATE INDEX IF NOT EXISTS ix_temporal_warrants_subject_domain
ON temporal_warrants(subject,domain,status);

CREATE INDEX IF NOT EXISTS ix_temporal_action_warrants_action
ON temporal_action_warrants(action_id,bound_at);
