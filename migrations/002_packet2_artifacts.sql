-- Packet 2 / current schema extras. CompanyDB._migrate version 2.
ALTER TABLE tasks ADD COLUMN input_fingerprint TEXT;
ALTER TABLE agent_runs ADD COLUMN provider_response_id TEXT;
ALTER TABLE agent_runs ADD COLUMN usage_json TEXT;
ALTER TABLE agent_runs ADD COLUMN stage_key TEXT;
ALTER TABLE memory ADD COLUMN confidence TEXT DEFAULT 'unverified';
ALTER TABLE memory ADD COLUMN task_id TEXT;
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, project TEXT, kind TEXT NOT NULL,
    name TEXT NOT NULL, sha256 TEXT NOT NULL, produced_by_run_id TEXT NOT NULL,
    phase TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, supersedes TEXT,
    body_path TEXT, action_id TEXT, created_at TEXT NOT NULL
);
