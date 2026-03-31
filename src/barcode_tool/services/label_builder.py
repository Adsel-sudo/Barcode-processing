"""Build structured barcode-label objects from recognized 3-line text groups."""

from __future__ import annotations

from collections.abc import Sequence

from barcode_tool.models.types import BBox, BarcodeLabel, TextLine
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
    """Compute label crop bbox from text bbox using a fixed-ratio policy.

    Policy tuned for current stable template:
    - label_x0 = text_x0 - 12
    - label_x1 = text_x1 + 12
    - label_y0 = text_y0 - text_height * 2.6
    - label_y1 = text_y1 + text_height * 0.15

    The final bbox is clamped into page_rect to avoid overflow.
    """
    text_x0, text_y0, text_x1, text_y1 = text_bbox
    page_x0, page_y0, page_x1, page_y1 = page_rect

    text_height = max(text_y1 - text_y0, 0.0)

    raw_x0 = text_x0 - x_padding
    raw_x1 = text_x1 + x_padding
    raw_y0 = text_y0 - text_height * y_up_scale
    raw_y1 = text_y1 + text_height * y_down_scale

    clamped_x0 = max(page_x0, raw_x0)
    clamped_y0 = max(page_y0, raw_y0)
    clamped_x1 = min(page_x1, raw_x1)
    clamped_y1 = min(page_y1, raw_y1)

    if clamped_x0 > clamped_x1:
        clamped_x0 = clamped_x1
    if clamped_y0 > clamped_y1:
        clamped_y0 = clamped_y1

    return (clamped_x0, clamped_y0, clamped_x1, clamped_y1)


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


def build_barcode_labels_from_page(
    page_index: int,
    groups: Sequence[Sequence[TextLine]],
    page_rect: BBox,
    source: str = "fallback-line-cluster",
    seen_filenames: dict[str, int] | None = None,
) -> list[BarcodeLabel]:
    """Build BarcodeLabel records from one page's recognized 3-line groups.

    Each group should represent exactly one barcode text triplet in order:
    first line, second line, third line.
    """
    tracker = seen_filenames if seen_filenames is not None else {}
    labels: list[BarcodeLabel] = []

    for group_idx, group in enumerate(groups, start=1):
        if len(group) < 3:
            continue

        first, second, third = group[0], group[1], group[2]
        used_lines = [first, second, third]
        text_bbox = compute_text_bbox(used_lines)
        label_bbox = compute_label_bbox(text_bbox=text_bbox, page_rect=page_rect)

        candidate = extract_candidate_filename(second.text)
        safe_name = sanitize_filename(candidate.value)
        unique_name = deduplicate_filename(safe_name, tracker)

        labels.append(
            BarcodeLabel(
                page_index=page_index,
                group_index=group_idx,
                source=source,
                first_line=first.text,
                second_line=second.text,
                third_line=third.text,
                candidate_filename=unique_name,
                text_bbox=text_bbox,
                label_bbox=label_bbox,
                line_count=len(group),
            )
        )

    return labels
