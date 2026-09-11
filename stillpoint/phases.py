from __future__ import annotations
import hashlib,json
from dataclasses import dataclass,field

def stage_key(task_id:str,phase:str,*,agent_id:str="",input_fingerprint:str=""):
    raw=f"{task_id}|{phase}|{agent_id}|{input_fingerprint}";digest=hashlib.sha256(raw.encode()).hexdigest()[:16]
    parts=[task_id,phase];
    if agent_id:parts.append(agent_id)
    parts.append(digest);return ":".join(parts)

def fingerprint(*parts):return hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()
def row_fingerprint(row):
    s=row.get("input_summary") or ""
    return s[3:].split("|",1)[0][:64] if s.startswith("fp:") else ""

@dataclass(frozen=True)
class TaskCheckpoints:
    planning_done:bool=False
    contributors_done:tuple[str,...]=()
    primary_done:bool=False
    review_done:bool=False
    revision_done:bool=False
    review_final_done:bool=False
    primary_output:str=""
    review_output:str=""
    revision_output:str=""
    review_final_output:str=""
    input_fingerprint:str=""
    contributor_outputs:dict[str,str]=field(default_factory=dict)
    def can_reuse_contributor(self,agent_id):return agent_id in self.contributors_done
    def can_reuse_primary(self):return self.primary_done and bool(self.primary_output)
    def can_reuse_review(self):return self.review_done and bool(self.review_output)

def checkpoints_from_runs(runs:list[dict],*,expected_fingerprint:str=""):
    contributors={};planning=primary=review=revision=review_final=False
    primary_output=review_output=revision_output=review_final_output=""
    for row in runs:
        fp=row_fingerprint(row)
        if expected_fingerprint and fp!=expected_fingerprint:
            continue
        phase=row.get("phase") or "";agent=row.get("agent_id") or "";out=row.get("output") or ""
        if phase in {"planning","planning_fallback","resume_planning","resume_planning_fallback"}:planning=True
        elif phase=="contribution" and agent:contributors[agent]=out
        elif phase in {"primary","resume_primary"}:primary=True;primary_output=out
        elif phase=="revision":revision=True;revision_output=out
        elif phase=="review":review=True;review_output=out
        elif phase=="review_final":review_final=True;review_final_output=out
    return TaskCheckpoints(planning,tuple(contributors),primary,review,revision,review_final,primary_output,review_output,revision_output,review_final_output,expected_fingerprint,contributors)
