import tempfile
import unittest
from pathlib import Path

from stillpoint.db import CompanyDB
from stillpoint.models import WorkPlan
from stillpoint.providers.base import IncompleteResponseError, ProviderResult
from stillpoint.providers.stub import NeutralStubProvider
from stillpoint.registry import AgentRegistry
from stillpoint.runtime import CompanyRuntime

ROOT = Path(__file__).resolve().parents[1]


class PlanningProvider:
    def generate(self, **kwargs):
        if kwargs.get("json_schema_name") == "authority_assessment":
            return ProviderResult(text='{"action_family":"none","mode":"unknown","target":"unknown","confidence":0.5,"reason":"none"}', model="neutral")
        if kwargs.get("json_schema"):
            return ProviderResult(
                text='{"primary":"author","contributors":[],"capabilities":[],"research_required":false,"review_required":false,"review_reason":"","expected_artifact":"prose","external_action_intent":"none","approval_required":false,"approval_reason":"","routing_reason":"Author owns this writing task."}',
                model="neutral", provider_response_id="plan-123", usage={"total_tokens": 9}, citations=["https://example.test/plan"]
            )
        return ProviderResult(text="done", model="neutral")


class IncompleteProvider:
    def generate(self, **kwargs):
        if kwargs.get("json_schema_name") == "authority_assessment":
            return ProviderResult(text='{"action_family":"none","mode":"unknown","target":"unknown","confidence":0.5,"reason":"none"}', model="neutral")
        raise IncompleteResponseError("cut off", partial_text="half-built", provider_response_id="resp-half")


class ProviderRuntimeTests(unittest.TestCase):
    def make(self, tmp, provider, smart=False):
        return CompanyRuntime(
            root=tmp, db=CompanyDB(tmp / "db.sqlite"), registry=AgentRegistry(ROOT / "config" / "agents.json"),
            provider=provider, default_model="neutral", smart_routing=smart,
        )

    def test_neutral_provider_runs_core(self):
        with tempfile.TemporaryDirectory() as d:
            rt=self.make(Path(d), NeutralStubProvider(), smart=False)
            out=rt.submit("Help me decide what to do next.")
            self.assertEqual(out.status.value,"completed")
            self.assertNotIn("grok", out.final_output.lower())
            rt.db.close()

    def test_planner_provenance_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            rt=self.make(Path(d), PlanningProvider(), smart=True)
            out=rt.submit("Rewrite chapter 3 in my voice.")
            planning=[r for r in rt.db.list_runs(out.task_id) if r["phase"]=="planning"]
            self.assertEqual(len(planning),1)
            self.assertEqual(planning[0]["provider_response_id"],"plan-123")
            self.assertIn('"total_tokens": 9', planning[0]["usage_json"])
            self.assertIn("example.test", planning[0]["citations_json"])
            rt.db.close()

    def test_incomplete_output_is_persisted_not_completed(self):
        with tempfile.TemporaryDirectory() as d:
            rt=self.make(Path(d), IncompleteProvider(), smart=False)
            with self.assertRaises(IncompleteResponseError):
                rt.submit("Rewrite chapter 3 in my voice.")
            task=rt.db.list_tasks(1)[0]
            self.assertEqual(task["status"],"failed")
            partial=[r for r in rt.db.list_runs(task["id"]) if r["phase"].endswith("_incomplete")]
            self.assertEqual(partial[0]["output"],"half-built")
            self.assertEqual(partial[0]["provider_response_id"],"resp-half")
            rt.db.close()


if __name__ == '__main__': unittest.main()
