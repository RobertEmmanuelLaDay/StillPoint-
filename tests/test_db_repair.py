import sqlite3,tempfile,unittest
from pathlib import Path
from stillpoint.db import CompanyDB
from stillpoint.contracts.models import ActionRequest,ArtifactRef

class DBRepairTests(unittest.TestCase):
    def test_fresh_db_migrates_to_6(self):
        with tempfile.TemporaryDirectory() as d:
            db=CompanyDB(Path(d)/"x.sqlite")
            self.assertEqual(db.schema_version,6);db.close()
    def test_future_db_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.sqlite"; c=sqlite3.connect(p); c.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL)"); c.execute("INSERT INTO schema_migrations VALUES(99,'x')");c.commit();c.close()
            with self.assertRaises(RuntimeError):CompanyDB(p)
    def test_stage_key_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            db=CompanyDB(Path(d)/"x.sqlite");t=db.create_task("x");a=db.add_run(t,"builder","primary","one",stage_key="s");b=db.add_run(t,"builder","primary","two",stage_key="s");self.assertEqual(a,b);self.assertEqual(len(db.list_runs(t)),1);db.close()
    def test_artifact_versions_supersede(self):
        with tempfile.TemporaryDirectory() as d:
            db=CompanyDB(Path(d)/"x.sqlite");t=db.create_task("x");r=db.add_run(t,"author","primary","x");a1=db.add_artifact(task_id=t,kind="prose",name="a",sha256="1",produced_by_run_id=r,phase="primary");a2=db.add_artifact(task_id=t,kind="prose",name="b",sha256="2",produced_by_run_id=r,phase="revision");rows=db.list_artifacts(t);self.assertEqual(rows[1]["version"],2);self.assertEqual(rows[1]["supersedes"],a1);db.close()
    def test_action_approval_binding(self):
        with tempfile.TemporaryDirectory() as d:
            db=CompanyDB(Path(d)/"x.sqlite");t=db.create_task("send");req=ActionRequest("a",t,"send_email","jane",["mail"],[ArtifactRef("x","abc")],True,None,"2099-01-01T00:00:00+00:00","2026-01-01T00:00:00+00:00","idem",["smtp-id"],authority_revision="rev");db.add_action_request(req);ap=db.add_approval(t,"approved");db.bind_action_approval("a",ap);row=db.list_action_requests(t)[0];self.assertEqual(row["approval_id"],ap);self.assertEqual(row["status"],"ready_for_action");db.close()

if __name__=='__main__':unittest.main()

class ApprovalBindingIsolationTests(unittest.TestCase):
    def test_action_request_cannot_borrow_approval_from_another_task(self):
        from stillpoint.contracts.models import ActionRequest, ArtifactRef
        with tempfile.TemporaryDirectory() as d:
            db=CompanyDB(Path(d)/"x.sqlite")
            task_a=db.create_task("send A")
            task_b=db.create_task("send B")
            req=ActionRequest(
                "action-a",task_a,"send_email","jane",["mail"],[ArtifactRef("x","abc")],True,None,
                "2099-01-01T00:00:00+00:00","2026-01-01T00:00:00+00:00","idem-a",["delivery_receipt"],
                authority_revision="rev-a",
            )
            db.add_action_request(req)
            wrong=db.add_approval(task_b,"approved")
            with self.assertRaises(ValueError):
                db.bind_action_approval(req.action_id,wrong)
            self.assertIsNone(db.get_action_request(req.action_id)["approval_id"])
            db.close()
