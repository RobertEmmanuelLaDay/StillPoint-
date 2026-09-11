from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HASH_FILE = HERE / "corpus_hashes.json"
FROZEN_50 = HERE / "stillpoint_adversarial_50.jsonl"
SHADOW_20 = HERE / "shadow_20.jsonl"


class CorpusIntegrityError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_hashes() -> dict[str, str]:
    raw = json.loads(HASH_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CorpusIntegrityError("corpus_hashes.json must be an object")
    return {str(k): str(v) for k, v in raw.items()}


def verify_file(path: Path, expected_sha256: str) -> str:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise CorpusIntegrityError(
            f"frozen corpus drift: {path.name}: expected {expected_sha256}, got {actual}"
        )
    return actual


def verify_frozen_corpora() -> dict[str, str]:
    expected = expected_hashes()
    required = {
        FROZEN_50.name: FROZEN_50,
        SHADOW_20.name: SHADOW_20,
    }
    verified: dict[str, str] = {}
    for name, path in required.items():
        if name not in expected:
            raise CorpusIntegrityError(f"missing expected corpus hash: {name}")
        if not path.exists():
            raise CorpusIntegrityError(f"missing frozen corpus: {path}")
        verified[name] = verify_file(path, expected[name])
    return verified


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorpusIntegrityError(f"invalid JSONL in {path.name}:{line_no}: {exc}") from exc
        if not isinstance(item, dict):
            raise CorpusIntegrityError(f"non-object case in {path.name}:{line_no}")
        rows.append(item)
    return rows


def load_frozen_50() -> list[dict]:
    verify_frozen_corpora()
    return load_jsonl(FROZEN_50)


def load_shadow_20() -> list[dict]:
    verify_frozen_corpora()
    return load_jsonl(SHADOW_20)
