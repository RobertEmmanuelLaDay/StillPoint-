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

def _json_value(value):
    try:return json.loads(value)
    except json.JSONDecodeError as exc:raise argparse.ArgumentTypeError(f"invalid JSON: {exc}") from exc

def _link_value(value):
    parts=value.split(":",1)
    if len(parts)!=2 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError("link must be CLAIM_ID:RELATION")
    return {"claim_id":parts[0],"relation":parts[1]}


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
    try:
        required={"temporal_claims","temporal_evidence","temporal_warrants","temporal_warrant_events","temporal_evaluations"}
        found={row[0] for row in rt.db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing=sorted(required-found);checks["temporal_authority"]={"ok":not missing,"missing":missing}
    except Exception as exc:checks["temporal_authority"]={"ok":False,"error":str(exc)}
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
        source_checkout = (root / "pyproject.toml").is_file() or (root / ".git").exists()
        if source_checkout:
            checks["corpus_integrity"]={"ok":False,"available":False,"error":"frozen corpus manifest missing from source checkout"}
        else:
            # Evaluator corpora are release-development assets, not runtime state.
            # A runtime-only wheel installation remains healthy without them.
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
    temporal=sub.add_parser("temporal")
    ts=temporal.add_subparsers(dest="temporal_cmd",required=True)
    claims=ts.add_parser("claims");claims.add_argument("--subject");claims.add_argument("--domain")
    claim=ts.add_parser("claim");claim.add_argument("claim_id")
    ca=ts.add_parser("claim-add");ca.add_argument("subject");ca.add_argument("predicate");ca.add_argument("domain");ca.add_argument("source");ca.add_argument("value",type=_json_value);ca.add_argument("--truth-state",default="unknown");ca.add_argument("--kind",default="assertion");ca.add_argument("--subject-mode",default="unspecified");ca.add_argument("--confidence",type=float);ca.add_argument("--expires-at");ca.add_argument("--supersedes")
    evidence=ts.add_parser("evidence");evidence.add_argument("--subject");evidence.add_argument("--domain")
    ea=ts.add_parser("evidence-add");ea.add_argument("subject");ea.add_argument("domain");ea.add_argument("source");ea.add_argument("payload",type=_json_value);ea.add_argument("--observed-at");ea.add_argument("--link",action="append",type=_link_value,default=[])
    warrants=ts.add_parser("warrants");warrants.add_argument("--subject");warrants.add_argument("--domain")
    warrant=ts.add_parser("warrant");warrant.add_argument("warrant_id")
    revoke=ts.add_parser("warrant-revoke");revoke.add_argument("warrant_id");revoke.add_argument("--reason",default="")
    release=ts.add_parser("warrant-release");release.add_argument("warrant_id");release.add_argument("--reason",default="")
    bind=ts.add_parser("action-bind-claims");bind.add_argument("action_id");bind.add_argument("claim_ids",nargs="+");bind.add_argument("--bridge",default="");bind.add_argument("--basis",default="operator-bound current evidence")
    reentries=ts.add_parser("reentries");reentries.add_argument("--subject")
    ro=ts.add_parser("reentry-open");ro.add_argument("subject");ro.add_argument("domain");ro.add_argument("reason");ro.add_argument("--prior-warrant");ro.add_argument("--evidence")
    rr=ts.add_parser("reentry-resolve");rr.add_argument("evaluation_id");rr.add_argument("disposition");rr.add_argument("rationale");rr.add_argument("--new-warrant")
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
            task["runs"]=rt.db.list_runs(args.task_id);task["artifacts"]=rt.db.list_artifacts(args.task_id);task["actions"]=rt.db.list_action_requests(args.task_id);task["usage"]=rt.db.get_task_usage(args.task_id)
            for action in task["actions"]:action["temporal_warrants"]=rt.temporal.list_action_warrants(action["id"])
            _json(task)
        elif args.cmd=="actions":
            rows=[]
            tasks=[rt.db.get_task(args.task_id)] if args.task_id else rt.db.list_tasks(100)
            for t in tasks:
                if t: rows.extend(rt.db.list_action_requests(t["id"]))
            _json(rows)
        elif args.cmd=="artifacts":_json(rt.db.list_artifacts(args.task_id))
        elif args.cmd=="approvals":_json([t for t in rt.db.list_tasks(100) if t["status"]=="waiting_approval"])
        elif args.cmd=="temporal":
            tc=args.temporal_cmd
            if tc=="claims":_json(rt.temporal.list_claims(subject=args.subject,domain=args.domain))
            elif tc=="claim":_json(rt.temporal.get_claim(args.claim_id))
            elif tc=="claim-add":
                claim_id=rt.temporal.record_claim(subject=args.subject,predicate=args.predicate,value=args.value,domain=args.domain,source=args.source,truth_state=args.truth_state,claim_kind=args.kind,subject_mode=args.subject_mode,confidence=args.confidence,expires_at=args.expires_at,supersedes_claim_id=args.supersedes)
                _json(rt.temporal.get_claim(claim_id))
            elif tc=="evidence":_json(rt.temporal.list_evidence(subject=args.subject,domain=args.domain))
            elif tc=="evidence-add":_json(rt.ingest_evidence(subject=args.subject,domain=args.domain,source=args.source,payload=args.payload,links=args.link,observed_at=args.observed_at))
            elif tc=="warrants":_json(rt.temporal.list_warrants(subject=args.subject,domain=args.domain))
            elif tc=="warrant":
                row=rt.temporal.get_warrant(args.warrant_id);row["events"]=rt.temporal.list_warrant_events(args.warrant_id);_json(row)
            elif tc=="warrant-revoke":rt.temporal.revoke_warrant(args.warrant_id,args.reason);_json(rt.temporal.get_warrant(args.warrant_id))
            elif tc=="warrant-release":rt.temporal.release_warrant(args.warrant_id,args.reason);_json(rt.temporal.get_warrant(args.warrant_id))
            elif tc=="action-bind-claims":_json(rt.bind_action_claims(args.action_id,args.claim_ids,bridge=args.bridge,basis=args.basis))
            elif tc=="reentries":_json(rt.temporal.list_reentries(subject=args.subject))
            elif tc=="reentry-open":_json({"evaluation_id":rt.temporal.open_reentry(subject=args.subject,domain=args.domain,reason=args.reason,prior_warrant_id=args.prior_warrant,trigger_evidence_id=args.evidence)})
            elif tc=="reentry-resolve":rt.temporal.resolve_reentry(args.evaluation_id,disposition=args.disposition,rationale=args.rationale,new_warrant_id=args.new_warrant);_json([r for r in rt.temporal.list_reentries() if r["id"]==args.evaluation_id][0])
        elif args.cmd=="doctor":return cmd_doctor(rt,root)
        return 0
    finally:rt.db.close()


if __name__=="__main__":raise SystemExit(main())
