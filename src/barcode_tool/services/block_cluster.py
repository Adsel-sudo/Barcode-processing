"""Barcode block clustering layer based on x/y coordinates."""

from __future__ import annotations

from barcode_tool.models.types import BarcodeBlock, BarcodeTextTriplet, TextLine
from barcode_tool.utils.bbox import union_bbox


def cluster_lines_by_column(lines: list[TextLine], x_threshold: float = 80.0) -> list[list[TextLine]]:
    """Group lines into column-like clusters by left x coordinate."""
    raise NotImplementedError


def split_cluster_into_blocks(cluster_lines: list[TextLine], y_gap_threshold: float = 18.0) -> list[list[TextLine]]:
    """Split one column cluster into block candidates by y gaps."""
    raise NotImplementedError


def detect_triplet(lines: list[TextLine]) -> BarcodeTextTriplet | None:
    """Detect first/second/third line structure from ordered lines."""
    raise NotImplementedError


def build_barcode_blocks(lines: list[TextLine], x_threshold: float = 80.0, y_gap_threshold: float = 18.0) -> list[BarcodeBlock]:
    """Build barcode blocks with optional triplet recognition for one page."""
    blocks: list[BarcodeBlock] = []
    grouped = cluster_lines_by_column(lines, x_threshold=x_threshold)

    block_index = 0
    for cluster in grouped:
        for one_block_lines in split_cluster_into_blocks(cluster, y_gap_threshold=y_gap_threshold):
            box = union_bbox([line.bbox for line in one_block_lines])
            triplet = detect_triplet(one_block_lines)
            blocks.append(
                BarcodeBlock(
                    page_index=one_block_lines[0].page_index,
                    block_index=block_index,
                    lines=one_block_lines,
                    text_bbox=box,
                    triplet=triplet,
                )
            )
            block_index += 1
    return blocks
