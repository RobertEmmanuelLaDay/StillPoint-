import tempfile,unittest
from pathlib import Path
from stillpoint.db import CompanyDB
from stillpoint.registry import AgentRegistry
from stillpoint.runtime import CompanyRuntime
from stillpoint.providers_mock import MockProvider,ProviderResult
from stillpoint.attachments import select_attachment_context

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/'config'/'agents.json'
def make_rt(root,provider=None):
    return CompanyRuntime(root=root,db=CompanyDB(root/'db.sqlite'),registry=AgentRegistry(CFG),provider=provider or MockProvider(),default_model='mock',smart_routing=False)

class RuntimeRepairTests(unittest.TestCase):
    def test_draft_not_send(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rt=make_rt(root);out=rt.submit('Draft the email to Jane. Do not send it.')
            self.assertEqual(out.status.value,'completed');self.assertEqual(out.plan.restricted_actions,[]);rt.db.close()
    def test_send_requires_action_approval(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rt=make_rt(root);out=rt.submit('Send the email to Jane.')
            self.assertEqual(out.status.value,'waiting_approval');reqs=rt.db.list_action_requests(out.task_id);self.assertEqual(len(reqs),1);self.assertEqual(reqs[0]['action_type'],'send_email');rt.approve(out.task_id);self.assertEqual(rt.db.get_task(out.task_id)['status'],'ready_for_action');rt.db.close()
    def test_compound_actions_persist(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rt=make_rt(root);out=rt.submit('Sign the agreement. Then pay the invoice.')
            self.assertEqual(set(out.plan.restricted_actions),{'sign','spend'});self.assertEqual({r['action_type'] for r in rt.db.list_action_requests(out.task_id)},{'sign','spend'});rt.db.close()
    def test_resume_recalculates_authority(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rt=make_rt(root);out=rt.submit('Draft the email.')
            rt.db.update_task(out.task_id,status='failed');res=rt.resume(out.task_id,'Now send it to Jane.')
            self.assertEqual(res.status.value,'waiting_approval');self.assertIn('send_email',res.plan.restricted_actions);self.assertEqual(len(rt.db.list_resume_instructions(out.task_id)),1);rt.db.close()
    def test_unchanged_resume_reuses_primary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rt=make_rt(root);out=rt.submit('Rewrite chapter 3 in my voice.')
            before=len(rt.db.list_runs(out.task_id));rt.db.update_task(out.task_id,status='failed');rt.resume(out.task_id);after=len(rt.db.list_runs(out.task_id));self.assertEqual(before,after);rt.db.close()
    def test_attachment_relevance_not_first_four(self):
        items=[{'name':f'{i}.txt','sha256':str(i),'text':'boring','truncated':'false'} for i in range(4)]+[{'name':'budget.txt','sha256':'5','text':'cash runway forecast revenue budget','truncated':'false'}]
        selected=select_attachment_context(items,'analyze budget cash runway')
        self.assertIn('budget.txt',[x['name'] for x in selected])
    def test_managed_attachment_survives_source_delete(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'note.txt';src.write_text('chapter notes');rt=make_rt(root);out=rt.submit('Rewrite chapter 3 from notes.',files=[str(src)]);src.unlink();rt.db.update_task(out.task_id,status='failed');res=rt.resume(out.task_id);self.assertEqual(res.status.value,'completed');rt.db.close()
    def test_path_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root=Path(d);p=Path(outside)/'secret.txt';p.write_text('secret');rt=make_rt(root)
            with self.assertRaises(PermissionError):rt.submit('Read notes',files=[str(p)])
            rt.db.close()

class RecordingProvider(MockProvider):
    def __init__(self):self.calls=[]
    def generate(self,**kw):
        self.calls.append((kw.get('phase'),kw.get('system',''),[getattr(t,'capability',str(t)) for t in kw.get('tools') or []]))
        return super().generate(**kw)

class CapabilityRepairTests(unittest.TestCase):
    def test_research_web_does_not_leak_to_builder_primary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=RecordingProvider();rt=make_rt(root,p);rt.submit('Research current API behavior and then build the client in Python.')
            contrib=[c for c in p.calls if c[0]=='contribution'];primary=[c for c in p.calls if c[0]=='primary'];self.assertIn('web_research',contrib[0][2]);self.assertNotIn('web_research',primary[0][2]);self.assertIn('code_execution',primary[0][2]);rt.db.close()

class HaltThenPassProvider(MockProvider):
    def __init__(self):self.reviews=0
    def generate(self,**kw):
        if kw.get('phase') in {'review','review_final'}:
            self.reviews+=1
            return ProviderResult(('HALT\nold issue' if self.reviews==1 else 'PASS\ncorrected'),kw.get('model','mock'))
        return super().generate(**kw)

class ReviewBindingTests(unittest.TestCase):
    def test_halt_review_not_reused_after_changed_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=HaltThenPassProvider();rt=make_rt(root,p);out=rt.submit('Build a budget and cash runway forecast.')
            self.assertEqual(out.status.value,'blocked');res=rt.resume(out.task_id,'Correct the assumptions and recalculate.')
            self.assertEqual(res.status.value,'completed');self.assertEqual(p.reviews,2);rt.db.close()

if __name__=='__main__':unittest.main()
