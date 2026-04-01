from pathlib import Path

import pytest

from barcode_tool.models.types import ExportableLabel, LabelExportResult
from barcode_tool.pipeline.label_export_pipeline import run_label_export_pipeline


class _Rect:
    x0 = 0.0
    y0 = 0.0
    x1 = 100.0
    y1 = 100.0


class _Page:
    rect = _Rect()


class _Doc:
    def __iter__(self):
        return iter([_Page()])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_common(monkeypatch):
    monkeypatch.setattr("barcode_tool.pipeline.label_export_pipeline.analyze_pdf_to_labels", lambda **_: [])
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.enrich_detected_labels",
        lambda **_: (
            [
                ExportableLabel(
                    page_index=0,
                    group_index=0,
                    candidate_filename="ABC123",
                    text_bbox=(0.0, 0.0, 10.0, 10.0),
                    label_bbox=(0.0, 0.0, 10.0, 10.0),
                )
            ],
            [],
        ),
    )
    monkeypatch.setattr("barcode_tool.pipeline.label_export_pipeline.fitz.open", lambda _: _Doc())
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.write_manifest",
        lambda report_path, **_: report_path,
    )


def test_source_pdf_deleted_when_pipeline_success(tmp_path: Path, monkeypatch) -> None:
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.export_labels_from_pdf",
        lambda **_: [
            LabelExportResult(page_index=0, group_index=0, candidate_filename="ABC123", success=True, output_path="ok.jpg")
        ],
    )

    source_pdf = tmp_path / "products.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    result = run_label_export_pipeline(
        pdf_path=source_pdf,
        output_dir=tmp_path / "out",
        delete_source_on_success=True,
    )

    assert result.source_pdf_deleted is True
    assert result.source_pdf_delete_error == ""
    assert source_pdf.exists() is False


def test_source_pdf_kept_when_export_has_failures(tmp_path: Path, monkeypatch) -> None:
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.export_labels_from_pdf",
        lambda **_: [
            LabelExportResult(
                page_index=0,
                group_index=0,
                candidate_filename="ABC123",
                success=False,
                error_message="mock export error",
            )
        ],
    )

    source_pdf = tmp_path / "products.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    result = run_label_export_pipeline(
        pdf_path=source_pdf,
        output_dir=tmp_path / "out",
        delete_source_on_success=True,
    )

    assert result.source_pdf_deleted is False
    assert source_pdf.exists() is True


def test_source_pdf_kept_when_pipeline_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.analyze_pdf_to_labels",
        lambda **_: (_ for _ in ()).throw(RuntimeError("mock analyze failure")),
    )

    source_pdf = tmp_path / "products.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(RuntimeError, match="mock analyze failure"):
        run_label_export_pipeline(
            pdf_path=source_pdf,
            output_dir=tmp_path / "out",
            delete_source_on_success=True,
        )

    assert source_pdf.exists() is True
