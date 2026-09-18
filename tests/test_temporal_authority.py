import tempfile
import unittest
from pathlib import Path

from stillpoint.adapters.registry import ActionAdapterRegistry, DryRunActionAdapter
from stillpoint.contracts.models import ActionEvidence, ActionResult
from stillpoint.db import CompanyDB
from stillpoint.providers.mock import MockProvider
from stillpoint.registry import AgentRegistry
from stillpoint.runtime import CompanyRuntime
from stillpoint.temporal import TemporalAuthorityLedger

ROOT = Path(__file__).resolve().parents[1]


class ReceiptAdapter:
    name = "temporal-receipt"
    action_types = ("send_email", "publish", "social_post", "spend", "sign", "delete", "other_external")

    def can_execute(self, request):
        return True

    def execute(self, request):
        criterion = request.success_criteria[0]
        return ActionResult(
            action_id=request.action_id,
            status="succeeded",
            evidence=[ActionEvidence(type=criterion, sha256="receipt", satisfies=criterion)],
            adapter=self.name,
            external_id="temporal-test",
        )


def make_runtime(tmp):
    return CompanyRuntime(
        root=tmp,
        db=CompanyDB(tmp / "db.sqlite"),
        registry=AgentRegistry(ROOT / "config" / "agents.json"),
        provider=MockProvider(),
        default_model="mock",
        smart_routing=False,
    )


