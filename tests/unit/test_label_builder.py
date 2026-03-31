from barcode_tool.models.types import TextLine
from barcode_tool.services.label_builder import (
    build_barcode_labels_from_page,
    compute_label_bbox,
    compute_text_bbox,
    deduplicate_filename,
    sanitize_filename,
)


def _line(text: str, bbox: tuple[float, float, float, float], idx: int) -> TextLine:
    return TextLine(text=text, bbox=bbox, page_index=0, line_index=idx)


def test_compute_text_bbox_uses_union_of_three_lines() -> None:
    lines = [
        _line("X01", (10.0, 100.0, 60.0, 115.0), 0),
        _line("desc, FILE", (15.0, 116.0, 110.0, 132.0), 1),
        _line("Made in China", (12.0, 133.0, 90.0, 149.0), 2),
    ]

    assert compute_text_bbox(lines) == (10.0, 100.0, 110.0, 149.0)


def test_compute_label_bbox_uses_ratio_and_page_clamp() -> None:
    text_bbox = (10.0, 100.0, 110.0, 149.0)
    # text_height = 49 -> y0 = 100 - 49*2.6 = -27.4, then clamped to 0
    bbox = compute_label_bbox(text_bbox=text_bbox, page_rect=(0.0, 0.0, 120.0, 200.0))
    assert bbox == (0.0, 0.0, 120.0, 156.35)


def test_filename_sanitize_and_deduplicate() -> None:
    assert sanitize_filename('A/B:C*D?') == 'A_B_C_D_'

    seen: dict[str, int] = {}
    assert deduplicate_filename("foo", seen) == "foo"
    assert deduplicate_filename("foo", seen) == "foo_2"
    assert deduplicate_filename("foo", seen) == "foo_3"


def test_build_barcode_labels_from_page_binds_text_and_label_bbox() -> None:
    groups = [
        [
            _line("X01", (10.0, 100.0, 60.0, 115.0), 0),
            _line("Item Name, AB-123", (15.0, 116.0, 110.0, 132.0), 1),
            _line("Made in China", (12.0, 133.0, 90.0, 149.0), 2),
        ],
        [
            _line("X02", (10.0, 200.0, 60.0, 215.0), 3),
            _line("Item Name, AB-123", (15.0, 216.0, 110.0, 232.0), 4),
            _line("New", (12.0, 233.0, 90.0, 249.0), 5),
        ],
    ]

    labels = build_barcode_labels_from_page(
        page_index=0,
        groups=groups,
        page_rect=(0.0, 0.0, 500.0, 700.0),
    )

    assert len(labels) == 2
    assert labels[0].group_index == 1
    assert labels[0].candidate_filename == "AB-123"
    assert labels[1].candidate_filename == "AB-123_2"
    assert labels[0].text_bbox == (10.0, 100.0, 110.0, 149.0)
    assert labels[0].label_bbox[0] == 0.0
