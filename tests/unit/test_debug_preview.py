from pathlib import Path

import pytest
from PIL import Image

from barcode_tool.models.types import ExportableLabel
from barcode_tool.services.debug_preview import (
    draw_label_bboxes,
    export_debug_previews,
    render_page_preview,
)

fitz = pytest.importorskip("fitz")


def test_draw_label_bboxes_returns_image() -> None:
    image = Image.new("RGB", (300, 200), (255, 255, 255))
    labels = [
        ExportableLabel(
            page_index=0,
            group_index=1,
            first_line="X01",
            second_line="Item, A",
            third_line="New",
            candidate_filename="A",
            text_bbox=(0.0, 0.0, 10.0, 10.0),
            label_bbox=(20.0, 30.0, 120.0, 80.0),
        )
    ]
    out = draw_label_bboxes(image=image, labels=labels, zoom=1.0)
    assert out.size == (300, 200)


def test_export_debug_previews_multi_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.new_page(width=200, height=200)
    doc.save(pdf_path)
    doc.close()

    labels = [
        ExportableLabel(
            page_index=0,
            group_index=1,
            first_line="X01",
            second_line="Item, A",
            third_line="New",
            candidate_filename="A",
            text_bbox=(0.0, 0.0, 10.0, 10.0),
            label_bbox=(10.0, 10.0, 60.0, 60.0),
        ),
        ExportableLabel(
            page_index=1,
            group_index=1,
            first_line="X02",
            second_line="Item, B",
            third_line="New",
            candidate_filename="B",
            text_bbox=(0.0, 0.0, 10.0, 10.0),
            label_bbox=(20.0, 20.0, 80.0, 80.0),
        ),
    ]

    out_paths = export_debug_previews(pdf_path=pdf_path, labels=labels, output_dir=tmp_path / "debug")
    assert len(out_paths) == 2
    assert out_paths[0].exists()
    assert out_paths[1].exists()


def test_render_page_preview_returns_image(tmp_path: Path) -> None:
    pdf_path = tmp_path / "single.pdf"
    doc = fitz.open()
    doc.new_page(width=120, height=80)
    doc.save(pdf_path)
    doc.close()

    with fitz.open(pdf_path) as loaded:
        image = render_page_preview(loaded[0], zoom=2.0)
    assert image.width > 0 and image.height > 0
