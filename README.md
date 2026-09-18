# StillPoint Core

StillPoint is a provider-independent company operating-system runtime. Robert Emmanuel LaDay is the sole human CEO and final authority. The runtime coordinates durable company functions—Orchestra, Author, Press, Signal, Ledger, Research, Builder, and targeted Still Point review—without making any model or provider the company itself.

The governing execution invariant is:

> capacity ≠ permission ≠ execution ≠ completion

Drafting is not sending. Preparation is not publication. Analysis is not spending. Approval is not execution. External execution is not complete until the exact authorized action has been executed by an adapter and the required structured evidence has been recorded.

## Current release-candidate scope

The core runtime includes deterministic and optional semantic authority assessment, structured planning, contributor handoffs, targeted review, durable SQLite state, artifact versions, managed attachments, resume/recovery, action requests/results, approval binding, idempotency, task budgets, provider provenance, frozen behavioral evaluation, and a CLI/operator surface.

No production email, publishing, payment, signature, deletion, or destructive adapter is enabled in this release candidate. Approved external work without a live adapter stops at `ready_for_action`.

## Install

```bash
python -m pip install .
```

A source checkout can also be run directly with Python 3.11+.

## Configuration

Set the repository/application root:

```bash
export STILLPOINT_ROOT=$PWD
```

The default provider is the deterministic mock provider. For xAI:

```bash
export STILLPOINT_PROVIDER=xai
export XAI_API_KEY=...
export STILLPOINT_MODEL=<configured-model>
```

Provider credentials are environment configuration and must never be committed to the repository.

## CLI

```bash
python -m stillpoint.cli status
python -m stillpoint.cli doctor
python -m stillpoint.cli submit "Rewrite chapter 3 in my voice."
python -m stillpoint.cli task TASK_ID
python -m stillpoint.cli approvals
python -m stillpoint.cli approve TASK_ID
python -m stillpoint.cli reject TASK_ID
python -m stillpoint.cli resume TASK_ID --note "CEO correction"
python -m stillpoint.cli actions TASK_ID
python -m stillpoint.cli artifacts TASK_ID
```

`doctor` checks the database/schema, agent registry, managed storage, provider configuration, and frozen evaluation-corpus hashes without exposing credentials.

## State and recovery

Runtime state is stored under `state/` by default. Task attachments are copied into task-scoped managed storage and fingerprinted. Resume instructions are persisted as new instruction events and re-planned so new external authority cannot inherit a weaker prior authorization envelope. Reusable stages are bound to stage-specific fingerprints.

## Authority and external actions

Restricted actions are preserved as a set, so compound instructions such as sign + spend or publish + send cannot be collapsed into a single permission. Consequential actions create durable `ActionRequest` records bound to exact task/authority/artifact identity. CEO approval is bound to those requests. Artifact revisions or authority changes stale the affected authorization.

A task can become `completed` after external execution only when the registered adapter succeeds and structured evidence satisfies the request's exact success criteria. A null or dry-run adapter can never establish real-world completion.

## Temporal authority and continuing evidence

The temporal authority layer separates claims, evidence, warrants, actions, and historical records. A description or prediction may inform a decision, but it cannot self-authorize an external action. Warrants are explicit, domain- and scope-bound, time-aware, auditable, and independently revocable or reviewable.

Material later evidence can place a supporting warrant into `review_required` without rewriting the earlier claim out of history. Expired, revoked, completed, superseded, or released warrants cannot authorize new action. Release preserves records while ending extraordinary authority.

The runtime binds every restricted external `ActionRequest` to an explicit temporal warrant in addition to CEO approval. Approval therefore remains necessary but is no longer sufficient when the current warrant has expired, been revoked, or requires review.

## Temporal operator surface

Temporal authority is available through the operator CLI as well as the Python runtime. Operators can inspect and create claims and evidence, inspect warrants and transition receipts, explicitly bind factual claims to pending action warrants, revoke or release warrants, and open or resolve re-entry evaluations.

Examples:

```bash
python -m stillpoint.cli temporal claims --subject person:1
python -m stillpoint.cli temporal claim-add person:1 eligibility benefits caseworker true --truth-state supported --subject-mode dynamic
python -m stillpoint.cli temporal evidence-add person:1 benefits new-record '{"eligible": false}' --link CLAIM_ID:contradicts
python -m stillpoint.cli temporal warrants --subject person:1
python -m stillpoint.cli temporal warrant WARRANT_ID
python -m stillpoint.cli temporal action-bind-claims ACTION_ID CLAIM_ID
python -m stillpoint.cli temporal reentries --subject person:1
```

Material continuing evidence now propagates across task boundaries. Active actions whose factual support enters review are moved to `review_required` and their tasks are blocked for re-evaluation. Completed history stays completed; for explicitly dynamic subjects, materially contrary later evidence can open a new auditable re-entry evaluation without rewriting the old action or warrant.

## Tests

```bash
python -m unittest discover -s tests -q
```

## Behavioral evaluation

The frozen 50-case and shadow 20-case corpora are byte-frozen and guarded by SHA-256 hashes:

```bash
python eval/run_eval.py
python eval/run_calibrated.py
python eval/run_shadow.py
```

Evaluation consumes the frozen JSONL files; normal evaluator execution does not regenerate them. Remaining failures must be classified rather than repaired by changing the exam.

## Repository layout

- `stillpoint/` — runtime, policy, authority, providers, adapters, contracts
- `config/agents.json` — durable function registry
- `migrations/` — canonical ordered SQL migration history
- `stillpoint/migrations/` — verified package mirror of canonical migrations
- `eval/` — immutable behavioral corpora, scoring, reports
- `tests/` — unit, integration, recovery, security, and end-to-end tests
- `policies/COMPANY.md` — company authority boundary

## Deliberately disabled/deferred

Production credentials and live external-action adapters are deployment concerns and are not required for the core release candidate. Native provider-specific bot swarms, provider-owned company memory, and prompt-kit-only architecture are outside the StillPoint core design.
