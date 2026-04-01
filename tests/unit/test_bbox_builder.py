from barcode_tool.models.types import DetectedLabel
from barcode_tool.services.bbox_builder import (
    BBoxBuildConfig,
    build_exportable_label,
    build_label_bbox,
    clamp_bbox_to_page,
    compute_text_height,
    expand_bbox,
)


def test_compute_text_height_and_expand_bbox() -> None:
    text_bbox = (10.0, 100.0, 110.0, 149.0)
    assert compute_text_height(text_bbox) == 49.0

    expanded = expand_bbox(text_bbox, BBoxBuildConfig(x_padding=12.0, y_up_scale=2.6, y_down_scale=0.15))
    assert expanded == (-2.0, -27.400000000000006, 122.0, 156.35)


def test_clamp_bbox_to_page() -> None:
    clamped = clamp_bbox_to_page((-2.0, -27.4, 122.0, 156.35), (0.0, 0.0, 120.0, 200.0))
    assert clamped == (0.0, 0.0, 120.0, 156.35)


def test_build_label_bbox_default_strategy() -> None:
    bbox = build_label_bbox((10.0, 100.0, 110.0, 149.0), (0.0, 0.0, 120.0, 200.0))
    assert bbox == (0.0, 0.0, 120.0, 156.35)


def test_build_exportable_label() -> None:
    detected = DetectedLabel(
        page_index=0,
        group_index=1,
        source="test",
        first_line="X01",
        second_line="Item, ABC",
        third_line="New",
        candidate_filename="ABC",
        text_bbox=(10.0, 100.0, 110.0, 149.0),
        line_count=3,
    )

    exportable = build_exportable_label(detected, (0.0, 0.0, 120.0, 200.0))
    assert exportable.page_index == 0
    assert exportable.candidate_filename == "ABC"
    assert exportable.label_bbox == (0.0, 0.0, 120.0, 156.35)
