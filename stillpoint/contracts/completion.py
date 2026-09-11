from __future__ import annotations

import re

from .models import CLAIMED_COMPLETION_PATTERNS


def output_claims_external_completion(text: str) -> bool:
    if not text:
        return False
    return any(re.search(pattern, text, re.I) for pattern in CLAIMED_COMPLETION_PATTERNS)


def forbid_complete_if_claimed(text: str, task_status_would_be: str) -> str:
    """If the model claims it already acted, do not mark completed."""
    if task_status_would_be == "completed" and output_claims_external_completion(text):
        return "blocked"
    return task_status_would_be
