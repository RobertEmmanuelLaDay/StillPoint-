import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stillpoint.db import CompanyDB
from stillpoint.models import WorkPlan
from stillpoint.providers.mock import MockProvider
from stillpoint.registry import AgentRegistry
from stillpoint.runtime import CompanyRuntime


def rt(tmp: Path) -> CompanyRuntime:
    cfg = ROOT / "config" / "agents.json"
    return CompanyRuntime(
        root=tmp,
        db=CompanyDB(tmp / "db.sqlite"),
        registry=AgentRegistry(cfg),
        provider=MockProvider(),
        default_model="mock",
        smart_routing=False,
    )


class ResumeStageTests(unittest.TestCase):
    def test_research_completed_builder_not(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            runtime = rt(tmp)
            goal = "Research current API behavior and then build the client."
            tid = runtime.db.create_task(goal)
            fp = runtime._fingerprint(goal, None, [])
            plan = WorkPlan(primary="builder", contributors=["research"], capabilities=["web_research"])
            runtime.db.set_plan(tid, plan.to_dict())
            runtime.db.update_task(tid, input_fingerprint=fp)
            runtime.db.add_run(tid, "research", "contribution", "RESEARCH_DONE", input_summary="fp:" + fp)
            runtime.db.update_task(tid, status="failed", error="interrupt after research")
            out = runtime.resume(tid)
            contrib = [r for r in runtime.db.list_runs(tid) if r["phase"] == "contribution"]
            self.assertEqual(sum(1 for r in contrib if r["agent_id"] == "research"), 1)
            self.assertEqual(contrib[0]["output"], "RESEARCH_DONE")
            runtime.db.close()

    def test_primary_completed_review_not(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            runtime = rt(tmp)
            goal = "Rewrite chapter 3 in my voice."
            tid = runtime.db.create_task(goal)
            fp = runtime._fingerprint(goal, None, [])
            plan = WorkPlan(primary="author", review_required=True, review_reason="publication")
            runtime.db.set_plan(tid, plan.to_dict())
            runtime.db.update_task(tid, input_fingerprint=fp)
            runtime.db.add_run(tid, "author", "primary", "PRIMARY_DONE", input_summary="fp:" + fp)
            runtime.db.update_task(tid, status="failed", error="interrupt after primary")
            runtime.resume(tid)
            primaries = [r for r in runtime.db.list_runs(tid) if r["phase"] in {"primary", "resume_primary"}]
            self.assertEqual(len(primaries), 1)
            self.assertEqual(primaries[0]["output"], "PRIMARY_DONE")
            runtime.db.close()

    def test_review_pass_commit_interrupt(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            runtime = rt(tmp)
            goal = "Prepare the final manuscript for publication-ready review."
            tid = runtime.db.create_task(goal)
            fp = runtime._fingerprint(goal, None, [])
            plan = WorkPlan(primary="author", review_required=True, review_reason="publication")
            runtime.db.set_plan(tid, plan.to_dict())
            runtime.db.update_task(tid, input_fingerprint=fp)
            runtime.db.add_run(tid, "author", "primary", "PRIMARY_DONE", input_summary="fp:" + fp)
            runtime.db.add_run(tid, "stillpoint", "review", "PASS\nok", input_summary="fp:" + fp)
            runtime.db.update_task(tid, status="failed", error="interrupt after review")
            runtime.resume(tid)
            self.assertEqual(len([r for r in runtime.db.list_runs(tid) if r["phase"] == "primary"]), 1)
            self.assertEqual(len([r for r in runtime.db.list_runs(tid) if r["phase"] == "review"]), 1)
            runtime.db.close()

    def test_revision_reused(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            runtime = rt(tmp)
            goal = "Prepare the final manuscript for publication-ready review."
            tid = runtime.db.create_task(goal)
            fp = runtime._fingerprint(goal, None, [])
            plan = WorkPlan(primary="author", review_required=True, review_reason="publication")
            runtime.db.set_plan(tid, plan.to_dict())
            runtime.db.update_task(tid, input_fingerprint=fp)
            runtime.db.add_run(tid, "author", "primary", "PRIMARY_DONE", input_summary="fp:" + fp)
            runtime.db.add_run(tid, "stillpoint", "review", "CORRECT\nfix x", input_summary="fp:" + fp)
            runtime.db.add_run(tid, "author", "revision", "REVISED", input_summary="fp:" + fp)
            runtime.db.update_task(tid, status="failed", error="interrupt after revision")
            runtime.resume(tid)
            self.assertEqual(len([r for r in runtime.db.list_runs(tid) if r["phase"] == "revision"]), 1)
            runtime.db.close()


if __name__ == "__main__":
    unittest.main()
