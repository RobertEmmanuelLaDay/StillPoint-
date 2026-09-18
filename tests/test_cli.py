import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class CLITests(unittest.TestCase):
    def run_cli(self,tmp,*args):
        env=os.environ.copy();env['STILLPOINT_ROOT']=str(tmp);env['PYTHONPATH']=str(ROOT)
        return subprocess.run([sys.executable,'-m','stillpoint.cli',*args],cwd=ROOT,env=env,text=True,capture_output=True)
    def test_doctor_clean_checkout_shape(self):
        # Doctor needs config/eval under runtime root, so use repository itself with isolated DB cleanup.
        env=os.environ.copy();env['STILLPOINT_ROOT']=str(ROOT);env['PYTHONPATH']=str(ROOT)
        p=subprocess.run([sys.executable,'-m','stillpoint.cli','doctor'],cwd=ROOT,env=env,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout);self.assertIn('corpus_integrity',p.stdout)
    def test_doctor_runtime_only_install_does_not_require_eval_assets(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d)
            p=self.run_cli(tmp,'doctor')
            self.assertEqual(p.returncode,0,p.stderr+p.stdout)
            data=json.loads(p.stdout)
            self.assertTrue(data['corpus_integrity']['ok'])
            self.assertFalse(data['corpus_integrity']['available'])

    def test_doctor_source_checkout_fails_closed_when_corpus_manifest_missing(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d)
            (tmp/'pyproject.toml').write_text('[project]\nname="fake"\nversion="0"\n')
            p=self.run_cli(tmp,'doctor')
            self.assertNotEqual(p.returncode,0)
            data=json.loads(p.stdout)
            self.assertFalse(data['corpus_integrity']['ok'])
            self.assertIn('manifest missing',data['corpus_integrity']['error'])

    def test_submit_and_status(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);(tmp/'config').mkdir();(tmp/'config'/'agents.json').write_text((ROOT/'config'/'agents.json').read_text())
            # migrations resolve from installed package root, but doctor isn't used here.
            p=self.run_cli(tmp,'submit','Rewrite chapter 3 in my voice.')
            self.assertEqual(p.returncode,0,p.stderr);self.assertIn('completed',p.stdout)
            s=self.run_cli(tmp,'status');self.assertIn('RECENTLY COMPLETED',s.stdout)


    def test_temporal_cli_claim_evidence_and_inspection(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);(tmp/'config').mkdir();(tmp/'config'/'agents.json').write_text((ROOT/'config'/'agents.json').read_text())
            created=self.run_cli(tmp,'temporal','claim-add','person:1','eligible','benefits','caseworker','true','--truth-state','supported','--subject-mode','dynamic')
            self.assertEqual(created.returncode,0,created.stderr+created.stdout)
            claim=json.loads(created.stdout);claim_id=claim['id']
            listed=self.run_cli(tmp,'temporal','claims','--subject','person:1')
            self.assertEqual(listed.returncode,0,listed.stderr);self.assertEqual(json.loads(listed.stdout)[0]['id'],claim_id)
            evidence=self.run_cli(tmp,'temporal','evidence-add','person:1','benefits','new-record','{"eligible": false}','--link',f'{claim_id}:contradicts')
            self.assertEqual(evidence.returncode,0,evidence.stderr+evidence.stdout)
            result=json.loads(evidence.stdout);self.assertTrue(result['evidence_id'])
            rows=self.run_cli(tmp,'temporal','evidence','--subject','person:1')
            self.assertEqual(rows.returncode,0,rows.stderr);self.assertEqual(len(json.loads(rows.stdout)),1)

if __name__=='__main__':unittest.main()
