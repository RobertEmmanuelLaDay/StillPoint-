import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from corpus import CASES
from run_eval import dump_jsonl, eval_case
from scoring import score_contributors, score_primary, score_tools


class EvaluatorUnitTests(unittest.TestCase):
    def test_corpus_size(self):
        self.assertGreaterEqual(len(CASES), 50)
        ids = [c["id"] for c in CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_metamorphic_pairs_differ_on_approval(self):
        by_id = {c["id"]: c for c in CASES}
        self.assertFalse(by_id["M_DRAFT_EMAIL"]["approval_required"])
        self.assertTrue(by_id["M_SEND_EMAIL"]["approval_required"])
        self.assertFalse(by_id["M_ANALYZE_SPEND"]["approval_required"])
        self.assertTrue(by_id["M_SPEND"]["approval_required"])
        self.assertFalse(by_id["M_PREP_KDP"]["approval_required"])
        self.assertTrue(by_id["M_PUBLISH_KDP"]["approval_required"])
        self.assertFalse(by_id["M_SEND_ME"]["approval_required"])
        self.assertTrue(by_id["M_SEND_THEM"]["approval_required"])

    def test_scoring_penalizes_committee(self):
        chk = score_contributors([], ["research"], ["research"])
        self.assertEqual(chk.status, "fail")

    def test_scoring_penalizes_author_search(self):
        chk = score_tools([], ["web_search"], ["web_search"])
        self.assertEqual(chk.status, "fail")

    def test_jsonl_roundtrip(self):
        path = ROOT / "eval" / "stillpoint_adversarial_50.jsonl"
        dump_jsonl(path)
        lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 50)

    def test_single_anti_committee_runs(self):
        result = eval_case(next(c for c in CASES if c["id"] == "AC_01"))
        self.assertIn(result.checks["primary_owner"], {"pass", "fail"})
        self.assertTrue(hasattr(result, "score"))


if __name__ == "__main__":
    unittest.main()
