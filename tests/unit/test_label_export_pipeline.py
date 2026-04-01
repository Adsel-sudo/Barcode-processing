from pathlib import Path

from barcode_tool.pipeline.label_export_pipeline import build_run_output_dir, try_delete_source_pdf


def test_build_run_output_dir_uses_pdf_stem_and_timestamp(tmp_path: Path) -> None:
    run_dir = build_run_output_dir(tmp_path, Path("products.pdf"))

    assert run_dir.parent == tmp_path
    assert run_dir.name.startswith("products_")
    assert len(run_dir.name) >= len("products_20260401_153000")


def test_build_run_output_dir_appends_suffix_when_name_exists(tmp_path: Path) -> None:
    first = build_run_output_dir(tmp_path, Path("products.pdf"))
    first.mkdir(parents=True, exist_ok=True)

    second = build_run_output_dir(tmp_path, Path("products.pdf"))

    assert second != first
    assert second.parent == tmp_path
    assert second.name.startswith(first.name + "_")


def test_try_delete_source_pdf_deletes_file_when_enabled(tmp_path: Path) -> None:
    source_pdf = tmp_path / "sample.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    deleted, error = try_delete_source_pdf(source_pdf, enabled=True)

    assert deleted is True
    assert error == ""
    assert source_pdf.exists() is False


def test_try_delete_source_pdf_skips_when_disabled(tmp_path: Path) -> None:
    source_pdf = tmp_path / "sample.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")

    deleted, error = try_delete_source_pdf(source_pdf, enabled=False)

    assert deleted is False
    assert error == ""
    assert source_pdf.exists() is True
