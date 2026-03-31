from pathlib import Path

from barcode_tool.models.types import BarcodeLabel
from barcode_tool.models.types import LabelExportResult
from barcode_tool.services.manifest_writer import write_manifest_csv


def test_write_manifest_csv_contains_required_fields(tmp_path: Path) -> None:
    labels = [
        BarcodeLabel(
            page_index=0,
            group_index=1,
            source="test",
            first_line="X01",
            second_line="Item, ABC",
            third_line="New",
            candidate_filename="ABC",
            text_bbox=(1.0, 2.0, 3.0, 4.0),
            label_bbox=(0.0, 0.0, 10.0, 10.0),
            line_count=3,
        )
    ]
    results = [
        LabelExportResult(
            page_index=0,
            group_index=1,
            candidate_filename="ABC",
            success=True,
            output_path="/tmp/ABC.jpg",
            error_message="",
        )
    ]

    report = write_manifest_csv(tmp_path / "report.csv", labels, results)
    content = report.read_text(encoding="utf-8-sig")

    assert "page_index" in content
    assert "candidate_filename" in content
    assert "output_path" in content
    assert "ABC" in content
