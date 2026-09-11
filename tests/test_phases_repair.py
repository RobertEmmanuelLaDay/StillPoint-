import unittest
from stillpoint.phases import checkpoints_from_runs,stage_key
class PhaseRepairTests(unittest.TestCase):
    def test_mixed_fingerprints_do_not_cross_reuse(self):
        runs=[
          {"phase":"contribution","agent_id":"research","output":"A","input_summary":"fp:"+"a"*64},
          {"phase":"primary","agent_id":"builder","output":"B","input_summary":"fp:"+"b"*64},
        ]
        ck=checkpoints_from_runs(runs,expected_fingerprint="b"*64)
        self.assertFalse(ck.can_reuse_contributor("research"));self.assertTrue(ck.primary_done);self.assertEqual(ck.primary_output,"B")
    def test_review_final_separate_from_initial(self):
        fp="c"*64
        runs=[{"phase":"review","agent_id":"stillpoint","output":"CORRECT old","input_summary":"fp:"+fp},{"phase":"review_final","agent_id":"stillpoint","output":"PASS new","input_summary":"fp:"+fp}]
        ck=checkpoints_from_runs(runs,expected_fingerprint=fp)
        self.assertEqual(ck.review_output,"CORRECT old");self.assertEqual(ck.review_final_output,"PASS new")
    def test_stage_key_changes_with_fingerprint(self):
        self.assertNotEqual(stage_key("t","primary",agent_id="a",input_fingerprint="x"),stage_key("t","primary",agent_id="a",input_fingerprint="y"))
if __name__=='__main__':unittest.main()
