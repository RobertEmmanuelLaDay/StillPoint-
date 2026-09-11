import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stillpoint.authority.deterministic import assess
from stillpoint.authority.merge import merge
from stillpoint.authority.schema import AuthorityAssessment


class FamilyParaphraseTests(unittest.TestCase):
    def test_communicate(self):
        for phrase in (
            "Send this note to the printer.",
            "Transmit this note to the printer.",
            "Forward this note to the printer.",
            "Hand the finished letter to the school secretary.",
        ):
            a = assess(phrase)
            self.assertEqual(a.intent, "send_email", phrase)
            self.assertTrue(a.approval_required, phrase)

    def test_publish(self):
        for phrase in (
            "Publish the book on KDP.",
            "Release the paperback publicly.",
            "Make the listing live.",
        ):
            a = assess(phrase)
            self.assertEqual(a.intent, "publish", phrase)

    def test_spend(self):
        for phrase in (
            "Spend $5,000.",
            "Purchase this subscription.",
            "Pay the $2400 invoice.",
            "Place the $2,400 ad buy now.",
        ):
            a = assess(phrase)
            self.assertEqual(a.intent, "spend", phrase)

    def test_sign(self):
        for phrase in (
            "Sign the contract.",
            "Execute the agreement.",
            "Initial the agreement.",
        ):
            a = assess(phrase)
            self.assertEqual(a.intent, "sign", phrase)

    def test_delete(self):
        for phrase in (
            "Delete the production database.",
            "Wipe the production repository.",
            "Destroy the production records.",
        ):
            a = assess(phrase)
            self.assertEqual(a.intent, "delete", phrase)


class ModeTests(unittest.TestCase):
    def test_analyze_not_execute(self):
        self.assertEqual(assess("Analyze whether we should spend $5,000.").intent, "none")
        self.assertEqual(assess("Analyze whether publishing makes sense.").intent, "none")

    def test_recommend(self):
        self.assertEqual(assess("Give me a recommendation on a $2,400 ad buy.").intent, "none")

    def test_draft(self):
        self.assertEqual(assess("Draft a contract.").intent, "none")
        self.assertEqual(assess("Sketch possible agreement terms.").intent, "none")

    def test_prepare(self):
        self.assertEqual(assess("Prepare the KDP package.").intent, "none")
        self.assertEqual(assess("Prepare it for possible release.").intent, "none")

    def test_prohibit(self):
        self.assertEqual(assess("Do not send this.").intent, "none")
        self.assertEqual(assess("Do not transmit it.").intent, "none")

    def test_find(self):
        self.assertEqual(assess("Find the files we may eventually delete.").intent, "none")
        self.assertEqual(assess("Identify files we might wipe later.").intent, "none")


class TargetTests(unittest.TestCase):
    def test_ceo_vs_external(self):
        self.assertEqual(assess("Send me the finished draft.").intent, "none")
        self.assertEqual(assess("Hand the finished letter back to me.").intent, "none")
        self.assertEqual(assess("Send the finished draft to the publisher.").intent, "send_email")
        self.assertEqual(assess("Hand the finished letter to the school secretary.").intent, "send_email")


class MonotonicTests(unittest.TestCase):
    def test_model_cannot_downgrade_delete(self):
        det = AuthorityAssessment("delete", "execute", "external_system", 0.9, "det", "deterministic")
        sem = AuthorityAssessment("none", "analyze", "unknown", 0.99, "model says chat", "semantic")
        merged = merge(det, sem)
        self.assertEqual(merged.intent, "delete")

    def test_model_can_escalate_unknown(self):
        det = AuthorityAssessment("none", "unknown", "unknown", 0.2, "det", "deterministic")
        sem = AuthorityAssessment("spend", "execute", "financial", 0.8, "buy now", "semantic")
        merged = merge(det, sem)
        self.assertEqual(merged.intent, "spend")


class AmbiguousImperativeTests(unittest.TestCase):
    def test_unresolved_external_imperative_fail_closed(self):
        a = assess("Transmit this package offsite immediately.")
        self.assertIn(a.intent, {"send_email", "other_external"})
        self.assertTrue(a.approval_required)
