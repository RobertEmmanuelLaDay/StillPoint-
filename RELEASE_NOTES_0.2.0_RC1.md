# StillPoint Core 0.2.0-rc1

StillPoint Core 0.2.0-rc1 is the first release candidate to include the Temporal Authority / Continuing Evidence architecture as enforceable runtime state.

## Governing execution rules

The existing invariant remains:

> capacity ≠ permission ≠ execution ≠ completion

This release adds enforceable temporal distinctions:

> knowledge ≠ ownership  
> description ≠ identity  
> prediction ≠ permission  
> confidence ≠ jurisdiction  
> past truth ≠ permanent authority  
> evidence ≠ warrant  
> release ≠ amnesia

Claims, evidence, warrants, external actions, completion, release, and re-entry are now separate durable concepts.

## Temporal authority

The runtime now supports:

- durable time-indexed claims with provenance, confidence when applicable, truth state, subject mode, supersession, expiration, and effective periods;
- continuing evidence ingress without rewriting earlier historical truth;
- explicit claim-to-warrant separation;
- prediction firewalls that prohibit confidence or model output from self-authorizing action;
- action/domain/scope/time-bounded warrants;
- active, review-required, expired, revoked, completed, superseded, and released warrant states;
- durable warrant-transition receipts;
- explicit cross-domain evidence bridges;
- release without deletion of evidence or history;
- re-entry evaluations that preserve prior receipts;
- dynamic-subject re-entry without forcing static subjects into endless mutability;
- founder, administrator, and provider identities with no bypass around warrant state.

## Runtime integration

Restricted external ActionRequests are bound to temporal warrants as well as exact CEO approval, artifact identity, action identity, adapter identity, and evidence requirements.

A non-current warrant cannot be revived by approval. A changed factual basis can block live actions across task boundaries. If authority changes while an adapter is executing, the external result is preserved, but StillPoint will not falsely mark the action completed.

Explicitly attaching new factual claims to an existing pending action invalidates prior approval and requires reapproval.

## Operator surface

The CLI now exposes claims, evidence, warrants, warrant history, claim binding, revocation, release, and re-entry operations under:

`stillpoint temporal ...`

The normal task inspection surface includes temporal warrants for each action, and `stillpoint doctor` checks the temporal schema.

## Persistence

Schema version: 6

New migrations since 0.1.0-rc1:

- `005_temporal_authority.sql`
- `006_temporal_warrant_events.sql`

Canonical and packaged migration mirrors remain identical.

## Verification

Release-candidate precursor 0.2.0a2 earned:

- 205/205 unit, integration, security, recovery, temporal, CLI, and end-to-end tests;
- Python 3.11 green;
- Python 3.13 green;
- raw evaluator: 40/50, score 97.0;
- calibrated evaluator: 48/50, score 99.4;
- shadow calibrated evaluator: 9/20, score 93.3;
- approval precision: 100%;
- action truthfulness: 100%;
- classified release gate: PASS.

The frozen evaluator corpora were not changed to obtain these results.

## Deployment boundary

No production email, publishing, payment, signing, deletion, or destructive adapter is enabled in this release candidate. This is intentional. Approved external work without a live adapter remains `ready_for_action`, never falsely completed.

No provider owns StillPoint state. xAI/Grok or another compatible provider may supply model intelligence; StillPoint retains its own durable authority, evidence, task, artifact, approval, action, and temporal state.
