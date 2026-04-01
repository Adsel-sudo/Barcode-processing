"""Analyze PDF text lines into recognition-stage DetectedLabel objects."""

from __future__ import annotations

from pathlib import Path

from barcode_tool.models.types import DetectedLabel, TextLine
from barcode_tool.services.block_cluster import cluster_lines_by_column
from barcode_tool.services.label_builder import build_detected_labels_from_page
from barcode_tool.utils.text import clean_text


def _group_lines_by_three(lines: list[TextLine]) -> list[list[TextLine]]:
    groups: list[list[TextLine]] = []
    for i in range(0, len(lines), 3):
        chunk = lines[i : i + 3]
        if len(chunk) == 3:
            groups.append(chunk)
    return groups


def _is_barcode_triplet(lines: list[TextLine]) -> bool:
    first, second, third = lines[0].text, lines[1].text, lines[2].text
    first_ok = clean_text(first).upper().startswith("X0")
    second_ok = bool(clean_text(second))
    third_norm = clean_text(third).lower()
    third_ok = "new" in third_norm or "新品" in third or "made in china" in third_norm
    return first_ok and second_ok and third_ok


def _debug_print_column_groups(page_index: int, clusters: list[list[TextLine]]) -> None:
    print(f"[DEBUG] page={page_index + 1} 列聚类数量: {len(clusters)}")
    for col_idx, cluster in enumerate(clusters, start=1):
        print(f"[DEBUG]   列#{col_idx} line_count={len(cluster)}")
        for line_idx, line in enumerate(cluster, start=1):
            print(f"[DEBUG]     L{line_idx:02d} y={line.bbox[1]:.2f} x={line.bbox[0]:.2f} text={line.text}")
        for group_idx, group in enumerate(_group_lines_by_three(cluster), start=1):
            print(f"[DEBUG]     组#{group_idx}: [{group[0].text}] | [{group[1].text}] | [{group[2].text}]")


def analyze_page_to_labels(
    page_index: int,
    page_lines: list[TextLine],
    x_threshold: float = 80.0,
    debug: bool = False,
) -> list[DetectedLabel]:
    """Analyze one page using validated fallback-line-cluster logic."""
    clusters = cluster_lines_by_column(page_lines, x_threshold=x_threshold)
    if debug:
        _debug_print_column_groups(page_index, clusters)

    triplet_groups: list[list[TextLine]] = []
    for cluster in clusters:
        for group in _group_lines_by_three(cluster):
            if _is_barcode_triplet(group):
                triplet_groups.append(group)

    return build_detected_labels_from_page(
        page_index=page_index,
        groups=triplet_groups,
        source="fallback-line-cluster",
    )


def analyze_pdf_to_labels(
    pdf_path: Path,
    use_fallback_cluster: bool = True,
    debug: bool = False,
) -> list[DetectedLabel]:
    """Analyze all pages in PDF and return recognized DetectedLabel list."""
    labels: list[DetectedLabel] = []

    import fitz

    with fitz.open(pdf_path) as doc:
        for page_index in range(len(doc)):
            from barcode_tool.services.pdf_parser import parse_page_lines

            page_lines = parse_page_lines(pdf_path=pdf_path, page_index=page_index, _doc=doc)

            if use_fallback_cluster:
                page_labels = analyze_page_to_labels(
                    page_index=page_index,
                    page_lines=page_lines,
                    debug=debug,
                )
            else:
                page_labels = []

            labels.extend(page_labels)

    return labels
