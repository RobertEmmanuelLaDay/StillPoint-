import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from stillpoint.authority.merge import apply_policy_floor, assess_authority_bundle, merge
from stillpoint.authority.schema import AuthorityAssessment, RESTRICTED_INTENTS
from stillpoint.authority.semantic import parse_semantic
from normalize import canonical_set


class PolicyFloorTests(unittest.TestCase):
    def test_every_restricted_intent_survives_none_assessment(self):
        base = AuthorityAssessment("none", "unknown", "unknown", 0.1, "empty")
        for intent in RESTRICTED_INTENTS:
            out = apply_policy_floor(base, intent)
            self.assertEqual(out.intent, intent, intent)
            self.assertTrue(out.approval_required, intent)
            self.assertNotEqual(out.action_family, "none", intent)


class ClauseTests(unittest.TestCase):
    def test_draft_then_send(self):
        bundle = assess_authority_bundle("Draft the email. Then send it to Jane.")
        self.assertIn("send_email", bundle.restricted_intents)

    def test_analyze_then_spend(self):
        bundle = assess_authority_bundle("Analyze the budget. Then spend $5,000.")
        self.assertIn("spend", bundle.restricted_intents)

    def test_prepare_then_publish(self):
        bundle = assess_authority_bundle("Prepare the KDP package. Then publish the book on KDP.")
        self.assertIn("publish", bundle.restricted_intents)

    def test_prohibit_does_not_cover_other_clause(self):
        bundle = assess_authority_bundle("Do not email Jane. Then publish the book on KDP.")
        self.assertIn("publish", bundle.restricted_intents)

    def test_find_then_wipe(self):
        bundle = assess_authority_bundle("Find the files. Then wipe the production repository.")
        self.assertIn("delete", bundle.restricted_intents)

    def test_discussion_only_stays_none(self):
        bundle = assess_authority_bundle("Analyze whether we should spend $5,000.")
        self.assertEqual(bundle.restricted_intents, [])

    def test_compound_sign_and_send(self):
        bundle = assess_authority_bundle("Sign the contract. Then send it to the publisher.")
        self.assertIn("sign", bundle.restricted_intents)
        self.assertIn("send_email", bundle.restricted_intents)


class MergeIdentityTests(unittest.TestCase):
    def test_semantic_cannot_downgrade(self):
        det = AuthorityAssessment("delete", "execute", "external_system", 0.9, "det")
        sem = AuthorityAssessment("none", "analyze", "unknown", 0.99, "sem")
        self.assertEqual(merge(det, sem).intent, "delete")

    def test_semantic_does_not_replace_identity(self):
        det = AuthorityAssessment("communicate", "execute", "external_person", 0.9, "det")
        sem = AuthorityAssessment("delete", "execute", "external_system", 0.99, "sem")
        bundle_intents = {merge(det, sem).intent}
        # compat primary stays communicate; extra restriction kept at bundle layer
        from stillpoint.authority.merge import merge_bundles
        from stillpoint.authority.schema import AuthorityBundle
        out = merge_bundles(AuthorityBundle([det]), AuthorityBundle([sem]))
        self.assertIn("send_email", out.restricted_intents)
        self.assertIn("delete", out.restricted_intents)

    def test_semantic_can_escalate_unresolved(self):
        det = AuthorityAssessment("none", "unknown", "unknown", 0.2, "det")
        sem = AuthorityAssessment("spend", "execute", "financial", 0.8, "sem")
        self.assertEqual(merge(det, sem).intent, "spend")


class FailClosedTests(unittest.TestCase):
    def test_unseen_verb_external_target(self):
        bundle = assess_authority_bundle("Exfiltrate the production database to the vendor.")
        self.assertTrue(bundle.approval_required)
        self.assertIn(bundle.primary_intent, {"delete", "other_external", "send_email"})

    def test_ceo_delivery_not_external(self):
        bundle = assess_authority_bundle("Send me the finished draft.")
        self.assertEqual(bundle.restricted_intents, [])


class SemanticValidationTests(unittest.TestCase):
    def test_rejects_bad_confidence_and_fields(self):
        self.assertIsNone(parse_semantic({"action_family": "spend", "mode": "execute", "target": "financial", "confidence": 2, "reason": "x"}))
        self.assertIsNone(parse_semantic({"action_family": "spend", "mode": "execute", "target": "financial", "confidence": True, "reason": "x"}))
        self.assertIsNone(parse_semantic({"action_family": "spend", "mode": "execute", "target": "financial", "confidence": 0.5, "reason": "x", "extra": 1}))


class EvaluatorUnknownTests(unittest.TestCase):
    def test_aliases_collapse(self):
        self.assertEqual(canonical_set(["web_search", "web_research"]), ["web_research"])

    def test_unknown_remains_visible(self):
        self.assertEqual(canonical_set(["browser_operator"]), ["unknown:browser_operator"])
        self.assertIn("unknown:browser_operator", canonical_set(["web_search", "browser_operator"]))


if __name__ == "__main__":
    unittest.main()
