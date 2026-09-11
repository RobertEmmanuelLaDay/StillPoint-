from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .budgets import BudgetLimits
from .db import CompanyDB
from .providers import make_provider
from .registry import AgentRegistry
from .runtime import CompanyRuntime


def _root() -> Path:
    return Path(os.getenv("STILLPOINT_ROOT") or Path.cwd()).resolve()


def _runtime(root: Path, provider_name: str = "mock") -> CompanyRuntime:
    provider = make_provider(provider_name)
    default_model = os.getenv("STILLPOINT_MODEL") or getattr(provider, "default_model", None) or "default"
    config_path = root / "config" / "agents.json"
    if not config_path.is_file():
        config_path = Path(__file__).resolve().parent / "defaults" / "agents.json"
    return CompanyRuntime(
        root=root,
        db=CompanyDB(root / "state" / "company.sqlite"),
        registry=AgentRegistry(config_path),
        provider=provider,
        default_model=default_model,
        smart_routing=os.getenv("STILLPOINT_SMART_ROUTING", "0") == "1",
        allowed_import_roots=[root],
    )


def _json(value):
    print(json.dumps(value, indent=2, default=str, ensure_ascii=False))


def cmd_status(rt: CompanyRuntime) -> None:
    rows=rt.db.list_tasks(50)
    buckets={}
    for row in rows:buckets.setdefault(row["status"],[]).append(row)
    for title,statuses in [
        ("ACTIVE",["new","running"]),
        ("NEEDS CEO APPROVAL",["waiting_approval"]),
        ("READY FOR ACTION",["ready_for_action"]),
        ("BLOCKED / FAILED",["blocked","failed"]),
        ("RECENTLY COMPLETED",["completed"]),
        ("REJECTED",["rejected"]),
    ]:
        print(title)
        found=[]
        for status in statuses:found.extend(buckets.get(status,[]))
        if not found:print("  -")
        for row in found[:12]:print(f"  {row['id']}  {row['status']}  {row['goal'][:80]}")


def cmd_doctor(rt: CompanyRuntime, root: Path) -> int:
    checks={}
    try: checks["database"]={"ok":True,"schema_version":rt.db.schema_version}
    except Exception as exc: checks["database"]={"ok":False,"error":str(exc)}
    try: checks["agent_registry"]={"ok":True,"agents":rt.registry.ids()}
    except Exception as exc: checks["agent_registry"]={"ok":False,"error":str(exc)}
    managed=rt.managed_files
    try: managed.mkdir(parents=True,exist_ok=True);checks["managed_storage"]={"ok":os.access(managed,os.W_OK),"path":str(managed)}
    except Exception as exc: checks["managed_storage"]={"ok":False,"error":str(exc)}
    corpus_manifest = root / "eval" / "corpus_hashes.json"
    if corpus_manifest.is_file():
        try:
            import hashlib
            hashes=json.loads(corpus_manifest.read_text())
            actual={}
            ok=True
            for name,expected in hashes.items():
                got=hashlib.sha256((root/"eval"/name).read_bytes()).hexdigest();actual[name]=got;ok &= got==expected
            checks["corpus_integrity"]={"ok":bool(ok),"available":True,"hashes":actual}
        except Exception as exc:
            checks["corpus_integrity"]={"ok":False,"available":True,"error":str(exc)}
    else:
        # Evaluator corpora are release-development assets, not runtime state.
        # A wheel installation remains healthy without them; source checkouts
        # verify the immutable corpus whenever the manifest is present.
        checks["corpus_integrity"]={"ok":True,"available":False,"note":"evaluator assets not installed"}
    provider=os.getenv("STILLPOINT_PROVIDER","mock")
    checks["provider"]={"ok":provider=="mock" or bool(os.getenv("XAI_API_KEY")),"name":provider,"live_credentials_present":bool(os.getenv("XAI_API_KEY")) if provider=="xai" else None}
    checks["overall_ok"]=all(v.get("ok",False) for k,v in checks.items() if isinstance(v,dict))
    _json(checks)
    return 0 if checks["overall_ok"] else 1


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(prog="stillpoint")
    parser.add_argument("--provider",default=os.getenv("STILLPOINT_PROVIDER","mock"))
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("status")
    submit=sub.add_parser("submit");submit.add_argument("goal");submit.add_argument("--project");submit.add_argument("--file",action="append",default=[]);submit.add_argument("--max-model-calls",type=int);submit.add_argument("--max-tool-calls",type=int);submit.add_argument("--max-tokens",type=int)
    approve=sub.add_parser("approve");approve.add_argument("task_id");approve.add_argument("--note",default="")
    reject=sub.add_parser("reject");reject.add_argument("task_id");reject.add_argument("--note",default="")
    resume=sub.add_parser("resume");resume.add_argument("task_id");resume.add_argument("--note",default="")
    task=sub.add_parser("task");task.add_argument("task_id")
    actions=sub.add_parser("actions");actions.add_argument("task_id",nargs="?")
    artifacts=sub.add_parser("artifacts");artifacts.add_argument("task_id")
    sub.add_parser("approvals")
    sub.add_parser("doctor")
    args=parser.parse_args(argv)
    root=_root();rt=_runtime(root,args.provider)
    try:
        if args.cmd=="status":cmd_status(rt)
        elif args.cmd=="submit":
            budget=None
            if any(v is not None for v in (args.max_model_calls,args.max_tool_calls,args.max_tokens)):
                budget=BudgetLimits(max_model_calls=args.max_model_calls,max_tool_calls=args.max_tool_calls,max_total_tokens=args.max_tokens)
            out=rt.submit(args.goal,project=args.project,files=args.file or None,budget=budget);_json({"task_id":out.task_id,"status":out.status.value,"primary":out.plan.primary,"restricted_actions":out.plan.restricted_actions})
        elif args.cmd=="approve":_json(rt.approve(args.task_id,args.note))
        elif args.cmd=="reject":_json(rt.reject(args.task_id,args.note))
        elif args.cmd=="resume":
            out=rt.resume(args.task_id,args.note);_json({"task_id":out.task_id,"status":out.status.value,"primary":out.plan.primary})
        elif args.cmd=="task":
            task=rt.db.get_task(args.task_id)
            if not task:raise KeyError(args.task_id)
            task["runs"]=rt.db.list_runs(args.task_id);task["artifacts"]=rt.db.list_artifacts(args.task_id);task["actions"]=rt.db.list_action_requests(args.task_id);task["usage"]=rt.db.get_task_usage(args.task_id);_json(task)
        elif args.cmd=="actions":
            rows=[]
            tasks=[rt.db.get_task(args.task_id)] if args.task_id else rt.db.list_tasks(100)
            for t in tasks:
                if t: rows.extend(rt.db.list_action_requests(t["id"]))
            _json(rows)
        elif args.cmd=="artifacts":_json(rt.db.list_artifacts(args.task_id))
        elif args.cmd=="approvals":_json([t for t in rt.db.list_tasks(100) if t["status"]=="waiting_approval"])
        elif args.cmd=="doctor":return cmd_doctor(rt,root)
        return 0
    finally:rt.db.close()


if __name__=="__main__":raise SystemExit(main())
