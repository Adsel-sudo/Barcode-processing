from barcode_tool.models.types import TextLine
from barcode_tool.services.label_analyzer import analyze_page_to_labels


def _line(text: str, bbox: tuple[float, float, float, float], idx: int) -> TextLine:
    return TextLine(text=text, bbox=bbox, page_index=0, line_index=idx)


def test_analyze_page_to_labels_uses_fallback_cluster_triplets() -> None:
    lines = [
        _line("X01", (10.0, 100.0, 60.0, 115.0), 0),
        _line("Item A, A001", (12.0, 116.0, 110.0, 132.0), 1),
        _line("Made in China", (10.0, 133.0, 90.0, 149.0), 2),
        _line("X02", (210.0, 100.0, 260.0, 115.0), 3),
        _line("Item B, B001", (212.0, 116.0, 310.0, 132.0), 4),
        _line("New", (210.0, 133.0, 290.0, 149.0), 5),
    ]

    labels = analyze_page_to_labels(
        page_index=0,
        page_lines=lines,
        page_rect=(0.0, 0.0, 400.0, 400.0),
        debug=False,
    )

    assert len(labels) == 2
    assert labels[0].candidate_filename == "A001"
    assert labels[1].candidate_filename == "B001"
    assert labels[0].source == "fallback-line-cluster"
