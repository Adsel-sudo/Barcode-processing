"""Core dataclasses for PDF-text barcode processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

BBox = tuple[float, float, float, float]


@dataclass(slots=True)
class TextLine:
    text: str
    bbox: BBox
    page_index: int
    line_index: int


@dataclass(slots=True)
class BarcodeTextTriplet:
    first_line: TextLine
    second_line: TextLine
    third_line: TextLine


@dataclass(slots=True)
class BarcodeBlock:
    page_index: int
    block_index: int
    lines: list[TextLine]
    text_bbox: BBox
    triplet: BarcodeTextTriplet | None = None


@dataclass(slots=True)
class BarcodeLabel:
    page_index: int
    group_index: int
    source: str
    first_line: str
    second_line: str
    third_line: str
    candidate_filename: str
    text_bbox: BBox
    label_bbox: BBox
    line_count: int


@dataclass(slots=True)
class FilenameCandidate:
    value: str
    source_text: str
    is_valid: bool
    reason: str = ""


@dataclass(slots=True)
class LabelExportResult:
    page_index: int
    group_index: int
    candidate_filename: str
    success: bool
    output_path: str = ""
    error_message: str = ""


@dataclass(slots=True)
class ExportTask:
    source_pdf: Path
    page_index: int
    label_bbox: BBox
    text_bbox: BBox
    candidate_filename: str


@dataclass(slots=True)
class PipelineRecord:
    page_index: int
    block_index: int
    triplet: BarcodeTextTriplet | None
    filename: FilenameCandidate | None
    status: Literal["ok", "skip", "error"] = "ok"
    message: str = ""


@dataclass(slots=True)
class PipelineResult:
    source_pdf: Path
    records: list[PipelineRecord] = field(default_factory=list)
