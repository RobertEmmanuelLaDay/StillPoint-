from __future__ import annotations

import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_attachment(path: str | Path, max_chars: int = 200_000) -> dict[str, str]:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(str(p))
    text = p.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return {
        "path": str(p),
        "name": p.name,
        "sha256": sha256(p),
        "text": text,
        "truncated": str(len(p.read_text(encoding="utf-8", errors="replace")) > max_chars).lower(),
    }
