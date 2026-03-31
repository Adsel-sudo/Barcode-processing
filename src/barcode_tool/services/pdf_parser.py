"""PDF text parsing layer: extract lines and coordinates from native PDF text."""

from __future__ import annotations

from pathlib import Path

import fitz

from barcode_tool.models.types import TextLine
from barcode_tool.utils.text import clean_text


def parse_pdf_lines(pdf_path: Path) -> list[TextLine]:
    """Parse all text lines with bbox from a PDF file."""
    all_lines: list[TextLine] = []
    with fitz.open(pdf_path) as doc:
        for page_index in range(len(doc)):
            all_lines.extend(parse_page_lines(pdf_path=pdf_path, page_index=page_index, _doc=doc))
    return all_lines


def parse_page_lines(pdf_path: Path, page_index: int, _doc: fitz.Document | None = None) -> list[TextLine]:
    """Parse one page's text lines with bbox from a PDF file."""
    owns_doc = _doc is None
    doc = _doc if _doc is not None else fitz.open(pdf_path)
    try:
        page = doc[page_index]
        raw = page.get_text("dict")
        lines: list[TextLine] = []

        line_index = 0
        for block in raw.get("blocks", []):
            if int(block.get("type", -1)) != 0:
                continue
            for ln in block.get("lines", []):
                spans = ln.get("spans", [])
                text = clean_text("".join(str(sp.get("text", "")) for sp in spans))
                if not text:
                    continue

                bbox = tuple(ln.get("bbox", (0.0, 0.0, 0.0, 0.0)))
                lines.append(
                    TextLine(
                        text=text,
                        bbox=bbox,  # type: ignore[arg-type]
                        page_index=page_index,
                        line_index=line_index,
                    )
                )
                line_index += 1

        lines.sort(key=lambda item: (item.bbox[1], item.bbox[0]))
        return lines
    finally:
        if owns_doc:
            doc.close()


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
