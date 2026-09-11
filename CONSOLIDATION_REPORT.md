# CONSOLIDATION_REPORT

1. Source inputs integrated
   - V5 runtime (via Integration Packet 2 tree)
   - Integration Packet 2
   - Behavior Repair Overlay 1
   - Authority and Evaluator Packet 1 (eval calibration + authority tests)
   - Authority Integrity Patch 1.1
   - Acceptance harness evaluator + frozen 50 + frozen shadow 20

2. Files materially changed
   - Package renamed to `stillpoint`
   - `stillpoint/policy.py` joins Overlay 1 intent with authority gate (monotonic)
   - `stillpoint/cli.py` status/submit/approve/reject/resume
   - `stillpoint/authority/` from Integrity 1.1
   - `migrations/001_baseline_v5.sql`, `002_packet2_artifacts.sql`
   - Deprecated `steelpoint.py` shim

3. Migrations applied
   - Version 1: V5 tables
   - Version 2: artifacts, fingerprints, provider_response_id, usage_json, stage_key
   - Applied automatically by `CompanyDB._migrate`

4. Compatibility decisions
   - `steelpoint.py` deprecated warning shim only
   - Frozen 50 and shadow 20 not edited
   - Overlay 1 router kept; authority overlays approval intent

5. Tests run
   - `python -m unittest discover -s tests -q`

6. Exact test counts
   - 78 run, 78 passed, 0 failed

7. Evaluation scores
   - Frozen 50: 31/50 pass, score 91.3, approval 96%, action-truthfulness 96%
   - Frozen shadow 20: not re-run in this consolidation pass (corpus preserved)

8. Known failures
   - Behavioral 50 still misses some routing/tool-expectation cases (see eval/results/latest.md)
   - Authority wiring moved approval precision from Overlay-1-only 100% on that tree to 96% here — integration delta, not a corpus edit

9. Intentionally unimplemented
   - Live email/pay/sign/publish/delete adapters
   - RAG
   - Native Grok Bots
   - UI

10. Security limitations
    - Attachments fenced but not a full sandbox
    - No secrets in repo; XAI_API_KEY via env
    - Fail-closed authority is structural, not a complete language model

11. Next engineering milestone
    - Independent ChatGPT holdout audit of this frozen repo
    - Then wire ActionRequest generation from AuthorityBundle.restricted_intents

12. Git
    - Repository initialized; environment prevented a reliable commit hash from being recorded
    - Treat this zip as the frozen checkpoint
