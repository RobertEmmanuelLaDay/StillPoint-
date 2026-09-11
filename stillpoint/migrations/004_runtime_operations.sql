ALTER TABLE task_files ADD COLUMN original_name TEXT;
ALTER TABLE task_files ADD COLUMN media_type TEXT;
ALTER TABLE task_files ADD COLUMN size_bytes INTEGER;

CREATE TABLE IF NOT EXISTS task_budgets (
    task_id TEXT PRIMARY KEY,
    max_model_calls INTEGER,
    max_tool_calls INTEGER,
    max_total_tokens INTEGER,
    max_elapsed_seconds REAL,
    max_cost_usd REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS task_usage (
    task_id TEXT PRIMARY KEY,
    model_calls INTEGER NOT NULL DEFAULT 0,
    tool_calls INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS ix_task_files_task_hash ON task_files(task_id, sha256);
