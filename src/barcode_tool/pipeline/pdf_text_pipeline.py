"""Pipeline orchestration for PDF-text mainline."""

from __future__ import annotations

from pathlib import Path

from barcode_tool.models.types import PipelineRecord, PipelineResult
from barcode_tool.services.block_cluster import build_barcode_blocks
from barcode_tool.services.filename_extractor import extract_candidate_filename
from barcode_tool.services.pdf_parser import parse_pdf_lines


def run_pdf_text_pipeline(pdf_path: Path) -> PipelineResult:
    """Run current mainline: parse -> cluster -> line2 filename extraction."""
    lines = parse_pdf_lines(pdf_path)
    result = PipelineResult(source_pdf=pdf_path)

    if not lines:
        return result

    pages = sorted({line.page_index for line in lines})
    for page_index in pages:
        page_lines = [line for line in lines if line.page_index == page_index]
        blocks = build_barcode_blocks(page_lines)
        for block in blocks:
            filename = None
            if block.triplet is not None:
                filename = extract_candidate_filename(block.triplet.second_line.text)
            result.records.append(
                PipelineRecord(
                    page_index=page_index,
                    block_index=block.block_index,
                    triplet=block.triplet,
                    filename=filename,
                )
            )

    return result
