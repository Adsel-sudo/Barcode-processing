from barcode_tool.models.types import DetectedLabel
from barcode_tool.services.label_enricher import (
    build_exportable_labels,
    enrich_detected_labels,
    validate_detected_label,
)


def _detected(
    candidate_filename: str = "ABC",
    group_index: int = 1,
    text_bbox: tuple[float, float, float, float] = (10.0, 100.0, 110.0, 149.0),
) -> DetectedLabel:
    return DetectedLabel(
        page_index=0,
        group_index=group_index,
        source="test",
        first_line="X01",
        second_line="Item, ABC",
        third_line="New",
        candidate_filename=candidate_filename,
        text_bbox=text_bbox,
        line_count=3,
    )


def test_validate_detected_label() -> None:
    ok, reason = validate_detected_label(_detected())
    assert ok is True
    assert reason == ""

    bad, bad_reason = validate_detected_label(_detected(candidate_filename="   "))
    assert bad is False
    assert "candidate_filename" in bad_reason


def test_build_exportable_labels() -> None:
    labels = build_exportable_labels([_detected()], {0: (0.0, 0.0, 120.0, 200.0)})
    assert len(labels) == 1
    assert labels[0].label_bbox == (0.0, 0.0, 120.0, 156.35)


def test_enrich_detected_labels_filters_invalid() -> None:
    valid = _detected("GOOD")
    invalid = _detected("   ")

    exportable, warnings = enrich_detected_labels(
        [valid, invalid],
        page_rect_by_index={0: (0.0, 0.0, 120.0, 200.0)},
    )

    assert len(exportable) == 1
    assert exportable[0].candidate_filename == "GOOD"
    assert len(warnings) == 1


def test_build_exportable_labels_applies_group_safe_top() -> None:
    labels = build_exportable_labels(
        [
            _detected("SECOND", group_index=2, text_bbox=(10.0, 100.0, 110.0, 149.0)),
            _detected("FIRST", group_index=1, text_bbox=(10.0, 70.0, 110.0, 92.0)),
        ],
        {0: (0.0, 0.0, 120.0, 220.0)},
    )

    assert [item.candidate_filename for item in labels] == ["FIRST", "SECOND"]
    assert labels[1].label_bbox[1] == 106.7
