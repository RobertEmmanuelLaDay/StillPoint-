CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    goal TEXT NOT NULL, project TEXT, status TEXT NOT NULL, plan_json TEXT,
    final_output TEXT, review_output TEXT, approval_reason TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, created_at TEXT NOT NULL,
    agent_id TEXT NOT NULL, phase TEXT NOT NULL, model TEXT, input_summary TEXT,
    output TEXT NOT NULL, citations_json TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS memory (
    scope TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
    source TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(scope, key)
);
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, task_id TEXT,
    decision TEXT NOT NULL, rationale TEXT, durable INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, created_at TEXT NOT NULL,
    decision TEXT NOT NULL, note TEXT
);
CREATE TABLE IF NOT EXISTS task_files (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, path TEXT NOT NULL,
    name TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL
);
