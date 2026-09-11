# StillPoint behavioral evaluation

The evaluator measures runtime behavior without changing production state or rewriting its exam.

## Frozen corpora

- `stillpoint_adversarial_50.jsonl` — original 50-case acceptance corpus
- `shadow_20.jsonl` — frozen shadow corpus
- `corpus_hashes.json` — SHA-256 identities for both corpora

Normal evaluation verifies these hashes and fails loudly if either corpus drifts. The JSONL files are consumed as data; they are not regenerated during a run.

## Commands

```bash
python eval/run_eval.py
python eval/run_calibrated.py
python eval/run_shadow.py
python eval/release_gate.py
```

`run_eval.py` preserves the original/raw tool-accounting semantics for historical comparability. `run_calibrated.py` additionally evaluates provider-independent semantic capabilities so aliases such as `web_research` and a provider's `web_search` representation are not counted as separate tools.

`release_gate.py` uses calibrated capability scoring and allows only failures explicitly classified as `evaluation_expectation_conflict` in `failure_classification.json`. Any new/unclassified failure fails the release gate.

Live-provider runs are optional and require credentials; ordinary unit tests and release gating do not.

## Outputs

Generated reports are written under `eval/results/` and are ignored by Git except for the placeholder file. The current release checkpoint records the exact aggregate scores and corpus hashes.
