"""Enrich recognition-stage labels into export-ready records."""

from __future__ import annotations

from collections.abc import Sequence

from barcode_tool.models.types import BBox, DetectedLabel, ExportableLabel
from barcode_tool.services.bbox_builder import build_exportable_label
from barcode_tool.utils.filename import sanitize_filename_component


def validate_detected_label(label: DetectedLabel) -> tuple[bool, str]:
    """Validate core fields needed by export stage."""
    if label.page_index < 0:
        return False, "page_index must be >= 0"
    if not sanitize_filename_component(label.candidate_filename):
        return False, "candidate_filename is empty after sanitization"

    x0, y0, x1, y1 = label.text_bbox
    if x1 <= x0 or y1 <= y0:
        return False, "text_bbox is invalid"

    return True, ""


def build_exportable_labels(
    detected_labels: Sequence[DetectedLabel],
    page_rect_by_index: dict[int, BBox],
    strategy: str = "default",
) -> list[ExportableLabel]:
    """Build ExportableLabel list from valid detected labels."""
    exportable: list[ExportableLabel] = []
    for label in detected_labels:
        page_rect = page_rect_by_index.get(label.page_index)
        if page_rect is None:
            continue
        exportable.append(build_exportable_label(label, page_rect=page_rect, strategy=strategy))
    return exportable


def enrich_detected_labels(
    detected_labels: Sequence[DetectedLabel],
    page_rect_by_index: dict[int, BBox],
    strategy: str = "default",
) -> tuple[list[ExportableLabel], list[str]]:
    """Run enrich stage: validate -> bbox build -> exportable labels."""
    valid_labels: list[DetectedLabel] = []
    warnings: list[str] = []

    for label in detected_labels:
        is_valid, reason = validate_detected_label(label)
        if not is_valid:
            warnings.append(
                f"skip page={label.page_index} group={label.group_index}: {reason}"
            )
            continue
        valid_labels.append(label)

    return build_exportable_labels(valid_labels, page_rect_by_index=page_rect_by_index, strategy=strategy), warnings
