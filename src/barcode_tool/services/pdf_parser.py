"""PDF text parsing layer: extract lines and coordinates from native PDF text."""

from __future__ import annotations

from pathlib import Path

from barcode_tool.models.types import TextLine
from barcode_tool.utils.text import clean_text


def parse_pdf_lines(pdf_path: Path) -> list[TextLine]:
    """Parse all text lines with bbox from a PDF file."""
    raise NotImplementedError


def parse_page_lines(pdf_path: Path, page_index: int) -> list[TextLine]:
    """Parse one page's text lines with bbox from a PDF file."""
    raise NotImplementedError


def normalize_line_text(lines: list[TextLine]) -> list[TextLine]:
    """Return lines with normalized text (spacing/punctuation cleanup)."""
    normalized: list[TextLine] = []
    for line in lines:
        normalized.append(
            TextLine(
                text=clean_text(line.text),
                bbox=line.bbox,
                page_index=line.page_index,
                line_index=line.line_index,
            )
        )
    return normalized
