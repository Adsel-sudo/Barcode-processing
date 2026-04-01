from barcode_tool.models.types import DetectedLabel
from barcode_tool.services.label_enricher import (
    build_exportable_labels,
    enrich_detected_labels,
    validate_detected_label,
)


def _detected(candidate_filename: str = "ABC") -> DetectedLabel:
    return DetectedLabel(
        page_index=0,
        group_index=1,
        source="test",
        first_line="X01",
        second_line="Item, ABC",
        third_line="New",
        candidate_filename=candidate_filename,
        text_bbox=(10.0, 100.0, 110.0, 149.0),
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
