"""Text normalization utilities."""

from __future__ import annotations

import re


def clean_text(value: str) -> str:
    """Normalize whitespace and trim text."""
    return re.sub(r"\s+", " ", (value or "").strip())
