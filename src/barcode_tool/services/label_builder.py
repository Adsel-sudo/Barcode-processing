"""Build recognition/export label objects from recognized text groups."""

from __future__ import annotations

from collections.abc import Sequence

from barcode_tool.models.types import BBox, DetectedLabel, ExportableLabel, TextLine
from barcode_tool.services.bbox_builder import build_label_bbox
from barcode_tool.services.filename_extractor import extract_candidate_filename
from barcode_tool.utils.filename import sanitize_filename_component


def compute_text_bbox(lines: Sequence[TextLine]) -> BBox:
    """Compute union bbox for the input lines.

    Reuse the original line bbox data directly instead of re-estimating geometry.
    """
    if not lines:
        raise ValueError("compute_text_bbox requires at least one line")

    x0 = min(line.bbox[0] for line in lines)
    y0 = min(line.bbox[1] for line in lines)
    x1 = max(line.bbox[2] for line in lines)
    y1 = max(line.bbox[3] for line in lines)
    return (x0, y0, x1, y1)


def compute_label_bbox(
    text_bbox: BBox,
    page_rect: BBox,
    x_padding: float = 12.0,
    y_up_scale: float = 2.6,
    y_down_scale: float = 0.15,
) -> BBox:
    """Backward-compatible wrapper around centralized bbox builder."""
    from barcode_tool.services.bbox_builder import BBoxBuildConfig

    return build_label_bbox(
        text_bbox=text_bbox,
        page_rect=page_rect,
        config=BBoxBuildConfig(x_padding=x_padding, y_up_scale=y_up_scale, y_down_scale=y_down_scale),
    )


def sanitize_filename(value: str, fallback: str = "unnamed") -> str:
    """Sanitize filename for downstream image export."""
    safe = sanitize_filename_component(value)
    if not safe:
        return fallback
    return safe


def deduplicate_filename(filename: str, seen: dict[str, int]) -> str:
    """Make filename unique with numeric suffix when duplicates appear."""
    current = seen.get(filename, 0)
    seen[filename] = current + 1
    if current == 0:
        return filename
    return f"{filename}_{current + 1}"


def build_detected_labels_from_page(
    page_index: int,
    groups: Sequence[Sequence[TextLine]],
    source: str = "fallback-line-cluster",
    seen_filenames: dict[str, int] | None = None,
) -> list[DetectedLabel]:
    """Build DetectedLabel records from one page's recognized 3-line groups."""
    tracker = seen_filenames if seen_filenames is not None else {}
    labels: list[DetectedLabel] = []

    for group_idx, group in enumerate(groups, start=1):
        if len(group) < 3:
            continue

        first, second, third = group[0], group[1], group[2]
        used_lines = [first, second, third]
        text_bbox = compute_text_bbox(used_lines)

        candidate = extract_candidate_filename(second.text)
        safe_name = sanitize_filename(candidate.value)
        unique_name = deduplicate_filename(safe_name, tracker)

        labels.append(
            DetectedLabel(
                page_index=page_index,
                group_index=group_idx,
                source=source,
                first_line=first.text,
                second_line=second.text,
                third_line=third.text,
                candidate_filename=unique_name,
                text_bbox=text_bbox,
                line_count=len(group),
            )
        )

    return labels


def build_exportable_labels(
    detected_labels: Sequence[DetectedLabel],
    page_rect_by_index: dict[int, BBox],
    strategy: str = "default",
) -> list[ExportableLabel]:
    """Backward-compatible wrapper; prefer `label_enricher.build_exportable_labels`."""
    from barcode_tool.services.label_enricher import build_exportable_labels as _build_exportable_labels

    return _build_exportable_labels(
        detected_labels=detected_labels,
        page_rect_by_index=page_rect_by_index,
        strategy=strategy,
    )
