import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stillpoint.intent import action_intent
from stillpoint.phases import TaskCheckpoints, checkpoints_from_runs
from stillpoint.policy import CompanyPolicy
from stillpoint.registry import AgentRegistry
from stillpoint.router import Router, has_term


class IntentTests(unittest.TestCase):
    def test_analyze_spend_is_not_spend(self):
        self.assertEqual(action_intent("Analyze whether we should spend $5,000."), "none")
        self.assertFalse(CompanyPolicy().approval_requirement("Analyze whether we should spend $5,000.")[0])

    def test_spend_is_spend(self):
        self.assertEqual(action_intent("Spend $5,000."), "spend")
        self.assertTrue(CompanyPolicy().approval_requirement("Spend $5,000.")[0])

    def test_do_not_buy(self):
        self.assertEqual(action_intent("Analyze this $5,000 purchase. Do not buy it."), "none")

    def test_delete_production_database(self):
        self.assertEqual(action_intent("Delete the production database."), "delete")
        self.assertTrue(CompanyPolicy().approval_requirement("Delete the production database.")[0])

    def test_send_me_vs_send_them(self):
        self.assertEqual(action_intent("Send me the draft."), "none")
        self.assertEqual(action_intent("Send the draft to the publisher."), "send_email")

    def test_draft_vs_send(self):
        self.assertEqual(action_intent("Draft the email."), "none")
        self.assertEqual(action_intent("Draft and send an email to Jane."), "send_email")

    def test_prepare_vs_publish(self):
        self.assertEqual(action_intent("Prepare the KDP upload."), "none")
        self.assertEqual(action_intent("Publish the book on KDP."), "publish")

    def test_draft_vs_sign(self):
        self.assertEqual(action_intent("Draft the contract."), "none")
        self.assertEqual(action_intent("Sign the contract."), "sign")

    def test_v5_public_statement_still_approves(self):
        self.assertTrue(CompanyPolicy().approval_requirement("Send this public statement now")[0])


class MatcherTests(unittest.TestCase):
    def test_no_substring_false_positives(self):
        self.assertFalse(has_term("approved metadata", "app"))
        self.assertFalse(has_term("approved metadata", "media"))
        self.assertTrue(has_term("approved metadata", "metadata"))
        self.assertTrue(has_term("write a python migration", "python"))


class RouterTests(unittest.TestCase):
    def setUp(self):
        cfg = ROOT / "config" / "agents.json"
        if not cfg.exists():
            cfg = Path("/home/workdir/artifacts/STILLPOINT_CODEX_INTEGRATION_PACKET_2/config/agents.json")
        self.router = Router(AgentRegistry(cfg), CompanyPolicy())

    def test_python_write_is_builder(self):
        plan = self.router.plan("Write a Python migration")
        self.assertEqual(plan.primary, "builder")
        self.assertIn("code_execution", plan.capabilities)

    def test_chapter_is_author_only(self):
        plan = self.router.plan("Fix this comma.")
        self.assertEqual(plan.primary, "author")
        self.assertEqual(plan.contributors, [])

    def test_kdp_prepare_is_press(self):
        plan = self.router.plan("Prepare KDP metadata.")
        self.assertEqual(plan.primary, "press")
        self.assertFalse(plan.approval_required)

    def test_email_is_signal(self):
        self.assertEqual(self.router.plan("Draft an email to Jane.").primary, "signal")

    def test_publication_ready_manuscript_is_press(self):
        plan = self.router.plan("Get this manuscript to a publication-ready milestone with verified requirements")
        self.assertEqual(plan.primary, "press")
        self.assertIn("author", plan.contributors)
        self.assertIn("research", plan.contributors)


class CheckpointApiTests(unittest.TestCase):
    def test_can_reuse_contributor_exists(self):
        ck = checkpoints_from_runs([
            {"phase": "contribution", "agent_id": "research", "output": "r", "input_summary": "fp:" + "a" * 64},
            {"phase": "primary", "agent_id": "builder", "output": "p", "input_summary": "fp:" + "a" * 64},
        ], expected_fingerprint="a" * 64)
        self.assertTrue(ck.can_reuse_contributor("research"))
        self.assertFalse(ck.can_reuse_contributor("signal"))
        self.assertTrue(ck.can_reuse_primary())

    def test_fingerprint_mismatch_does_not_reuse(self):
        ck = checkpoints_from_runs([
            {"phase": "primary", "agent_id": "author", "output": "p", "input_summary": "fp:" + "a" * 64},
        ], expected_fingerprint="b" * 64)
        self.assertFalse(ck.can_reuse_primary())


if __name__ == "__main__":
    unittest.main()
