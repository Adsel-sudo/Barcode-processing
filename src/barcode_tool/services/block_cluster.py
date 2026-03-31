"""Barcode block clustering layer based on x/y coordinates."""

from __future__ import annotations

from barcode_tool.models.types import BarcodeBlock, BarcodeTextTriplet, TextLine
from barcode_tool.utils.bbox import union_bbox
from barcode_tool.utils.text import clean_text


def cluster_lines_by_column(lines: list[TextLine], x_threshold: float = 80.0) -> list[list[TextLine]]:
    """Group lines into column-like clusters by left x coordinate."""
    if not lines:
        return []

    ordered = sorted(lines, key=lambda line: (line.bbox[0], line.bbox[1]))
    clusters: list[list[TextLine]] = []
    anchors: list[float] = []

    for line in ordered:
        x0 = line.bbox[0]
        if not clusters:
            clusters.append([line])
            anchors.append(x0)
            continue

        distances = [abs(x0 - anchor) for anchor in anchors]
        best_idx = min(range(len(distances)), key=distances.__getitem__)
        if distances[best_idx] <= x_threshold:
            clusters[best_idx].append(line)
            anchors[best_idx] = sum(item.bbox[0] for item in clusters[best_idx]) / len(clusters[best_idx])
        else:
            clusters.append([line])
            anchors.append(x0)

    for cluster in clusters:
        cluster.sort(key=lambda line: (line.bbox[1], line.bbox[0]))
    return clusters


def split_cluster_into_blocks(cluster_lines: list[TextLine], y_gap_threshold: float = 18.0) -> list[list[TextLine]]:
    """Split one column cluster into block candidates by y gaps."""
    if not cluster_lines:
        return []

    ordered = sorted(cluster_lines, key=lambda line: (line.bbox[1], line.bbox[0]))
    groups: list[list[TextLine]] = [[ordered[0]]]

    for prev, current in zip(ordered, ordered[1:]):
        gap = current.bbox[1] - prev.bbox[1]
        if gap > y_gap_threshold:
            groups.append([current])
        else:
            groups[-1].append(current)

    return groups


def _is_barcode_triplet(first: str, second: str, third: str) -> bool:
    first_ok = clean_text(first).upper().startswith("X0")
    second_ok = bool(clean_text(second))
    third_norm = clean_text(third).lower()
    third_ok = "new" in third_norm or "新品" in third or "made in china" in third_norm
    return first_ok and second_ok and third_ok


def detect_triplet(lines: list[TextLine]) -> BarcodeTextTriplet | None:
    """Detect first/second/third line structure from ordered lines."""
    if len(lines) < 3:
        return None

    ordered = sorted(lines, key=lambda line: (line.bbox[1], line.bbox[0]))
    for idx in range(len(ordered) - 2):
        first = ordered[idx]
        second = ordered[idx + 1]
        third = ordered[idx + 2]
        if _is_barcode_triplet(first.text, second.text, third.text):
            return BarcodeTextTriplet(first_line=first, second_line=second, third_line=third)
    return None


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
