from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .attachments import select_attachment_context
from .budgets import BudgetExceeded, BudgetLimits, BudgetedProviderProxy
from .capabilities import capabilities_for_call
from .contracts.models import ActionEvidence,ActionRequest,ActionResult,ArtifactRef
from .providers.base import IncompleteResponseError, InProgressResponseError
from .adapters.base import NotAuthorized, runtime_complete
from .db import CompanyDB
from .file_loader import import_attachment,read_attachment
from .models import TaskOutcome,TaskStatus,WorkPlan
from .phases import fingerprint,stage_key
from .planner import Planner
from .policy import CompanyPolicy
from .prompts import agent_system_prompt,review_prompt,task_prompt
from .registry import AgentRegistry
from .temporal import TemporalAuthorityLedger

def _sha_text(text:str)->str:return hashlib.sha256(text.encode("utf-8")).hexdigest()
def _now_dt():return datetime.now(timezone.utc)

class CompanyRuntime:
    def __init__(self,*,root:Path,db:CompanyDB,registry:AgentRegistry,provider,default_model:str,smart_routing:bool=True,allowed_import_roots=None,default_budget:BudgetLimits|None=None):
        self.root=root;self.db=db;self.registry=registry;self.default_model=default_model
        self.raw_provider=provider;self._active_task_id=None;self.default_budget=default_budget
        self.provider=BudgetedProviderProxy(provider,task_id_getter=lambda:self._active_task_id,before_call=self._budget_before_call,after_call=self._budget_after_call)
        self.policy=CompanyPolicy(provider=self.provider,authority_model=default_model)
        self.temporal=TemporalAuthorityLedger(db)
        self.planner=Planner(registry,self.policy,self.provider,default_model,smart=smart_routing)
        self.managed_files=root/"state"/"managed_files"
        self.allowed_import_roots=[Path(r).resolve() for r in (allowed_import_roots or [root])]
    def _budget_before_call(self,task_id,*,tool_count=0):
        budget=self.db.get_task_budget(task_id)
        if not budget:return
        usage=self.db.get_task_usage(task_id)
        task=self.db.get_task(task_id) or {}
        def hit(limit,current,prospective=0): return limit is not None and current+prospective>limit
        if hit(budget.get("max_model_calls"),usage.get("model_calls",0),1):raise BudgetExceeded("model-call budget exhausted")
        if hit(budget.get("max_tool_calls"),usage.get("tool_calls",0),tool_count):raise BudgetExceeded("tool-call budget exhausted")
        if budget.get("max_total_tokens") is not None and usage.get("total_tokens",0)>=budget["max_total_tokens"]:raise BudgetExceeded("token budget exhausted")
        if budget.get("max_cost_usd") is not None and usage.get("cost_usd",0.0)>=budget["max_cost_usd"]:raise BudgetExceeded("cost budget exhausted")
        if budget.get("max_elapsed_seconds") is not None and task.get("created_at"):
            try:
                created=datetime.fromisoformat(task["created_at"].replace("Z","+00:00")); elapsed=(_now_dt()-created).total_seconds()
            except Exception: elapsed=0
            if elapsed>=budget["max_elapsed_seconds"]:raise BudgetExceeded("elapsed-time budget exhausted")
    def _budget_after_call(self,task_id,*,usage,tool_count=0):
        total=usage.get("total_tokens") if isinstance(usage,dict) else 0
        if total is None and isinstance(usage,dict):total=(usage.get("input_tokens") or 0)+(usage.get("output_tokens") or 0)
        cost=0.0
        if isinstance(usage,dict):
            for key in ("cost_usd","cost"):
                if isinstance(usage.get(key),(int,float)):
                    cost=float(usage[key]);break
        self.db.add_task_usage(task_id,model_calls=1,tool_calls=tool_count,total_tokens=int(total or 0),cost_usd=cost)
    def _memory_text(self,project):
        scopes=["company"]+([f"project:{project}"] if project else [])
        return "\n".join(f"[{r['scope']}] {r['key']}: {r['value']}" for r in self.db.get_memory(scopes))
    def _fingerprint(self,goal,project,attachments):return fingerprint(goal,project,[(a["name"],a["sha256"]) for a in attachments])
    @staticmethod
    def _canonical_output(result):
        text=result.text
        if getattr(result,"citations",None):text+= "\n\nPROVIDER SOURCE URLS:\n"+"\n".join(f"- {u}" for u in result.citations)
        return text
    def _spec_caps(self,plan,agent_id,phase):
        if phase=="contribution":
            for s in plan.contributor_specs:
                if s.get("id")==agent_id:return list(s.get("capabilities") or [])
            return []
        return list(plan.primary_capabilities or plan.capabilities)
    def _spec_requests(self,plan,agent_id,phase):
        if phase=="contribution":
            for s in plan.contributor_specs:
                if s.get("id")==agent_id:return list(s.get("tool_requests") or [])
            return []
        return list(plan.primary_tool_requests or [])
    def _existing_stage(self,task_id,phase,agent_id,input_fp,legacy_fp=""):
        # Current stages are reused only by exact stage-specific fingerprint.
        key=stage_key(task_id,phase,agent_id=agent_id,input_fingerprint=input_fp)
        row=self.db.get_run_by_stage_key(key)
        if row:
            return row
        # Compatibility for pre-stage-fingerprint checkpoints: those releases stored the
        # task-root fingerprint on every run. Reuse is permitted only when that exact
        # root fingerprint still matches the current instruction/files/project state.
        if legacy_fp:
            legacy_key=stage_key(task_id,phase,agent_id=agent_id,input_fingerprint=legacy_fp)
            row=self.db.get_run_by_stage_key(legacy_key)
            if row:
                return row
            expected="fp:"+legacy_fp
            for candidate in self.db.list_runs(task_id):
                if candidate.get("phase")==phase and candidate.get("agent_id")==agent_id and candidate.get("input_summary")==expected:
                    return candidate
        return None
    def _record_planning(self,task_id,goal,project,planning_output,model_planned,planning_model):
        if not planning_output and not model_planned:
            return
        provenance=getattr(self.planner,"last_provenance",{}) or {}
        phase="planning" if model_planned else "planning_fallback"
        fp=fingerprint(goal,project,"planning")
        self.db.add_run(
            task_id,"orchestra",phase,planning_output or "",model=provenance.get("model") or planning_model,
            input_summary="fp:"+fp,citations=provenance.get("citations") or [],
            provider_response_id=provenance.get("provider_response_id") or "",usage=provenance.get("usage") or {},
            stage_key=stage_key(task_id,phase,agent_id="orchestra",input_fingerprint=fp),
        )

    def _call_agent(self,task_id,agent_id,phase,goal,project,contributions,attachments,plan,*,correction="",input_fp="",legacy_fp=""):
        existing=self._existing_stage(task_id,phase,agent_id,input_fp,legacy_fp)
        if existing:return existing["output"]
        agent=self.registry.get(agent_id);model=agent.model or self.default_model
        selected=select_attachment_context(attachments,goal)
        prompt=task_prompt(goal,project,self._memory_text(project),contributions,selected,correction)
        tools=capabilities_for_call(agent_id=agent_id,plan_capabilities=list(plan.capabilities),agent_capabilities=self._spec_caps(plan,agent_id,phase),review_reason=plan.review_reason,scoped_requests=self._spec_requests(plan,agent_id,phase))
        try:
            result=self.provider.generate(system=agent_system_prompt(agent),prompt=prompt,model=model,tools=tools,task_id=task_id,phase=phase,effort="high" if agent_id in {"author","stillpoint","builder"} else "medium")
        except IncompleteResponseError as exc:
            partial=exc.partial_text or ""
            self.db.add_run(task_id,agent_id,phase+"_incomplete",partial,model=model,input_summary="fp:"+input_fp,provider_response_id=exc.provider_response_id or "",stage_key=stage_key(task_id,phase+"_incomplete",agent_id=agent_id,input_fingerprint=input_fp))
            raise
        except InProgressResponseError as exc:
            self.db.add_run(task_id,agent_id,phase+"_in_progress","",model=model,input_summary="fp:"+input_fp,provider_response_id=exc.provider_response_id or "",stage_key=stage_key(task_id,phase+"_in_progress",agent_id=agent_id,input_fingerprint=input_fp))
            raise
        output=self._canonical_output(result)
        run_id=self.db.add_run(task_id,agent_id,phase,output,model=getattr(result,"model",model),input_summary="fp:"+input_fp,citations=getattr(result,"citations",[]),provider_response_id=getattr(result,"provider_response_id",None) or "",usage=getattr(result,"usage",None),stage_key=stage_key(task_id,phase,agent_id=agent_id,input_fingerprint=input_fp))
        if phase in {"primary","resume_primary","revision"}:
            self.db.add_artifact(task_id=task_id,project=project,kind=plan.expected_artifact or "other",name=f"{phase}.txt",sha256=_sha_text(output),produced_by_run_id=run_id,phase=phase)
        return output
    def _review(self,task_id,goal,artifact,reason,plan,*,phase,input_fp,legacy_fp=""):
        existing=self._existing_stage(task_id,phase,"stillpoint",input_fp,legacy_fp)
        if existing:return existing["output"]
        agent=self.registry.get("stillpoint");model=agent.model or self.default_model
        tools=capabilities_for_call(agent_id="stillpoint",plan_capabilities=[],agent_capabilities=[],review_reason=reason)
        try:
            result=self.provider.generate(system=agent_system_prompt(agent),prompt=review_prompt(goal,artifact,reason),model=model,tools=tools,task_id=task_id,phase=phase,effort="high")
        except IncompleteResponseError as exc:
            self.db.add_run(task_id,"stillpoint",phase+"_incomplete",exc.partial_text or "",model=model,input_summary="fp:"+input_fp,provider_response_id=exc.provider_response_id or "",stage_key=stage_key(task_id,phase+"_incomplete",agent_id="stillpoint",input_fingerprint=input_fp))
            raise
        except InProgressResponseError as exc:
            self.db.add_run(task_id,"stillpoint",phase+"_in_progress","",model=model,input_summary="fp:"+input_fp,provider_response_id=exc.provider_response_id or "",stage_key=stage_key(task_id,phase+"_in_progress",agent_id="stillpoint",input_fingerprint=input_fp))
            raise
        output=self._canonical_output(result)
        self.db.add_run(task_id,"stillpoint",phase,output,model=getattr(result,"model",model),input_summary="fp:"+input_fp,citations=getattr(result,"citations",[]),provider_response_id=getattr(result,"provider_response_id",None) or "",usage=getattr(result,"usage",None),stage_key=stage_key(task_id,phase,agent_id="stillpoint",input_fingerprint=input_fp))
        return output
    @staticmethod
    def _judgment(review):
        first=review.strip().splitlines()[0].strip().upper() if review.strip() else "CORRECT"
        if first.startswith("PASS"):return "PASS"
        if first.startswith("HALT"):return "HALT"
        return "CORRECT"
    def _load_saved_attachments(self,task_id):
        out=[]
        for row in self.db.list_task_files(task_id):
            item=read_attachment(row["path"])
            if item["sha256"]!=row["sha256"]:raise RuntimeError(f"managed attachment changed: {row['name']}")
            out.append(item)
        return out
    def _latest_artifact_refs(self,task_id):
        rows=self.db.list_artifacts(task_id)
        if not rows:return []
        latest={}
        for r in rows:
            prior=latest.get(r["kind"])
            if not prior or r["version"]>=prior["version"]:latest[r["kind"]]=r
        return [ArtifactRef(name=r["name"],sha256=r["sha256"],kind=r["kind"],artifact_id=r["id"],version=r["version"]) for r in latest.values()]
    def _latest_artifact_map(self,task_id):
        latest={}
        for r in self.db.list_artifacts(task_id):
            prior=latest.get(r["kind"])
            if not prior or r["version"]>=prior["version"]:latest[r["kind"]]=r
        return latest
    def _stale_superseded_actions(self,task_id,plan):
        latest=self._latest_artifact_map(task_id)
        for row in self.db.list_action_requests(task_id):
            if row["status"] in {"completed","stale","failed"}:continue
            stale=row.get("authority_revision")!=plan.authority_revision
            for ref in json.loads(row["artifact_refs_json"]):
                kind=ref.get("kind","other");cur=latest.get(kind)
                if cur and (cur["id"]!=ref.get("artifact_id") or cur["version"]!=ref.get("version",1) or cur["sha256"]!=ref.get("sha256")):
                    stale=True
            if stale:
                self.db.mark_action_stale(row["id"])
                self.temporal.mark_action_warrants_review_required(row["id"],reason="action request became stale")
    def _prepare_actions(self,task_id,goal,plan):
        if not plan.restricted_actions:return []
        self._stale_superseded_actions(task_id,plan)
        bundle=self.policy.authority(goal); refs=self._latest_artifact_refs(task_id); now=_now_dt(); out=[]
        by_intent={}
        for a in bundle.restricted:
            by_intent.setdefault(a.intent,a)
        for action in plan.restricted_actions:
            a=by_intent.get(action); target=(a.clause.strip() if a and a.clause else (a.target if a else "unknown"));scope=[a.target if a else "unknown",target]
            raw="|".join([task_id,plan.authority_revision,action,target,*[f"{r.artifact_id}:{r.version}:{r.sha256}" for r in refs]])
            idem=hashlib.sha256(raw.encode()).hexdigest();existing=self.db.find_action_request_by_idempotency(idem)
            if existing:
                self.temporal.ensure_runtime_warrant(action_id=existing["id"],task_id=task_id,action_type=existing["action_type"],target=existing["target"],scope=json.loads(existing["scope_json"]),authority_revision=existing["authority_revision"],issued_at=existing["issued_at"],expires_at=existing["expires_at"])
                out.append(existing["id"]);continue
            req=ActionRequest(action_id=hashlib.sha256(("action|"+raw).encode()).hexdigest()[:20],task_id=task_id,action_type=action,target=target,scope=scope,artifact_refs=refs,approval_required=True,approval_id=None,expires_at=(now+timedelta(hours=24)).isoformat(),issued_at=now.isoformat(),idempotency_key=idem,success_criteria=[{"send_email":"delivery_receipt","publish":"publication_receipt","social_post":"post_receipt","spend":"payment_receipt","sign":"signature_receipt","delete":"deletion_receipt"}.get(action,"external_receipt")],authority_revision=plan.authority_revision)
            self.db.add_action_request(req)
            self.temporal.ensure_runtime_warrant(action_id=req.action_id,task_id=task_id,action_type=req.action_type,target=req.target,scope=req.scope,authority_revision=req.authority_revision,issued_at=req.issued_at,expires_at=req.expires_at)
            out.append(req.action_id)
        return out
    def _finish(self,task_id,goal,plan,primary_output,review_text):
        if plan.restricted_actions:
            self._prepare_actions(task_id,goal,plan)
            self.db.update_task(task_id,status="waiting_approval",final_output=primary_output,review_output=review_text,approval_reason=plan.approval_reason)
            return TaskOutcome(task_id,TaskStatus.WAITING_APPROVAL,plan,primary_output,review_text,plan.approval_reason)
        self.db.update_task(task_id,status="completed",final_output=primary_output,review_output=review_text,error=None)
        return TaskOutcome(task_id,TaskStatus.COMPLETED,plan,primary_output,review_text)
    def _execute(self,task_id,goal,project,plan,attachments):
        root_fp=self._fingerprint(goal,project,attachments);self.db.update_task(task_id,input_fingerprint=root_fp)
        contributions=[]
        for i,cid in enumerate(plan.contributors):
            prior=[]
            for j,(name,out) in enumerate(contributions):
                prior_spec=plan.contributor_specs[j] if j<len(plan.contributor_specs) else {}
                if prior_spec.get("before")=="next_contributor":prior.append((name,out))
            cfp=fingerprint(root_fp,"contribution",cid,[(n,_sha_text(o)) for n,o in prior])
            output=self._call_agent(task_id,cid,"contribution",goal,project,prior,attachments,plan,input_fp=cfp,legacy_fp=root_fp)
            contributions.append((self.registry.get(cid).name,output))
        pfp=fingerprint(root_fp,"primary",[(n,_sha_text(o)) for n,o in contributions])
        primary_output=self._call_agent(task_id,plan.primary,"primary",goal,project,contributions,attachments,plan,input_fp=pfp,legacy_fp=root_fp)
        review_text=""
        if plan.review_required and plan.primary!="stillpoint":
            rfp=fingerprint(root_fp,"review",_sha_text(primary_output))
            review_text=self._review(task_id,goal,primary_output,plan.review_reason,plan,phase="review",input_fp=rfp,legacy_fp=root_fp);judgment=self._judgment(review_text)
            if judgment=="HALT":
                self.db.update_task(task_id,status="blocked",final_output=primary_output,review_output=review_text);return TaskOutcome(task_id,TaskStatus.BLOCKED,plan,primary_output,review_text)
            if judgment=="CORRECT":
                revfp=fingerprint(root_fp,"revision",_sha_text(primary_output),_sha_text(review_text))
                primary_output=self._call_agent(task_id,plan.primary,"revision",goal,project,contributions,attachments,plan,correction=review_text,input_fp=revfp,legacy_fp=root_fp)
                ffp=fingerprint(root_fp,"review_final",_sha_text(primary_output))
                review_text=self._review(task_id,goal,primary_output,"post-correction final review",plan,phase="review_final",input_fp=ffp,legacy_fp=root_fp)
                if self._judgment(review_text)!="PASS":
                    self.db.update_task(task_id,status="blocked",final_output=primary_output,review_output=review_text);return TaskOutcome(task_id,TaskStatus.BLOCKED,plan,primary_output,review_text)
        return self._finish(task_id,goal,plan,primary_output,review_text)
    def submit(self,goal,*,project=None,files=None,budget:BudgetLimits|None=None):
        task_id=self.db.create_task(goal,project)
        if budget or self.default_budget:
            self.db.set_task_budget(task_id,budget or self.default_budget)
        self._active_task_id=task_id
        try:
            plan,planning_output,model_planned,planning_model=self.planner.plan(goal);self.db.set_plan(task_id,plan.to_dict())
            self._record_planning(task_id,goal,project,planning_output,model_planned,planning_model)
            self.db.add_plan_revision(task_id,fingerprint(goal),plan.authority_revision,plan.to_dict())
            attachments=[]
            for source in files or []:
                item=import_attachment(source,self.managed_files,task_id,allowed_roots=self.allowed_import_roots);attachments.append(item)
                self.db.add_task_file(task_id,item["path"],item["name"],item["sha256"],original_name=item.get("original_name") or item["name"],media_type=item.get("media_type"),size_bytes=item.get("size_bytes"))
            return self._execute(task_id,goal,project,plan,attachments)
        except BudgetExceeded as exc:
            self.db.update_task(task_id,status="blocked",error=str(exc));raise
        except Exception as exc:
            self.db.update_task(task_id,status="failed",error=str(exc));raise
        finally:
            self._active_task_id=None
    def resume(self,task_id,note=""):
        task=self.db.get_task(task_id)
        if not task:raise KeyError(task_id)
        if task["status"] not in {"new","running","failed","blocked"}:raise RuntimeError(f"task cannot be resumed from status={task['status']}")
        self._active_task_id=task_id
        try:
            effective=task["goal"]
            if note:effective+=f"\n\nCEO RESUME INSTRUCTION:\n{note}"
            if note or not task.get("plan_json"):
                plan,planning_output,model_planned,planning_model=self.planner.plan(effective);self.db.set_plan(task_id,plan.to_dict())
                self._record_planning(task_id,effective,task.get("project"),planning_output,model_planned,planning_model)
                pr=self.db.add_plan_revision(task_id,fingerprint(effective),plan.authority_revision,plan.to_dict())
                if note:self.db.add_resume_instruction(task_id,note,fingerprint(note),plan.authority_revision,pr)
            else:plan=WorkPlan.from_dict(json.loads(task["plan_json"]))
            attachments=self._load_saved_attachments(task_id);self.db.update_task(task_id,status="running",error=None)
            return self._execute(task_id,effective,task.get("project"),plan,attachments)
        except BudgetExceeded as exc:
            self.db.update_task(task_id,status="blocked",error=str(exc));raise
        except Exception as exc:
            self.db.update_task(task_id,status="failed",error=str(exc));raise
        finally:
            self._active_task_id=None
    def promote_memory(self,key,value,*,scope="company",source="CEO",confidence="verified",task_id=None):
        if source != "CEO":
            raise PermissionError("durable memory promotion requires CEO source")
        if not key or not str(key).strip():raise ValueError("memory key required")
        self.db.set_memory(str(key),str(value),scope=scope,source=source,confidence=confidence,task_id=task_id)
        return {"scope":scope,"key":str(key),"value":str(value),"source":source,"confidence":confidence,"task_id":task_id}
    def _request_from_row(self,row):
        refs=[ArtifactRef(**{k:v for k,v in item.items() if k in {"name","sha256","kind","media_type","artifact_id","version"}}) for item in json.loads(row["artifact_refs_json"])]
        return ActionRequest(action_id=row["id"],task_id=row["task_id"],action_type=row["action_type"],target=row["target"],scope=json.loads(row["scope_json"]),artifact_refs=refs,approval_required=bool(row["approval_required"]),approval_id=row["approval_id"],expires_at=row["expires_at"],issued_at=row["issued_at"],idempotency_key=row["idempotency_key"],success_criteria=json.loads(row["success_criteria_json"]),click_irreversible=bool(row["click_irreversible"]),authority_revision=row["authority_revision"])
    def execute_action(self,action_id,adapter_registry,*,now_iso=None):
        row=self.db.get_action_request(action_id)
        if not row:raise KeyError(action_id)
        prior_results = self.db.list_action_results(action_id)
        if row["status"] == "completed":
            raise RuntimeError("action idempotency prevents duplicate execution")
        # A null/dry-run attempt proves no real external action occurred, so it must not
        # permanently consume the request. Any real adapter dispatch is treated as
        # potentially side-effecting and cannot be repeated automatically.
        if any(
            result.get("adapter")
            and result.get("adapter") != "null"
            and not str(result.get("adapter")).startswith("dry_run")
            for result in prior_results
        ):
            raise RuntimeError("action idempotency prevents duplicate external dispatch")
        req=self._request_from_row(row)
        if req.approval_required and (not req.permitted(now_iso or _now_dt().isoformat()) or not self.db.has_action_approval(req.action_id,req.approval_id)):
            raise NotAuthorized("missing, expired, or mismatched approval")
        latest=self._latest_artifact_map(req.task_id)
        for ref in req.artifact_refs:
            cur=latest.get(ref.kind)
            if ref.artifact_id and (not cur or cur["id"]!=ref.artifact_id or cur["version"]!=ref.version or cur["sha256"]!=ref.sha256):raise NotAuthorized("artifact changed since authorization")
        auth_now=now_iso or _now_dt().isoformat()
        try:
            temporal_warrant=self.temporal.authorize_action(req.action_id,req.action_type,"external_action",req.scope,now_iso=auth_now)
        except PermissionError as exc:
            self.db.update_action_request_status(action_id,"review_required")
            self.db.update_task(req.task_id,status="blocked",error=str(exc))
            raise NotAuthorized(str(exc)) from exc
        result=adapter_registry.execute(req)
        self.db.add_action_result(result)
        if not self.temporal.authorization_still_current(temporal_warrant["id"],expected_updated_at=temporal_warrant["updated_at"],action_type=req.action_type,domain="external_action",scope=req.scope,now_iso=now_iso or _now_dt().isoformat()):
            self.db.update_action_request_status(action_id,"review_required")
            self.db.update_task(req.task_id,status="blocked",error="temporal warrant changed during execution; external result preserved for review")
            return {"action_id":action_id,"status":"review_required","result":result}
        status=runtime_complete(req,result,now_iso=now_iso)
        self.db.update_action_request_status(action_id,status)
        if status=="completed":
            self.temporal.complete_action_warrant(action_id)
            pending=[r for r in self.db.list_action_requests(req.task_id) if r["status"]!="completed"]
            if not pending:self.db.update_task(req.task_id,status="completed")
        return {"action_id":action_id,"status":status,"result":result}
    def approve(self,task_id,note=""):
        task=self.db.get_task(task_id)
        if not task:raise KeyError(task_id)
        if task["status"]!="waiting_approval":raise RuntimeError("task is not waiting for approval")
        latest=self._latest_artifact_map(task_id)
        requests=[r for r in self.db.list_action_requests(task_id) if r["status"]=="waiting_approval"]
        if not requests:raise RuntimeError("no current action requests to approve")
        # Authorization binds the latest exact artifact version for each referenced kind.
        for r in requests:
            for ref in json.loads(r["artifact_refs_json"]):
                cur=latest.get(ref.get("kind","other"))
                if ref.get("artifact_id") and (not cur or cur["id"]!=ref.get("artifact_id") or cur["version"]!=ref.get("version",1) or cur["sha256"]!=ref.get("sha256")):
                    self.db.mark_action_stale(r["id"]);raise RuntimeError("artifact changed since action request was prepared")
        try:
            for r in requests:
                self.temporal.authorize_action(r["id"],r["action_type"],"external_action",json.loads(r["scope_json"]),now_iso=_now_dt().isoformat())
        except PermissionError as exc:
            for r in requests:self.db.update_action_request_status(r["id"],"review_required")
            self.db.update_task(task_id,status="blocked",error=str(exc))
            raise RuntimeError("current temporal warrant required before approval") from exc
        approval=self.db.add_approval(task_id,"approved",note)
        for r in requests:self.db.bind_action_approval(r["id"],approval)
        self.db.update_task(task_id,status="ready_for_action",approval_reason="")
        return self.db.get_task(task_id)
    def ingest_evidence(self,*,subject,domain,source,payload,links=None,observed_at=None,provenance=None):
        result=self.temporal.ingest_evidence(
            subject=subject,domain=domain,source=source,payload=payload,links=links or [],
            observed_at=observed_at,provenance=provenance,
        )
        blocked_tasks=[]
        for action_id in result["review_action_ids"]:
            action=self.db.get_action_request(action_id)
            if not action or action["status"] in {"completed","stale","failed"}:continue
            self.db.update_action_request_status(action_id,"review_required")
            task=self.db.get_task(action["task_id"])
            if task and task["status"] not in {"completed","rejected"}:
                self.db.update_task(action["task_id"],status="blocked",error="material continuing evidence requires temporal review")
                blocked_tasks.append(action["task_id"])
        result["blocked_task_ids"]=list(dict.fromkeys(blocked_tasks))
        return result

    def bind_action_claims(self,action_id,claim_ids,*,bridge="",basis="operator-bound current evidence"):
        action=self.db.get_action_request(action_id)
        if not action:raise KeyError(action_id)
        warrant_id=self.temporal.attach_claims_to_action_warrant(
            action_id,list(claim_ids),claim_bridge=bridge,basis=basis,issued_by="stillpoint-runtime"
        )
        self.db.reset_action_for_reapproval(action_id)
        task=self.db.get_task(action["task_id"])
        if task and task["status"] not in {"completed","rejected"}:
            self.db.update_task(action["task_id"],status="waiting_approval",approval_reason="temporal claim binding changed; CEO reapproval required",error=None)
        return {"action_id":action_id,"warrant_id":warrant_id,"claim_ids":list(dict.fromkeys(claim_ids))}

    def reject(self,task_id,note=""):
        task=self.db.get_task(task_id)
        if not task:raise KeyError(task_id)
        self.db.add_approval(task_id,"rejected",note);self.db.update_task(task_id,status="rejected");return self.db.get_task(task_id)
