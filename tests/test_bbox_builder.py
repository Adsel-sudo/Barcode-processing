from barcode_tool.services.bbox_builder import (
    build_label_bbox,
    clamp_bbox_to_page,
    compute_text_height,
)


def test_build_label_bbox_expands_and_clamps() -> None:
    text_bbox = (10.0, 100.0, 110.0, 149.0)
    page_rect = (0.0, 0.0, 120.0, 200.0)

    bbox = build_label_bbox(text_bbox=text_bbox, page_rect=page_rect)
    assert bbox == (0.0, 0.0, 120.0, 156.35)


def test_text_height_and_clamp_boundary_cases() -> None:
    assert compute_text_height((10.0, 10.0, 20.0, 30.0)) == 20.0

    clamped = clamp_bbox_to_page(
        bbox=(-50.0, -50.0, 500.0, 500.0),
        page_rect=(0.0, 0.0, 100.0, 100.0),
    )
    assert clamped == (0.0, 0.0, 100.0, 100.0)
