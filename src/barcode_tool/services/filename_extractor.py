"""Filename extraction layer: parse candidate filename from line-2 text."""

from __future__ import annotations

from barcode_tool.models.types import FilenameCandidate
from barcode_tool.utils.filename import sanitize_filename_component
from barcode_tool.utils.text import clean_text


def extract_candidate_filename(second_line_text: str) -> FilenameCandidate:
    """Extract filename candidate using comma/space fallback strategy."""
    normalized = clean_text(second_line_text).replace("，", ",")
    if not normalized:
        return FilenameCandidate(value="", source_text=second_line_text, is_valid=False, reason="empty-line2")

    if "," in normalized:
        raw = normalized.rsplit(",", 1)[-1]
    elif " " in normalized:
        raw = normalized.rsplit(" ", 1)[-1]
    else:
        raw = normalized

    candidate = sanitize_filename_component(raw)
    if not candidate:
        return FilenameCandidate(value="", source_text=second_line_text, is_valid=False, reason="empty-after-sanitize")

    return FilenameCandidate(value=candidate, source_text=second_line_text, is_valid=True)
