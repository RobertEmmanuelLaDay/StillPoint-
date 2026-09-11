CREATE TABLE IF NOT EXISTS plan_revisions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    instruction_fingerprint TEXT NOT NULL,
    authority_revision TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS resume_instructions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    instruction TEXT NOT NULL,
    instruction_fingerprint TEXT NOT NULL,
    authority_revision TEXT NOT NULL,
    plan_revision_id TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(plan_revision_id) REFERENCES plan_revisions(id)
);
CREATE TABLE IF NOT EXISTS action_requests (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    artifact_refs_json TEXT NOT NULL,
    approval_required INTEGER NOT NULL,
    approval_id TEXT,
    expires_at TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    success_criteria_json TEXT NOT NULL,
    click_irreversible INTEGER NOT NULL DEFAULT 0,
    authority_revision TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS action_approvals (
    action_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    bound_at TEXT NOT NULL,
    artifact_hashes_json TEXT NOT NULL,
    PRIMARY KEY(action_id, approval_id),
    FOREIGN KEY(action_id) REFERENCES action_requests(id),
    FOREIGN KEY(approval_id) REFERENCES approvals(id)
);
CREATE TABLE IF NOT EXISTS action_results (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    external_id TEXT,
    error TEXT,
    adapter TEXT NOT NULL,
    FOREIGN KEY(action_id) REFERENCES action_requests(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_runs_stage_key
ON agent_runs(stage_key)
WHERE stage_key IS NOT NULL AND stage_key <> '';
CREATE INDEX IF NOT EXISTS ix_action_requests_task ON action_requests(task_id, status);
CREATE INDEX IF NOT EXISTS ix_action_results_action ON action_results(action_id, created_at);
