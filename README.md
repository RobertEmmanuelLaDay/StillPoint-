# StillPoint

Company operating system for Robert Emmanuel LaDay.

StillPoint is the company runtime. Grok/xAI is a provider, not the owner of state.

## Run

```bash
export STILLPOINT_ROOT=$PWD
python -m stillpoint.cli status
python -m stillpoint.cli submit "Rewrite chapter 3 in my voice."
python -m stillpoint.cli approve TASK_ID
```

Provider: `STILLPOINT_PROVIDER=mock` (default) or `xai` with `XAI_API_KEY`.

State: `state/company.sqlite` (created on first use).

## Test

```bash
python -m unittest discover -s tests -v
```

## Evaluate

```bash
python eval/run_eval.py
```

Frozen corpora in `eval/` are not edited during development.

## Layout

- `stillpoint/` runtime, authority, providers, adapters
- `config/agents.json` jurisdictions
- `migrations/` schema history (also applied by `CompanyDB`)
- `eval/` behavioral evaluator + frozen 50 + frozen shadow 20
- `tests/` consolidated unit/integration tests

## Authority

`stillpoint.authority` classifies external action family, mode, and target.
Planner/policy may not weaken a required restriction.

## Unimplemented

No live email, pay, sign, publish, or destroy adapters.
Approved external work stops at `ready_for_action`.