class TemporalAuthorityTests(unittest.TestCase):
    def test_historical_truth_survives_supersession(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            old = ledger.record_claim(
                subject="person:1", predicate="status", value="A", domain="identity",
                source="record", observed_at="2026-01-01T00:00:00+00:00", truth_state="supported"
            )
            new = ledger.record_claim(
                subject="person:1", predicate="status", value="B", domain="identity",
                source="record", observed_at="2026-02-01T00:00:00+00:00", truth_state="supported",
                supersedes_claim_id=old,
            )
            self.assertEqual(ledger.get_claim(old)["status"], "superseded")
            self.assertEqual(ledger.get_claim(old)["value_json"], '"A"')
            self.assertEqual(ledger.get_claim(new)["status"], "current")
            db.close()

    def test_unknown_is_not_coerced_to_false(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="person:1", predicate="future", value=None, domain="risk",
                source="model", truth_state="unknown", claim_kind="prediction"
            )
            row = ledger.get_claim(claim)
            self.assertEqual(row["truth_state"], "unknown")
            self.assertEqual(row["value_json"], "null")
            db.close()

    def test_material_new_evidence_triggers_warrant_review(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="person:1", predicate="eligible", value=True, domain="benefit",
                source="caseworker", truth_state="supported"
            )
            warrant = ledger.issue_warrant(
                subject="person:1", domain="benefit", authorized_actions=["approve"],
                scope=["case:1"], basis_type="policy", basis="benefit rule 7",
                issued_by="reviewer", claim_ids=[claim]
            )
            ev = ledger.record_evidence(
                subject="person:1", domain="benefit", source="new-record",
                payload={"eligible": False}
            )
            ledger.link_evidence(claim, ev, "contradicts")
            self.assertEqual(ledger.get_warrant(warrant)["status"], "review_required")
            self.assertFalse(ledger.warrant_authorizes(
                warrant, action_type="approve", domain="benefit", scope=["case:1"]
            ))
            db.close()

    def test_high_confidence_prediction_cannot_self_authorize(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="person:1", predicate="risk", value=0.9999, domain="risk",
                source="model", confidence=0.9999, truth_state="supported", claim_kind="prediction"
            )
            with self.assertRaises(ValueError):
                ledger.issue_warrant(
                    subject="person:1", domain="risk", authorized_actions=["restrain"],
                    scope=["person:1"], basis_type="prediction", basis="model score",
                    issued_by="model", claim_ids=[claim]
                )
            db.close()

    def test_bare_claim_cannot_self_authorize(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            with self.assertRaises(ValueError):
                ledger.issue_warrant(
                    subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                    basis_type="claim", basis="claim exists", issued_by="system"
                )
            db.close()

    def test_domain_and_scope_are_contained(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            warrant = ledger.issue_warrant(
                subject="person:1", domain="medical", authorized_actions=["read_record"],
                scope=["chart:1"], basis_type="policy", basis="care policy", issued_by="clinician"
            )
            self.assertTrue(ledger.warrant_authorizes(
                warrant, action_type="read_record", domain="medical", scope=["chart:1"]
            ))
            self.assertFalse(ledger.warrant_authorizes(
                warrant, action_type="read_record", domain="employment", scope=["chart:1"]
            ))
            self.assertFalse(ledger.warrant_authorizes(
                warrant, action_type="read_record", domain="medical", scope=["chart:1", "payroll"]
            ))
            db.close()

    def test_expired_warrant_cannot_authorize(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            warrant = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="policy", basis="bounded rule", issued_by="system",
                issued_at="2026-01-01T00:00:00+00:00",
                effective_from="2026-01-01T00:00:00+00:00",
                expires_at="2026-01-02T00:00:00+00:00",
            )
            self.assertFalse(ledger.warrant_authorizes(
                warrant, action_type="act", domain="d", scope=["x"],
                now_iso="2026-01-03T00:00:00+00:00"
            ))
            self.assertEqual(ledger.get_warrant(warrant)["status"], "expired")
            db.close()

    def test_revoked_and_completed_warrants_cannot_authorize(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            one = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="policy", basis="rule", issued_by="system"
            )
            two = ledger.issue_warrant(
                subject="y", domain="d", authorized_actions=["act"], scope=["y"],
                basis_type="policy", basis="rule", issued_by="system"
            )
            ledger.revoke_warrant(one, "changed conditions")
            ledger.complete_warrant(two)
            self.assertFalse(ledger.warrant_authorizes(one, action_type="act", domain="d", scope=["x"]))
            self.assertFalse(ledger.warrant_authorizes(two, action_type="act", domain="d", scope=["y"]))
            db.close()

    def test_release_preserves_record_and_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="person:1", predicate="event", value="occurred", domain="history",
                source="archive", truth_state="supported", claim_kind="historical"
            )
            ev = ledger.record_evidence(
                subject="person:1", domain="history", source="archive", payload={"receipt": "r1"}
            )
            ledger.link_evidence(claim, ev, "supports")
            warrant = ledger.issue_warrant(
                subject="person:1", domain="history", authorized_actions=["review"], scope=["record:1"],
                basis_type="manual_review", basis="bounded review", issued_by="reviewer", claim_ids=[claim]
            )
            ledger.complete_warrant(warrant)
            ledger.release_warrant(warrant, "review complete")
            self.assertEqual(ledger.get_warrant(warrant)["status"], "released")
            self.assertEqual(len(ledger.list_claims(subject="person:1")), 1)
            self.assertEqual(len(ledger.list_evidence(subject="person:1")), 1)
            db.close()

    def test_cross_domain_claim_use_requires_explicit_bridge(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="person:1", predicate="diagnosis", value="x", domain="medical",
                source="doctor", truth_state="supported"
            )
            with self.assertRaises(ValueError):
                ledger.issue_warrant(
                    subject="person:1", domain="employment", authorized_actions=["schedule"],
                    scope=["job:1"], basis_type="policy", basis="work rule", issued_by="manager",
                    claim_ids=[claim]
                )
            warrant = ledger.issue_warrant(
                subject="person:1", domain="employment", authorized_actions=["schedule"],
                scope=["job:1"], basis_type="policy", basis="work rule", issued_by="manager",
                claim_ids=[claim], claim_bridge="explicit medical-to-employment accommodation bridge"
            )
            self.assertTrue(ledger.warrant_authorizes(
                warrant, action_type="schedule", domain="employment", scope=["job:1"]
            ))
            db.close()

    def test_reentry_preserves_prior_decision_and_can_bind_new_warrant(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            old = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="policy", basis="old rule", issued_by="system"
            )
            ledger.complete_warrant(old)
            ev = ledger.record_evidence(subject="x", domain="d", source="new", payload={"changed": True})
            review = ledger.open_reentry(
                subject="x", domain="d", reason="material new evidence",
                prior_warrant_id=old, trigger_evidence_id=ev
            )
            new = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="manual_review", basis="re-evaluated current facts", issued_by="reviewer"
            )
            ledger.resolve_reentry(review, disposition="new_warrant", rationale="conditions changed", new_warrant_id=new)
            rows = ledger.list_reentries(subject="x")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["prior_warrant_id"], old)
            self.assertEqual(rows[0]["new_warrant_id"], new)
            self.assertEqual(ledger.get_warrant(old)["status"], "completed")
            db.close()

    def test_founder_identity_does_not_bypass_expiration(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            warrant = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="ceo_instruction", basis="CEO instruction",
                issued_by="Robert Emmanuel LaDay",
                issued_at="2026-01-01T00:00:00+00:00",
                effective_from="2026-01-01T00:00:00+00:00",
                expires_at="2026-01-02T00:00:00+00:00",
            )
            self.assertFalse(ledger.warrant_authorizes(
                warrant, action_type="act", domain="d", scope=["x"],
                now_iso="2026-01-03T00:00:00+00:00"
            ))
            db.close()

    def test_runtime_restricted_action_gets_explicit_warrant(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            action = rt.db.list_action_requests(out.task_id)[0]
            warrants = rt.temporal.list_action_warrants(action["id"])
            self.assertEqual(len(warrants), 1)
            self.assertEqual(warrants[0]["status"], "active")
            self.assertEqual(warrants[0]["domain"], "external_action")
            rt.db.close()

    def test_runtime_revoked_warrant_blocks_approved_action(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            rt.approve(out.task_id)
            action = rt.db.list_action_requests(out.task_id)[0]
            warrant = rt.temporal.list_action_warrants(action["id"])[0]
            rt.temporal.revoke_warrant(warrant["id"], "conditions changed")
            with self.assertRaises(PermissionError):
                rt.execute_action(action["id"], ActionAdapterRegistry([ReceiptAdapter()]))
            rt.db.close()

    def test_runtime_completed_action_completes_warrant(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            rt.approve(out.task_id)
            action = rt.db.list_action_requests(out.task_id)[0]
            rt.execute_action(action["id"], ActionAdapterRegistry([ReceiptAdapter()]))
            warrant = rt.temporal.list_action_warrants(action["id"])[0]
            self.assertEqual(warrant["status"], "completed")
            rt.db.close()

    def test_dry_run_never_completes_warrant(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            rt.approve(out.task_id)
            action = rt.db.list_action_requests(out.task_id)[0]
            rt.execute_action(action["id"], ActionAdapterRegistry([DryRunActionAdapter()]))
            warrant = rt.temporal.list_action_warrants(action["id"])[0]
            self.assertEqual(warrant["status"], "active")
            rt.db.close()

    def test_review_required_warrant_blocks_prior_approval(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            rt.approve(out.task_id)
            action = rt.db.list_action_requests(out.task_id)[0]
            rt.temporal.mark_action_warrants_review_required(action["id"], reason="new evidence")
            with self.assertRaises(PermissionError):
                rt.execute_action(action["id"], ActionAdapterRegistry([ReceiptAdapter()]))
            self.assertEqual(rt.db.get_task(out.task_id)["status"], "ready_for_action")
            rt.db.close()


    def test_terminal_runtime_warrant_is_not_silently_reissued(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            action = rt.db.list_action_requests(out.task_id)[0]
            warrant = rt.temporal.list_action_warrants(action["id"])[0]
            rt.temporal.revoke_warrant(warrant["id"], "changed conditions")
            returned = rt.temporal.ensure_runtime_warrant(
                action_id=action["id"], task_id=out.task_id, action_type=action["action_type"],
                target=action["target"], scope=__import__("json").loads(action["scope_json"]),
                authority_revision=action["authority_revision"], issued_at=action["issued_at"],
                expires_at=action["expires_at"],
            )
            self.assertEqual(returned, warrant["id"])
            self.assertEqual(len(rt.temporal.list_action_warrants(action["id"])), 1)
            rt.db.close()

    def test_supporting_claim_expiry_blocks_warrant_at_use_time(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="x", predicate="eligible", value=True, domain="d", source="record",
                truth_state="supported", expires_at="2026-01-02T00:00:00+00:00"
            )
            warrant = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="policy", basis="rule", issued_by="reviewer", claim_ids=[claim],
                issued_at="2026-01-01T00:00:00+00:00"
            )
            self.assertFalse(ledger.warrant_authorizes(
                warrant, action_type="act", domain="d", scope=["x"],
                now_iso="2026-01-03T00:00:00+00:00"
            ))
            self.assertEqual(ledger.get_warrant(warrant)["status"], "review_required")
            db.close()

    def test_evidence_cannot_silently_cross_domains(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            claim = ledger.record_claim(
                subject="x", predicate="diagnosis", value="y", domain="medical",
                source="doctor", truth_state="supported"
            )
            ev = ledger.record_evidence(
                subject="x", domain="employment", source="manager", payload={"fact": "z"}
            )
            with self.assertRaises(ValueError):
                ledger.link_evidence(claim, ev, "supports")
            db.close()

    def test_category_confidence_and_repeated_predictions_do_not_mint_warrants(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            for i in range(5):
                ledger.record_claim(
                    subject="x", predicate=f"risk:{i}", value=0.999999, domain="risk",
                    source="model", confidence=0.999999, truth_state="supported", claim_kind="prediction"
                )
            with self.assertRaises(ValueError):
                ledger.issue_warrant(
                    subject="x", domain="risk", authorized_actions=["restrain"], scope=["x"],
                    basis_type="classification", basis="category membership", issued_by="model"
                )
            self.assertEqual(ledger.list_warrants(subject="x"), [])
            db.close()

    def test_privileged_identity_does_not_bypass_warrant_state(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            for issuer in ("administrator", "provider:xai", "Robert Emmanuel LaDay"):
                warrant = ledger.issue_warrant(
                    subject=issuer, domain="d", authorized_actions=["act"], scope=[issuer],
                    basis_type="delegation", basis="bounded delegation", issued_by=issuer
                )
                ledger.revoke_warrant(warrant, "revoked")
                self.assertFalse(ledger.warrant_authorizes(
                    warrant, action_type="act", domain="d", scope=[issuer]
                ))
            db.close()

    def test_release_transition_keeps_terminal_history(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            warrant = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="policy", basis="rule", issued_by="reviewer"
            )
            ledger.complete_warrant(warrant)
            ledger.release_warrant(warrant, "authority released")
            transitions = [(r["from_status"], r["to_status"]) for r in ledger.list_warrant_events(warrant)]
            self.assertIn(("active", "completed"), transitions)
            self.assertIn(("completed", "released"), transitions)
            db.close()


    def test_terminal_warrant_link_does_not_rewrite_completed_history(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            ledger = TemporalAuthorityLedger(db)
            old = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="policy", basis="old", issued_by="reviewer"
            )
            ledger.complete_warrant(old)
            new = ledger.issue_warrant(
                subject="x", domain="d", authorized_actions=["act"], scope=["x"],
                basis_type="manual_review", basis="new facts", issued_by="reviewer",
                supersedes_warrant_id=old
            )
            self.assertEqual(ledger.get_warrant(old)["status"], "completed")
            self.assertEqual(ledger.get_warrant(new)["supersedes_warrant_id"], old)
            db.close()

    def test_review_before_approval_blocks_and_opens_resume_path(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            action = rt.db.list_action_requests(out.task_id)[0]
            rt.temporal.mark_action_warrants_review_required(action["id"], reason="new evidence")
            with self.assertRaises(RuntimeError):
                rt.approve(out.task_id)
            self.assertEqual(rt.db.get_task(out.task_id)["status"], "blocked")
            self.assertEqual(rt.db.get_action_request(action["id"])["status"], "review_required")
            rt.db.close()

    def test_review_after_approval_blocks_execution_and_opens_resume_path(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            rt.approve(out.task_id)
            action = rt.db.list_action_requests(out.task_id)[0]
            rt.temporal.mark_action_warrants_review_required(action["id"], reason="new evidence")
            with self.assertRaises(Exception) as caught:
                rt.execute_action(action["id"], ActionAdapterRegistry([ReceiptAdapter()]))
            self.assertIn("warrant", str(caught.exception).lower())
            self.assertEqual(rt.db.get_task(out.task_id)["status"], "blocked")
            self.assertEqual(rt.db.get_action_request(action["id"])["status"], "review_required")
            rt.db.close()

    def test_evidence_change_during_adapter_execution_never_false_completes(self):
        with tempfile.TemporaryDirectory() as d:
            rt = make_runtime(Path(d))
            out = rt.submit("Send this note to the printer.")
            rt.approve(out.task_id)
            action = rt.db.list_action_requests(out.task_id)[0]

            class EvidenceChangesDuringDispatch(ReceiptAdapter):
                name = "temporal-race-test"
                def execute(self, request):
                    rt.temporal.mark_action_warrants_review_required(
                        request.action_id, reason="material evidence arrived during execution"
                    )
                    return super().execute(request)

            result = rt.execute_action(
                action["id"], ActionAdapterRegistry([EvidenceChangesDuringDispatch()])
            )
            self.assertEqual(result["status"], "review_required")
            self.assertEqual(rt.db.get_task(out.task_id)["status"], "blocked")
            self.assertEqual(rt.db.get_action_request(action["id"])["status"], "review_required")
            self.assertEqual(len(rt.db.list_action_results(action["id"])), 1)
            rt.db.close()

    def test_schema_version_six_contains_temporal_tables(self):
        with tempfile.TemporaryDirectory() as d:
            db = CompanyDB(Path(d) / "db.sqlite")
            self.assertEqual(db.schema_version, 6)
            tables = {r[0] for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for name in {
                "temporal_claims", "temporal_evidence", "temporal_claim_evidence",
                "temporal_warrants", "temporal_action_warrants", "temporal_evaluations"
            }:
                self.assertIn(name, tables)
            db.close()


if __name__ == "__main__":
    unittest.main()
