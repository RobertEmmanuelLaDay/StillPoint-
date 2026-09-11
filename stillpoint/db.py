from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
TASK_UPDATE_COLUMNS = frozenset({
    "updated_at", "goal", "project", "status", "plan_json", "final_output",
    "review_output", "approval_reason", "error", "input_fingerprint",
})
RUN_COLUMNS_OK = True


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class CompanyDB:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                goal TEXT NOT NULL,
                project TEXT,
                status TEXT NOT NULL,
                plan_json TEXT,
                final_output TEXT,
                review_output TEXT,
                approval_reason TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                model TEXT,
                input_summary TEXT,
                output TEXT NOT NULL,
                citations_json TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS memory (
                scope TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(scope, key)
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                task_id TEXT,
                decision TEXT NOT NULL,
                rationale TEXT,
                durable INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                decision TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS task_files (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            """
        )
        current = self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] or 0
        if current < 1:
            self.conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(1, ?)", (utcnow(),))
            current = 1
        if current < 2:
            for stmt in (
                "ALTER TABLE tasks ADD COLUMN input_fingerprint TEXT",
                "ALTER TABLE agent_runs ADD COLUMN provider_response_id TEXT",
                "ALTER TABLE agent_runs ADD COLUMN usage_json TEXT",
                "ALTER TABLE agent_runs ADD COLUMN stage_key TEXT",
                "ALTER TABLE memory ADD COLUMN confidence TEXT DEFAULT 'unverified'",
                "ALTER TABLE memory ADD COLUMN task_id TEXT",
                """CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    project TEXT,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    produced_by_run_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    supersedes TEXT,
                    body_path TEXT,
                    action_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                )""",
            ):
                try:
                    self.conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise
            self.conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(2, ?)", (utcnow(),))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def create_task(self, goal: str, project: str | None = None) -> str:
        task_id = uuid.uuid4().hex[:12]
        now = utcnow()
        self.conn.execute(
            "INSERT INTO tasks(id,created_at,updated_at,goal,project,status) VALUES(?,?,?,?,?,?)",
            (task_id, now, now, goal, project, "new"),
        )
        self.conn.commit()
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        bad = [k for k in fields if k not in TASK_UPDATE_COLUMNS]
        if bad:
            raise ValueError(f"disallowed task columns: {bad}")
        fields["updated_at"] = utcnow()
        cols = ", ".join(f"{key}=?" for key in fields)
        values = list(fields.values()) + [task_id]
        self.conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", values)
        self.conn.commit()

    def set_plan(self, task_id: str, plan: dict[str, Any]) -> None:
        self.update_task(task_id, plan_json=json.dumps(plan, ensure_ascii=False), status="running")

    def add_run(
        self,
        task_id: str,
        agent_id: str,
        phase: str,
        output: str,
        model: str = "",
        input_summary: str = "",
        citations: list[str] | None = None,
        provider_response_id: str = "",
        usage: dict | None = None,
        stage_key: str = "",
    ) -> str:
        run_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            """INSERT INTO agent_runs
            (id,task_id,created_at,agent_id,phase,model,input_summary,output,citations_json,
             provider_response_id,usage_json,stage_key)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, task_id, utcnow(), agent_id, phase, model, input_summary, output,
                json.dumps(citations or [], ensure_ascii=False),
                provider_response_id,
                json.dumps(usage or {}, ensure_ascii=False),
                stage_key,
            ),
        )
        self.conn.commit()
        return run_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def list_runs(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM agent_runs WHERE task_id=? ORDER BY created_at ASC", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def set_memory(self, key: str, value: str, scope: str = "company", source: str = "CEO") -> None:
        self.conn.execute(
            """INSERT INTO memory(scope,key,value,source,updated_at) VALUES(?,?,?,?,?)
            ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value,source=excluded.source,updated_at=excluded.updated_at""",
            (scope, key, value, source, utcnow()),
        )
        self.conn.commit()

    def get_memory(self, scopes: list[str] | None = None) -> list[dict[str, Any]]:
        if scopes:
            placeholders = ",".join("?" for _ in scopes)
            rows = self.conn.execute(
                f"SELECT * FROM memory WHERE scope IN ({placeholders}) ORDER BY scope,key", scopes
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM memory ORDER BY scope,key").fetchall()
        return [dict(r) for r in rows]

    def add_decision(self, decision: str, rationale: str = "", task_id: str | None = None, durable: bool = True) -> str:
        decision_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO decisions(id,created_at,task_id,decision,rationale,durable) VALUES(?,?,?,?,?,?)",
            (decision_id, utcnow(), task_id, decision, rationale, 1 if durable else 0),
        )
        self.conn.commit()
        return decision_id

    def add_task_file(self, task_id: str, path: str, name: str, sha256: str) -> str:
        file_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO task_files(id,task_id,path,name,sha256,created_at) VALUES(?,?,?,?,?,?)",
            (file_id, task_id, path, name, sha256, utcnow()),
        )
        self.conn.commit()
        return file_id

    def list_task_files(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM task_files WHERE task_id=? ORDER BY created_at ASC", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def add_approval(self, task_id: str, decision: str, note: str = "") -> str:
        approval_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO approvals(id,task_id,created_at,decision,note) VALUES(?,?,?,?,?)",
            (approval_id, task_id, utcnow(), decision, note),
        )
        self.conn.commit()
        return approval_id

    def add_artifact(
        self,
        *,
        task_id: str,
        kind: str,
        name: str,
        sha256: str,
        produced_by_run_id: str,
        phase: str,
        project: str | None = None,
        version: int = 1,
        supersedes: str | None = None,
        body_path: str | None = None,
        action_id: str | None = None,
    ) -> str:
        artifact_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            """INSERT INTO artifacts
            (id,task_id,project,kind,name,sha256,produced_by_run_id,phase,version,supersedes,body_path,action_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (artifact_id, task_id, project, kind, name, sha256, produced_by_run_id, phase,
             version, supersedes, body_path, action_id, utcnow()),
        )
        self.conn.commit()
        return artifact_id

    def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at ASC", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]
