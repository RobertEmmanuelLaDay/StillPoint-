import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from normalize import canonical_set
from scoring_calibrated import score_tools_calibrated


class CalibrationTests(unittest.TestCase):
    def test_aliases_collapse(self):
        self.assertEqual(canonical_set(["web_search", "web_research"]), ["web_research"])
        self.assertEqual(canonical_set(["code_interpreter", "code_execution"]), ["code_execution"])

    def test_expected_provider_name_matches_semantic_actual(self):
        chk = score_tools_calibrated(["web_search"], [], ["web_research", "web_search"])
        self.assertEqual(chk.status, "pass")

    def test_missing_still_fails(self):
        chk = score_tools_calibrated(["web_research"], [], [])
        self.assertEqual(chk.status, "fail")
