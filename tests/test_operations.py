import tempfile
import unittest
import zipfile
from pathlib import Path

from stillpoint.adapters.registry import ActionAdapterRegistry, DryRunActionAdapter
from stillpoint.db import CompanyDB
from stillpoint.file_loader import read_attachment
from stillpoint.providers.mock import MockProvider
from stillpoint.registry import AgentRegistry
from stillpoint.runtime import CompanyRuntime

ROOT=Path(__file__).resolve().parents[1]

class OperationTests(unittest.TestCase):
    def make(self,tmp):return CompanyRuntime(root=tmp,db=CompanyDB(tmp/'db.sqlite'),registry=AgentRegistry(ROOT/'config'/'agents.json'),provider=MockProvider(),default_model='mock',smart_routing=False)
    def test_html_text_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.html';p.write_text('<h1>Hello</h1><script>evil()</script><p>World</p>')
            item=read_attachment(p)
            self.assertIn('Hello',item['text']);self.assertIn('World',item['text']);self.assertNotIn('evil',item['text'])
    def test_docx_text_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.docx'
            xml='<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p></w:body></w:document>'
            with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml',xml)
            self.assertEqual(read_attachment(p)['text'],'Hello DOCX')
    def test_memory_requires_ceo_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            rt=self.make(Path(d))
            with self.assertRaises(PermissionError):rt.promote_memory('x','y',source='model')
            rt.promote_memory('canon','value',task_id='t1')
            row=rt.db.get_memory(['company'])[0]
            self.assertEqual(row['source'],'CEO');self.assertEqual(row['confidence'],'verified');self.assertEqual(row['task_id'],'t1')
            rt.db.close()

    def test_adapter_result_must_bind_exact_action_request(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);rt=self.make(tmp)
            out=rt.submit('Send this note to the printer.');rt.approve(out.task_id)
            action=rt.db.list_action_requests(out.task_id)[0]
            from stillpoint.contracts.models import ActionEvidence, ActionResult
            class WrongActionResult:
                name='real-test';action_types=('send_email',)
                def can_execute(self,request):return True
                def execute(self,request):
                    criterion=request.success_criteria[0]
                    return ActionResult(action_id='different-action',status='succeeded',evidence=[ActionEvidence(type=criterion,sha256='x',satisfies=criterion)],adapter=self.name)
            with self.assertRaises(ValueError):
                rt.execute_action(action['id'],ActionAdapterRegistry([WrongActionResult()]))
            self.assertEqual(rt.db.list_action_results(action['id']),[])
            self.assertEqual(rt.db.get_action_request(action['id'])['status'],'ready_for_action')
            rt.db.close()

    def test_registry_records_selected_adapter_identity(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);rt=self.make(tmp)
            out=rt.submit('Send this note to the printer.');rt.approve(out.task_id)
            action=rt.db.list_action_requests(out.task_id)[0]
            from stillpoint.contracts.models import ActionEvidence, ActionResult
            class HonestExecutorForgedLabel:
                name='real-test';action_types=('send_email',)
                def can_execute(self,request):return True
                def execute(self,request):
                    criterion=request.success_criteria[0]
                    return ActionResult(action_id=request.action_id,status='succeeded',evidence=[ActionEvidence(type=criterion,sha256='x',satisfies=criterion)],adapter='forged-label')
            result=rt.execute_action(action['id'],ActionAdapterRegistry([HonestExecutorForgedLabel()]))
            self.assertEqual(result['status'],'completed')
            persisted=rt.db.list_action_results(action['id'])[-1]
            self.assertEqual(persisted['adapter'],'real-test')
            rt.db.close()
    def test_dry_run_adapter_never_completes(self):
        with tempfile.TemporaryDirectory() as d:
            rt=self.make(Path(d));out=rt.submit('Send this note to the printer.')
            rt.approve(out.task_id)
            action=rt.db.list_action_requests(out.task_id)[0]
            result=rt.execute_action(action['id'],ActionAdapterRegistry([DryRunActionAdapter()]))
            self.assertEqual(result['status'],'ready_for_action')
            self.assertEqual(rt.db.get_task(out.task_id)['status'],'ready_for_action')
            rt.db.close()

if __name__=='__main__':unittest.main()

class StaleApprovalTests(unittest.TestCase):
    def test_new_artifact_version_stales_old_action_request(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);rt=OperationTests().make(tmp)
            out=rt.submit('Send this note to the printer.')
            req=rt.db.list_action_requests(out.task_id)[0]
            old_ref=__import__('json').loads(req['artifact_refs_json'])[0]
            latest=rt.db.list_artifacts(out.task_id)[-1]
            rt.db.add_artifact(task_id=out.task_id,kind=latest['kind'],name='changed.txt',sha256='newhash',produced_by_run_id=latest['produced_by_run_id'],phase='revision')
            with self.assertRaises(RuntimeError):rt.approve(out.task_id)
            self.assertEqual(rt.db.get_action_request(req['id'])['status'],'stale')
            rt.db.close()

class RetryBoundaryTests(unittest.TestCase):
    def test_null_adapter_does_not_consume_future_real_execution(self):
        with tempfile.TemporaryDirectory() as d:
            tmp=Path(d);rt=OperationTests().make(tmp)
            out=rt.submit('Send this note to the printer.');rt.approve(out.task_id)
            action=rt.db.list_action_requests(out.task_id)[0]
            first=rt.execute_action(action['id'],ActionAdapterRegistry([]))
            self.assertEqual(first['status'],'ready_for_action')
            from stillpoint.contracts.models import ActionEvidence, ActionResult
            class RealReceipt:
                name='real-test';action_types=('send_email',)
                def can_execute(self,request):return True
                def execute(self,request):
                    c=request.success_criteria[0]
                    return ActionResult(action_id=request.action_id,status='succeeded',evidence=[ActionEvidence(type=c,sha256='x',satisfies=c)],adapter=self.name)
            second=rt.execute_action(action['id'],ActionAdapterRegistry([RealReceipt()]))
            self.assertEqual(second['status'],'completed')
            rt.db.close()

    def test_action_request_permitted_without_now_still_checks_expiry(self):
        from stillpoint.contracts.models import ActionRequest
        req=ActionRequest(
            action_id='a',task_id='t',action_type='send_email',target='x',scope=[],artifact_refs=[],
            approval_required=True,approval_id='approval',expires_at='2000-01-01T00:00:00+00:00',
            issued_at='1999-01-01T00:00:00+00:00',idempotency_key='k',success_criteria=['receipt']
        )
        self.assertFalse(req.permitted())
