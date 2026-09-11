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
    def test_submit_and_status(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);(tmp/'config').mkdir();(tmp/'config'/'agents.json').write_text((ROOT/'config'/'agents.json').read_text())
            # migrations resolve from installed package root, but doctor isn't used here.
            p=self.run_cli(tmp,'submit','Rewrite chapter 3 in my voice.')
            self.assertEqual(p.returncode,0,p.stderr);self.assertIn('completed',p.stdout)
            s=self.run_cli(tmp,'status');self.assertIn('RECENTLY COMPLETED',s.stdout)

if __name__=='__main__':unittest.main()
