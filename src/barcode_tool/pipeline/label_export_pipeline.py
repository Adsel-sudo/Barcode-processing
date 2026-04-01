"""Pipeline orchestration for PDF barcode label export."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import fitz

from barcode_tool.models.types import DetectedLabel, ExportableLabel, LabelExportResult
from barcode_tool.services.crop_exporter import export_labels_from_pdf
from barcode_tool.services.debug_preview import export_debug_previews
from barcode_tool.services.label_analyzer import analyze_pdf_to_labels
from barcode_tool.services.label_enricher import enrich_detected_labels
from barcode_tool.services.manifest_writer import write_manifest
from barcode_tool.utils.filename import sanitize_filename_component


@dataclass(slots=True)
class LabelExportPipelineResult:
    detected_labels: list[DetectedLabel] = field(default_factory=list)
    exportable_labels: list[ExportableLabel] = field(default_factory=list)
    export_results: list[LabelExportResult] = field(default_factory=list)
    enrich_warnings: list[str] = field(default_factory=list)
    run_output_dir: str = ""
    image_dir: str = ""
    report_path: str = ""
    preview_paths: list[str] = field(default_factory=list)
    source_pdf_deleted: bool = False
    source_pdf_delete_error: str = ""


def build_run_output_dir(base_output_dir: Path, pdf_path: Path) -> Path:
    """Build a unique run output directory under base_output_dir.

    Naming pattern: {pdf_stem}_{YYYYMMDD_HHMMSS}[_{n}]
    """
    safe_pdf_stem = sanitize_filename_component(pdf_path.stem) or "input"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_pdf_stem}_{timestamp}"

    candidate = base_output_dir / base_name
    suffix = 1
    while candidate.exists():
        candidate = base_output_dir / f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def try_delete_source_pdf(pdf_path: Path, enabled: bool) -> tuple[bool, str]:
    """Try deleting source PDF when enabled; never raise to callers."""
    if not enabled:
        return False, ""

    try:
        if pdf_path.exists():
            pdf_path.unlink()
            return True, ""
    except OSError as exc:
        return False, str(exc)

    return False, ""


def run_label_export_pipeline(
    pdf_path: Path,
    output_dir: Path,
    report_path: Path | None = None,
    image_width: int = 589,
    image_height: int = 386,
    jpg_quality: int = 95,
    use_fallback_cluster: bool = True,
    debug_preview: bool = False,
    debug_dir: Path | None = None,
    delete_source_on_success: bool = True,
    debug: bool = False,
    bbox_strategy: str = "default",
) -> LabelExportPipelineResult:
    """Run full workflow: analyze -> enrich -> export -> manifest -> optional preview."""
    run_output_dir = build_run_output_dir(base_output_dir=output_dir, pdf_path=pdf_path)
    image_dir = run_output_dir / "images"
    report_dir = run_output_dir / "report"
    debug_output_dir = debug_dir if debug_dir is not None else run_output_dir / "debug"

    run_output_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    if debug_preview:
        debug_output_dir.mkdir(parents=True, exist_ok=True)

    resolved_report_path = report_dir / (report_path.name if report_path is not None else "report.csv")

    detected_labels = analyze_pdf_to_labels(
        pdf_path=pdf_path,
        use_fallback_cluster=use_fallback_cluster,
        debug=debug,
    )

    with fitz.open(pdf_path) as doc:
        page_rect_by_index = {
            idx: (page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)
            for idx, page in enumerate(doc)
        }

    exportable_labels, enrich_warnings = enrich_detected_labels(
        detected_labels=detected_labels,
        page_rect_by_index=page_rect_by_index,
        strategy=bbox_strategy,
    )

    export_results = export_labels_from_pdf(
        pdf_path=pdf_path,
        labels=exportable_labels,
        output_dir=image_dir,
        target_width=image_width,
        target_height=image_height,
        jpeg_quality=jpg_quality,
    )

    manifest_path = write_manifest(report_path=resolved_report_path, labels=exportable_labels, results=export_results)

    preview_paths: list[str] = []
    if debug_preview:
        # Preview consumes the same exportable_labels list as exporter to avoid bbox divergence.
        preview_paths = [
            str(path)
            for path in export_debug_previews(
                pdf_path=pdf_path,
                labels=exportable_labels,
                output_dir=debug_output_dir,
            )
        ]

    source_pdf_deleted = False
    source_pdf_delete_error = ""
    all_exports_succeeded = all(item.success for item in export_results)
    if delete_source_on_success and all_exports_succeeded:
        source_pdf_deleted, source_pdf_delete_error = try_delete_source_pdf(pdf_path=pdf_path, enabled=True)

    return LabelExportPipelineResult(
        detected_labels=detected_labels,
        exportable_labels=exportable_labels,
        export_results=export_results,
        enrich_warnings=enrich_warnings,
        run_output_dir=str(run_output_dir),
        image_dir=str(image_dir),
        report_path=str(manifest_path),
        preview_paths=preview_paths,
        source_pdf_deleted=source_pdf_deleted,
        source_pdf_delete_error=source_pdf_delete_error,
    )
