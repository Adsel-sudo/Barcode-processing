from pathlib import Path

import pytest
from PIL import Image

from barcode_tool.models.types import ExportableLabel
from barcode_tool.services.crop_exporter import (
    export_labels_from_pdf,
    fit_image_to_canvas,
)

fitz = pytest.importorskip("fitz")


def test_fit_image_to_canvas_keeps_aspect_ratio_and_target_size() -> None:
    src = Image.new("RGB", (1000, 200), color=(0, 0, 0))
    dst = fit_image_to_canvas(src, target_width=589, target_height=386)

    assert dst.size == (589, 386)
    # Because source is very wide, top-left corner should remain white padding.
    assert dst.getpixel((0, 0)) == (255, 255, 255)


def test_export_labels_from_pdf_generates_fixed_size_jpg_and_deduplicates(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((30, 30), "X01")
    page.insert_text((30, 50), "Item Name, ABC123")
    page.insert_text((30, 70), "Made in China")
    doc.save(pdf_path)
    doc.close()

    labels = [
        ExportableLabel(
            page_index=0,
            group_index=1,
            first_line="X01",
            second_line="Item Name, ABC123",
            third_line="Made in China",
            candidate_filename="ABC123",
            text_bbox=(20.0, 20.0, 180.0, 80.0),
            label_bbox=(10.0, 10.0, 220.0, 120.0),
        ),
        ExportableLabel(
            page_index=0,
            group_index=2,
            first_line="X02",
            second_line="Item Name, ABC123",
            third_line="New",
            candidate_filename="ABC123",
            text_bbox=(20.0, 120.0, 180.0, 180.0),
            label_bbox=(10.0, 110.0, 220.0, 220.0),
        ),
    ]

    output_dir = tmp_path / "out"
    results = export_labels_from_pdf(pdf_path=pdf_path, labels=labels, output_dir=output_dir)

    assert len(results) == 2
    assert all(item.success for item in results)

    first = Path(results[0].output_path)
    second = Path(results[1].output_path)
    assert first.name == "ABC123.jpg"
    assert second.name == "ABC123_1.jpg"

    with Image.open(first) as im1:
        assert im1.size == (589, 386)
    with Image.open(second) as im2:
        assert im2.size == (589, 386)


def test_export_labels_from_pdf_keeps_batch_on_failure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample2.pdf"

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 30), "X01")
    doc.save(pdf_path)
    doc.close()

    labels = [
        ExportableLabel(
            page_index=9,
            group_index=1,
            first_line="X01",
            second_line="foo, BAD",
            third_line="New",
            candidate_filename="BAD",
            text_bbox=(0.0, 0.0, 10.0, 10.0),
            label_bbox=(0.0, 0.0, 10.0, 10.0),
        ),
        ExportableLabel(
            page_index=0,
            group_index=2,
            first_line="X02",
            second_line="foo, GOOD",
            third_line="New",
            candidate_filename="GOOD",
            text_bbox=(10.0, 10.0, 80.0, 60.0),
            label_bbox=(5.0, 5.0, 120.0, 90.0),
        ),
    ]

    results = export_labels_from_pdf(pdf_path=pdf_path, labels=labels, output_dir=tmp_path / "out2")
    assert len(results) == 2
    assert results[0].success is False
    assert "invalid page_index" in results[0].error_message
    assert results[1].success is True
