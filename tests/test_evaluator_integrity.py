import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from frozen import CorpusIntegrityError, FROZEN_50, SHADOW_20, expected_hashes, load_frozen_50, load_shadow_20, verify_file, verify_frozen_corpora


class FrozenEvaluatorTests(unittest.TestCase):
    def test_frozen_hashes_match(self):
        verified = verify_frozen_corpora()
        self.assertEqual(set(verified), {FROZEN_50.name, SHADOW_20.name})

    def test_exact_case_counts(self):
        self.assertEqual(len(load_frozen_50()), 50)
        self.assertEqual(len(load_shadow_20()), 20)

    def test_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "corpus.jsonl"
            p.write_text('{"id":"x"}\n', encoding="utf-8")
            expected = expected_hashes()[FROZEN_50.name]
            with self.assertRaises(CorpusIntegrityError):
                verify_file(p, expected)

    def test_normal_runner_does_not_regenerate_frozen_corpus(self):
        source = (ROOT / "eval" / "run_eval.py").read_text(encoding="utf-8")
        main = source[source.index("def main"):]
        self.assertNotIn("dump_jsonl(", main)


if __name__ == "__main__":
    unittest.main()
