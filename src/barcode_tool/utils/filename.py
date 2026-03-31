"""Filename cleanup utilities."""

from __future__ import annotations

import re

from barcode_tool.utils.text import clean_text


_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename_component(value: str, replacement: str = "_") -> str:
    """Make a string safe as a filename component."""
    cleaned = clean_text(value)
    cleaned = _ILLEGAL_FILENAME_CHARS.sub(replacement, cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned
