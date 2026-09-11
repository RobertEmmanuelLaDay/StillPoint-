import unittest
from stillpoint.authority.deterministic import assess_bundle
from stillpoint.authority.gate import authority_actions
from stillpoint.authority.semantic import SemanticAuthority
from stillpoint.authority.merge import assess_authority_bundle
from stillpoint.contracts.models import ActionRequest, ActionEvidence, ActionResult, ArtifactRef
from stillpoint.adapters.base import evidence_satisfies, runtime_complete

class FakeProvider:
    default_model="fake-neutral-model"
    def __init__(self,text):self.text=text;self.models=[]
    def generate(self,**kw):
        self.models.append(kw.get("model"))
        return type("R",(),{"text":self.text})()

class RepairCoreTests(unittest.TestCase):
    def test_descriptive_repository_not_command(self):
        self.assertEqual(assess_bundle("The repository is in production.").restricted_intents,[])
    def test_descriptive_database_not_command(self):
        self.assertEqual(assess_bundle("The database contains $500 in test records.").restricted_intents,[])
    def test_unknown_external_imperative_fails_closed(self):
        b=assess_bundle("Exfiltrate the production database to the vendor.")
        self.assertTrue(b.approval_required)
    def test_compound_sign_spend(self):
        self.assertEqual(set(authority_actions("Sign the agreement. Then pay the invoice.")),{"sign","spend"})
    def test_publish_send(self):
        self.assertEqual(set(authority_actions("Publish the announcement. Then send it to Jane.")),{"publish","send_email"})
    def test_semantic_escalates_but_not_downgrades(self):
        p=FakeProvider('{"action_family":"none","mode":"analyze","target":"unknown","confidence":0.9,"reason":"no"}')
        b=assess_authority_bundle("Wipe the production repository.",semantic=SemanticAuthority(p))
        self.assertIn("delete",b.restricted_intents)
    def test_semantic_uses_provider_model_not_grok_hardcode(self):
        p=FakeProvider('{"action_family":"spend","mode":"execute","target":"financial","confidence":0.9,"reason":"x"}')
        SemanticAuthority(p).assess("do it")
        self.assertEqual(p.models,["fake-neutral-model"])
    def req(self,**kw):
        d=dict(action_id="a",task_id="t",action_type="send_email",target="jane",scope=["mail"],artifact_refs=[ArtifactRef("x","aa")],approval_required=True,approval_id="ok",expires_at="2026-01-01T10:00:00+00:00",issued_at="2026-01-01T00:00:00+00:00",idempotency_key="k",success_criteria=["smtp-id"])
        d.update(kw);return ActionRequest(**d)
    def test_timezone_expiry_real_datetime(self):
        self.assertFalse(self.req().permitted("2026-01-01T05:30:00-05:00"))
    def test_naive_timestamp_fails_closed(self):
        self.assertFalse(self.req(expires_at="2026-01-01T10:00:00").permitted("2026-01-01T05:00:00+00:00"))
    def test_negative_note_cannot_satisfy(self):
        self.assertFalse(evidence_satisfies(self.req(),[ActionEvidence("text","x",note="not sent")]))
    def test_structured_evidence_satisfies(self):
        self.assertTrue(evidence_satisfies(self.req(),[ActionEvidence("receipt","x",satisfies="smtp-id")]))
    def test_null_adapter_never_completes(self):
        r=ActionResult("a","succeeded",[ActionEvidence("smtp-id","x",satisfies="smtp-id")],adapter="null")
        self.assertEqual(runtime_complete(self.req(),r,now_iso="2026-01-01T05:00:00+00:00"),"ready_for_action")

if __name__=='__main__':unittest.main()

from stillpoint.policy import CompanyPolicy
from stillpoint.models import WorkPlan

class PolicyIntegrationTests(unittest.TestCase):
    def test_policy_preserves_compound_actions(self):
        p=CompanyPolicy()
        self.assertEqual(set(p.action_intents("Sign the agreement. Then pay the invoice.")),{"sign","spend"})
    def test_workplan_roundtrip_preserves_actions(self):
        p=WorkPlan(primary="ledger",external_action_intent="sign",restricted_actions=["sign","spend"])
        q=WorkPlan.from_dict(p.to_dict())
        self.assertEqual(q.restricted_actions,["sign","spend"])
    def test_legacy_plan_promotes_primary_action(self):
        q=WorkPlan.from_dict({"primary":"signal","external_action_intent":"send_email"})
        self.assertEqual(q.restricted_actions,["send_email"])
    def test_semantic_provider_is_live_in_policy(self):
        p=FakeProvider('{"action_family":"spend","mode":"execute","target":"financial","confidence":0.9,"reason":"semantic escalation"}')
        policy=CompanyPolicy(provider=p)
        self.assertIn("spend",policy.action_intents("Authorize this external operation."))
        self.assertEqual(p.models,["fake-neutral-model"])
