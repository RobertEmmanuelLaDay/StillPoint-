from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .db import CompanyDB
from .providers import make_provider
from .registry import AgentRegistry
from .runtime import CompanyRuntime


def _root() -> Path:
    env = os.getenv("STILLPOINT_ROOT")
    if env:
        return Path(env)
    return Path.cwd()


def _runtime(root: Path, provider_name: str = "mock") -> CompanyRuntime:
    db = CompanyDB(root / "state" / "company.sqlite")
    return CompanyRuntime(
        root=root,
        db=db,
        registry=AgentRegistry(root / "config" / "agents.json"),
        provider=make_provider(provider_name),
        default_model=os.getenv("STILLPOINT_MODEL", "grok-4.6"),
        smart_routing=os.getenv("STILLPOINT_SMART_ROUTING", "0") == "1",
    )


def cmd_status(rt: CompanyRuntime) -> None:
    rows = rt.db.list_tasks(50)
    if not rows:
        print("No tasks.")
        return
    buckets = {"running": [], "waiting_approval": [], "blocked": [], "failed": [], "ready_for_action": [], "completed": []}
    for row in rows:
        buckets.setdefault(row["status"], []).append(row)
    print("ACTIVE")
    for row in buckets.get("running", []):
        print(f"  {row['id']}  {row['goal'][:80]}")
    print("NEEDS CEO APPROVAL")
    for row in buckets.get("waiting_approval", []):
        print(f"  {row['id']}  {row.get('approval_reason') or ''}  {row['goal'][:60]}")
    print("READY FOR ACTION")
    for row in buckets.get("ready_for_action", []):
        print(f"  {row['id']}  {row['goal'][:80]}")
    print("BLOCKED / FAILED")
    for row in buckets.get("blocked", []) + buckets.get("failed", []):
        print(f"  {row['id']}  {row['status']}  {row.get('error') or ''}")
    print("RECENTLY COMPLETED")
    for row in buckets.get("completed", [])[:8]:
        print(f"  {row['id']}  {row['goal'][:80]}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="stillpoint")
    parser.add_argument("--provider", default=os.getenv("STILLPOINT_PROVIDER", "mock"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_sub = sub.add_parser("submit")
    p_sub.add_argument("goal")
    p_sub.add_argument("--project")
    p_sub.add_argument("--file", action="append", default=[])
    p_ap = sub.add_parser("approve")
    p_ap.add_argument("task_id")
    p_ap.add_argument("--note", default="")
    p_rj = sub.add_parser("reject")
    p_rj.add_argument("task_id")
    p_rs = sub.add_parser("resume")
    p_rs.add_argument("task_id")
    p_rs.add_argument("--note", default="")
    args = parser.parse_args(argv)
    root = _root()
    rt = _runtime(root, args.provider)
    try:
        if args.cmd == "status":
            cmd_status(rt)
        elif args.cmd == "submit":
            out = rt.submit(args.goal, project=args.project, files=args.file or None)
            print(json.dumps({"task_id": out.task_id, "status": out.status.value, "primary": out.plan.primary}, indent=2))
        elif args.cmd == "approve":
            print(json.dumps(rt.approve(args.task_id, args.note), indent=2, default=str))
        elif args.cmd == "reject":
            print(json.dumps(rt.reject(args.task_id, args.note), indent=2, default=str))
        elif args.cmd == "resume":
            out = rt.resume(args.task_id, args.note)
            print(json.dumps({"task_id": out.task_id, "status": out.status.value}, indent=2))
        return 0
    finally:
        rt.db.close()


if __name__ == "__main__":
    raise SystemExit(main())
