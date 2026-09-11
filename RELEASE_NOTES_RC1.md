# StillPoint Core 0.1.0-rc1

Base: `4d2299e2948e19507e1ccffdcd9255bb4ab285a0`

This release candidate turns the frozen V5/consolidation baseline into a provider-independent, recoverable company-runtime core with durable authority/action state.

Key earned changes include unified deterministic + optional semantic authority, preservation of compound restricted actions, exact artifact-bound `ActionRequest` approval, evidence-gated `ActionResult` completion, safe resume/replanning, stage fingerprints and idempotency, contributor-scoped capabilities, provider provenance, managed attachment storage and DOCX/HTML ingestion, memory promotion discipline, task budgets, ordered SQL migrations, CLI operations, immutable evaluator corpora, release classification, packaging, and CI.

No live production email, publication, payment, signing, deletion, or destructive adapter is enabled. No real-world consequential action was executed during this build.

The frozen evaluator still contains expectation conflicts. They remain frozen and are classified rather than edited. See `eval/FAILURE_CLASSIFICATION.md` and `eval/failure_classification.json`.
