"""Pipeline orchestration for PDF barcode label export."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz

from barcode_tool.models.types import DetectedLabel, ExportableLabel, LabelExportResult
from barcode_tool.services.crop_exporter import export_labels_from_pdf
from barcode_tool.services.debug_preview import export_debug_previews
from barcode_tool.services.label_analyzer import analyze_pdf_to_labels
from barcode_tool.services.label_enricher import enrich_detected_labels
from barcode_tool.services.manifest_writer import write_manifest


@dataclass(slots=True)
class LabelExportPipelineResult:
    detected_labels: list[DetectedLabel] = field(default_factory=list)
    exportable_labels: list[ExportableLabel] = field(default_factory=list)
    export_results: list[LabelExportResult] = field(default_factory=list)
    enrich_warnings: list[str] = field(default_factory=list)
    report_path: str = ""
    preview_paths: list[str] = field(default_factory=list)


def run_label_export_pipeline(
    pdf_path: Path,
    output_dir: Path,
    report_path: Path,
    image_width: int = 589,
    image_height: int = 386,
    jpg_quality: int = 95,
    use_fallback_cluster: bool = True,
    debug_preview: bool = False,
    debug_dir: Path | None = None,
    debug: bool = False,
    bbox_strategy: str = "default",
) -> LabelExportPipelineResult:
    """Run full workflow: analyze -> enrich -> export -> manifest -> optional preview."""
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
        output_dir=output_dir,
        target_width=image_width,
        target_height=image_height,
        jpeg_quality=jpg_quality,
    )

    manifest_path = write_manifest(report_path=report_path, labels=exportable_labels, results=export_results)

    preview_paths: list[str] = []
    if debug_preview:
        # Preview consumes the same exportable_labels list as exporter to avoid bbox divergence.
        preview_output_dir = debug_dir if debug_dir is not None else output_dir / "debug"
        preview_paths = [
            str(path)
            for path in export_debug_previews(pdf_path=pdf_path, labels=exportable_labels, output_dir=preview_output_dir)
        ]

    return LabelExportPipelineResult(
        detected_labels=detected_labels,
        exportable_labels=exportable_labels,
        export_results=export_results,
        enrich_warnings=enrich_warnings,
        report_path=str(manifest_path),
        preview_paths=preview_paths,
    )
