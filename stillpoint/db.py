from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


_MIGRATION_RE = re.compile(r"^(\d{3})_.*\.sql$")
TASK_UPDATE_COLUMNS = frozenset(
    {
        "updated_at",
        "goal",
        "project",
        "status",
        "plan_json",
        "final_output",
        "review_output",
        "approval_reason",
        "error",
        "input_fingerprint",
    }
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_migrations_dir() -> Path:
    """Return the canonical migration directory for a checkout or installed package.

    In a source checkout the top-level ``migrations`` directory is authoritative.
    Packaged releases include a verified mirror under ``stillpoint/migrations``.
    """

    checkout = Path(__file__).resolve().parents[1] / "migrations"
    if checkout.is_dir():
        return checkout
    packaged = Path(__file__).resolve().parent / "migrations"
    if packaged.is_dir():
        return packaged
    return checkout


MIGRATIONS_DIR = _default_migrations_dir()


def _migration_files(directory: Path | None = None) -> list[tuple[int, Path]]:
    root = Path(directory or MIGRATIONS_DIR)
    items: list[tuple[int, Path]] = []
    for path in root.glob("*.sql"):
        match = _MIGRATION_RE.match(path.name)
        if match:
            items.append((int(match.group(1)), path))
    items.sort(key=lambda item: item[0])
    return items


def _sql_statements(script: str) -> Iterable[str]:
    """Yield complete SQL statements without giving ``executescript`` transaction control."""

    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            pending = ""
            if statement:
                yield statement
    if pending.strip():
        raise RuntimeError("migration contains incomplete SQL")


class CompanyDB:
    def __init__(self, path: Path, *, migrations_dir: Path | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrations_dir = Path(migrations_dir or MIGRATIONS_DIR)
        self.conn: sqlite3.Connection | None = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._closed = False
        self._migrate()

    def _connection(self) -> sqlite3.Connection:
        if self._closed or self.conn is None:
            raise RuntimeError("database is closed")
        return self.conn

    def _migrate(self) -> None:
        conn = self._connection()
        migrations = _migration_files(self.migrations_dir)
        if not migrations:
            raise RuntimeError(f"no migration files found in {self.migrations_dir}")
        versions = [version for version, _ in migrations]
        if versions != list(range(versions[0], versions[-1] + 1)) or versions[0] != 1:
            raise RuntimeError(f"migration versions must be contiguous from 1: {versions}")

        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        current = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] or 0
        latest = migrations[-1][0]
        if current > latest:
            raise RuntimeError(f"database schema version {current} is newer than runtime {latest}")

        for version, path in migrations:
            if version <= current:
                continue
            script = path.read_text(encoding="utf-8")
            try:
                conn.execute("BEGIN IMMEDIATE")
                for statement in _sql_statements(script):
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                    (version, utcnow()),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            current = version

    @property
    def schema_version(self) -> int:
        row = self._connection().execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)

    def close(self) -> None:
        if self._closed:
            return
        conn = self.conn
        self.conn = None
        self._closed = True
        if conn is not None:
            conn.close()

    def __enter__(self) -> "CompanyDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        # Best-effort cleanup only. Production code should close explicitly or use a context manager.
        try:
            self.close()
        except Exception:
            pass

    def create_task(self, goal: str, project: str | None = None) -> str:
        task_id = uuid.uuid4().hex[:12]
        now = utcnow()
        conn = self._connection()
        conn.execute(
            "INSERT INTO tasks(id,created_at,updated_at,goal,project,status) VALUES(?,?,?,?,?,?)",
            (task_id, now, now, goal, project, "new"),
        )
        conn.commit()
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        bad = [key for key in fields if key not in TASK_UPDATE_COLUMNS]
        if bad:
            raise ValueError(f"disallowed task columns: {bad}")
        fields["updated_at"] = utcnow()
        cols = ", ".join(f"{key}=?" for key in fields)
        conn = self._connection()
        conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", [*fields.values(), task_id])
        conn.commit()

    def set_plan(self, task_id: str, plan: dict[str, Any]) -> None:
        self.update_task(task_id, plan_json=json.dumps(plan, ensure_ascii=False), status="running")

    def add_plan_revision(
        self,
        task_id: str,
        instruction_fingerprint: str,
        authority_revision: str,
        plan: dict[str, Any],
    ) -> str:
        revision_id = uuid.uuid4().hex[:12]
        conn = self._connection()
        conn.execute(
            "INSERT INTO plan_revisions(id,task_id,created_at,instruction_fingerprint,authority_revision,plan_json) "
            "VALUES(?,?,?,?,?,?)",
            (
                revision_id,
                task_id,
                utcnow(),
                instruction_fingerprint,
                authority_revision,
                json.dumps(plan, ensure_ascii=False),
            ),
        )
        conn.commit()
        return revision_id

    def list_plan_revisions(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM plan_revisions WHERE task_id=? ORDER BY created_at,id", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def add_resume_instruction(
        self,
        task_id: str,
        instruction: str,
        instruction_fingerprint: str,
        authority_revision: str,
        plan_revision_id: str,
    ) -> str:
        instruction_id = uuid.uuid4().hex[:12]
        conn = self._connection()
        conn.execute(
            "INSERT INTO resume_instructions(id,task_id,created_at,instruction,instruction_fingerprint,authority_revision,plan_revision_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                instruction_id,
                task_id,
                utcnow(),
                instruction,
                instruction_fingerprint,
                authority_revision,
                plan_revision_id,
            ),
        )
        conn.commit()
        return instruction_id

    def list_resume_instructions(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM resume_instructions WHERE task_id=? ORDER BY created_at,id", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

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
        conn = self._connection()
        try:
            conn.execute(
                """INSERT INTO agent_runs
                (id,task_id,created_at,agent_id,phase,model,input_summary,output,citations_json,
                 provider_response_id,usage_json,stage_key)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    task_id,
                    utcnow(),
                    agent_id,
                    phase,
                    model,
                    input_summary,
                    output,
                    json.dumps(citations or [], ensure_ascii=False),
                    provider_response_id,
                    json.dumps(usage or {}, ensure_ascii=False),
                    stage_key,
                ),
            )
        except sqlite3.IntegrityError as exc:
            if stage_key and "agent_runs.stage_key" in str(exc):
                row = conn.execute("SELECT id FROM agent_runs WHERE stage_key=?", (stage_key,)).fetchone()
                if row:
                    return str(row[0])
            raise
        conn.commit()
        return run_id

    def get_run_by_stage_key(self, key: str) -> dict[str, Any] | None:
        row = self._connection().execute("SELECT * FROM agent_runs WHERE stage_key=?", (key,)).fetchone()
        return dict(row) if row else None

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self._connection().execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def list_runs(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM agent_runs WHERE task_id=? ORDER BY created_at,id", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def add_approval(self, task_id: str, decision: str, note: str = "") -> str:
        approval_id = uuid.uuid4().hex[:12]
        conn = self._connection()
        conn.execute(
            "INSERT INTO approvals(id,task_id,created_at,decision,note) VALUES(?,?,?,?,?)",
            (approval_id, task_id, utcnow(), decision, note),
        )
        conn.commit()
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
        version: int | None = None,
        supersedes: str | None = None,
        body_path: str | None = None,
        action_id: str | None = None,
    ) -> str:
        conn = self._connection()
        prior = conn.execute(
            "SELECT id,version FROM artifacts WHERE task_id=? AND kind=? "
            "ORDER BY version DESC,created_at DESC LIMIT 1",
            (task_id, kind),
        ).fetchone()
        if version is None:
            version = int(prior["version"] + 1) if prior else 1
        if supersedes is None and prior:
            supersedes = str(prior["id"])
        artifact_id = uuid.uuid4().hex[:12]
        conn.execute(
            """INSERT INTO artifacts
            (id,task_id,project,kind,name,sha256,produced_by_run_id,phase,version,supersedes,body_path,action_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                artifact_id,
                task_id,
                project,
                kind,
                name,
                sha256,
                produced_by_run_id,
                phase,
                version,
                supersedes,
                body_path,
                action_id,
                utcnow(),
            ),
        )
        conn.commit()
        return artifact_id

    def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at,id", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def add_task_file(
        self,
        task_id: str,
        path: str,
        name: str,
        sha256: str,
        original_name: str | None = None,
        media_type: str | None = None,
        size_bytes: int | None = None,
    ) -> str:
        file_id = uuid.uuid4().hex[:12]
        conn = self._connection()
        conn.execute(
            "INSERT INTO task_files(id,task_id,path,name,sha256,created_at,original_name,media_type,size_bytes) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                file_id,
                task_id,
                path,
                name,
                sha256,
                utcnow(),
                original_name or name,
                media_type,
                size_bytes,
            ),
        )
        conn.commit()
        return file_id

    def list_task_files(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM task_files WHERE task_id=? ORDER BY created_at,id", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def set_memory(
        self,
        key: str,
        value: str,
        scope: str = "company",
        source: str = "CEO",
        confidence: str = "verified",
        task_id: str | None = None,
    ) -> None:
        conn = self._connection()
        conn.execute(
            """INSERT INTO memory(scope,key,value,source,updated_at,confidence,task_id)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(scope,key) DO UPDATE SET
              value=excluded.value,
              source=excluded.source,
              updated_at=excluded.updated_at,
              confidence=excluded.confidence,
              task_id=excluded.task_id""",
            (scope, key, value, source, utcnow(), confidence, task_id),
        )
        conn.commit()

    def get_memory(self, scopes: list[str] | None = None) -> list[dict[str, Any]]:
        conn = self._connection()
        if scopes:
            placeholders = ",".join("?" for _ in scopes)
            rows = conn.execute(
                f"SELECT * FROM memory WHERE scope IN ({placeholders}) ORDER BY scope,key", scopes
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM memory ORDER BY scope,key").fetchall()
        return [dict(row) for row in rows]

    def add_action_request(self, request) -> str:
        conn = self._connection()
        now = utcnow()
        conn.execute(
            """INSERT INTO action_requests
            (id,task_id,created_at,updated_at,action_type,target,scope_json,artifact_refs_json,
             approval_required,approval_id,expires_at,issued_at,idempotency_key,success_criteria_json,
             click_irreversible,authority_revision,status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                request.action_id,
                request.task_id,
                now,
                now,
                request.action_type,
                request.target,
                json.dumps(request.scope, ensure_ascii=False),
                json.dumps([asdict(item) for item in request.artifact_refs], ensure_ascii=False),
                1 if request.approval_required else 0,
                request.approval_id,
                request.expires_at,
                request.issued_at,
                request.idempotency_key,
                json.dumps(request.success_criteria, ensure_ascii=False),
                1 if request.click_irreversible else 0,
                request.authority_revision,
                "waiting_approval" if request.approval_required else "ready_for_action",
            ),
        )
        conn.commit()
        return request.action_id

    def get_action_request(self, action_id: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM action_requests WHERE id=?", (action_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_action_request_by_idempotency(self, key: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM action_requests WHERE idempotency_key=?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def list_action_requests(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM action_requests WHERE task_id=? ORDER BY created_at,id", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def update_action_request_status(self, action_id: str, status: str) -> None:
        conn = self._connection()
        conn.execute(
            "UPDATE action_requests SET status=?,updated_at=? WHERE id=?",
            (status, utcnow(), action_id),
        )
        conn.commit()

    def reset_action_for_reapproval(self, action_id: str, *, status: str = "waiting_approval") -> None:
        conn=self._connection()
        if not conn.execute("SELECT 1 FROM action_requests WHERE id=?", (action_id,)).fetchone():
            raise KeyError(action_id)
        conn.execute(
            "UPDATE action_requests SET approval_id=NULL,status=?,updated_at=? WHERE id=?",
            (status,utcnow(),action_id),
        )
        conn.commit()

    def mark_action_stale(self, action_id: str, reason: str = "stale authorization") -> None:
        # The schema intentionally stores status, not free-form stale reasons. The caller's
        # exception/event supplies the human-readable reason while persistence stays normalized.
        del reason
        self.update_action_request_status(action_id, "stale")

    def bind_action_approval(self, action_id: str, approval_id: str) -> None:
        conn = self._connection()
        row = conn.execute(
            "SELECT task_id,artifact_refs_json FROM action_requests WHERE id=?", (action_id,)
        ).fetchone()
        if not row:
            raise KeyError(action_id)
        approval = conn.execute(
            "SELECT task_id,decision FROM approvals WHERE id=?", (approval_id,)
        ).fetchone()
        if not approval:
            raise KeyError(approval_id)
        if approval["task_id"] != row["task_id"]:
            raise ValueError("approval belongs to a different task")
        if approval["decision"] != "approved":
            raise ValueError("approval record is not approved")
        refs = json.loads(row["artifact_refs_json"])
        hashes = [item.get("sha256") for item in refs]
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO action_approvals(action_id,approval_id,bound_at,artifact_hashes_json) VALUES(?,?,?,?)",
                (action_id, approval_id, utcnow(), json.dumps(hashes, ensure_ascii=False)),
            )
            conn.execute(
                "UPDATE action_requests SET approval_id=?,status='ready_for_action',updated_at=? WHERE id=?",
                (approval_id, utcnow(), action_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def has_action_approval(self, action_id: str, approval_id: str | None) -> bool:
        if not approval_id:
            return False
        row = self._connection().execute(
            "SELECT 1 FROM action_approvals WHERE action_id=? AND approval_id=?",
            (action_id, approval_id),
        ).fetchone()
        return bool(row)

    def add_action_result(self, result) -> str:
        result_id = uuid.uuid4().hex[:12]
        conn = self._connection()
        conn.execute(
            "INSERT INTO action_results(id,action_id,created_at,status,evidence_json,external_id,error,adapter) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                result_id,
                result.action_id,
                utcnow(),
                result.status,
                json.dumps([asdict(item) for item in result.evidence], ensure_ascii=False),
                result.external_id,
                result.error,
                result.adapter,
            ),
        )
        conn.commit()
        return result_id

    def list_action_results(self, action_id: str) -> list[dict[str, Any]]:
        rows = self._connection().execute(
            "SELECT * FROM action_results WHERE action_id=? ORDER BY created_at,id", (action_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def set_task_budget(self, task_id: str, limits) -> None:
        raw = limits.to_dict() if hasattr(limits, "to_dict") else dict(limits or {})
        conn = self._connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """INSERT INTO task_budgets
                (task_id,max_model_calls,max_tool_calls,max_total_tokens,max_elapsed_seconds,max_cost_usd,created_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET
                  max_model_calls=excluded.max_model_calls,
                  max_tool_calls=excluded.max_tool_calls,
                  max_total_tokens=excluded.max_total_tokens,
                  max_elapsed_seconds=excluded.max_elapsed_seconds,
                  max_cost_usd=excluded.max_cost_usd""",
                (
                    task_id,
                    raw.get("max_model_calls"),
                    raw.get("max_tool_calls"),
                    raw.get("max_total_tokens"),
                    raw.get("max_elapsed_seconds"),
                    raw.get("max_cost_usd"),
                    utcnow(),
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO task_usage(task_id,model_calls,tool_calls,total_tokens,cost_usd,updated_at) "
                "VALUES(?,0,0,0,0,?)",
                (task_id, utcnow()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def get_task_budget(self, task_id: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM task_budgets WHERE task_id=?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_task_usage(self, task_id: str) -> dict[str, Any]:
        row = self._connection().execute(
            "SELECT * FROM task_usage WHERE task_id=?", (task_id,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "task_id": task_id,
            "model_calls": 0,
            "tool_calls": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "updated_at": None,
        }

    def add_task_usage(
        self,
        task_id: str,
        *,
        model_calls: int = 0,
        tool_calls: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> dict[str, Any]:
        conn = self._connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR IGNORE INTO task_usage(task_id,model_calls,tool_calls,total_tokens,cost_usd,updated_at) "
                "VALUES(?,0,0,0,0,?)",
                (task_id, utcnow()),
            )
            conn.execute(
                """UPDATE task_usage SET
                model_calls=model_calls+?, tool_calls=tool_calls+?, total_tokens=total_tokens+?,
                cost_usd=cost_usd+?, updated_at=? WHERE task_id=?""",
                (
                    int(model_calls),
                    int(tool_calls),
                    int(total_tokens),
                    float(cost_usd),
                    utcnow(),
                    task_id,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return self.get_task_usage(task_id)
