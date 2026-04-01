from pathlib import Path

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


def _mock_pipeline_services(monkeypatch):
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
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.export_labels_from_pdf",
        lambda **kwargs: [
            LabelExportResult(
                page_index=0,
                group_index=0,
                candidate_filename="ABC123",
                success=True,
                output_path=str(Path(kwargs["output_dir"]) / "ABC123.jpg"),
            )
        ],
    )
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.write_manifest",
        lambda report_path, **_: report_path,
    )
    monkeypatch.setattr(
        "barcode_tool.pipeline.label_export_pipeline.export_debug_previews",
        lambda output_dir, **_: [Path(output_dir) / "page_001_debug.jpg"],
    )
    monkeypatch.setattr("barcode_tool.pipeline.label_export_pipeline.fitz.open", lambda _: _Doc())


def test_run_output_layout_creates_images_report_dirs(tmp_path: Path, monkeypatch) -> None:
    _mock_pipeline_services(monkeypatch)

    source_pdf = tmp_path / "products.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    result = run_label_export_pipeline(
        pdf_path=source_pdf,
        output_dir=tmp_path / "out",
        debug_preview=False,
        delete_source_on_success=False,
    )

    run_output_dir = Path(result.run_output_dir)
    assert run_output_dir.parent == tmp_path / "out"
    assert (run_output_dir / "images").is_dir()
    assert (run_output_dir / "report").is_dir()
    assert (run_output_dir / "debug").exists() is False


def test_run_output_layout_creates_debug_dir_when_enabled(tmp_path: Path, monkeypatch) -> None:
    _mock_pipeline_services(monkeypatch)

    source_pdf = tmp_path / "products.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    result = run_label_export_pipeline(
        pdf_path=source_pdf,
        output_dir=tmp_path / "out",
        debug_preview=True,
        delete_source_on_success=False,
    )

    run_output_dir = Path(result.run_output_dir)
    assert (run_output_dir / "images").is_dir()
    assert (run_output_dir / "report").is_dir()
    assert (run_output_dir / "debug").is_dir()
    assert len(result.preview_paths) == 1
