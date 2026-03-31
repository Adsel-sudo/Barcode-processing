"""Pipeline orchestration for PDF barcode label export."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from barcode_tool.models.types import BarcodeLabel, LabelExportResult
from barcode_tool.services.crop_exporter import export_labels_from_pdf
from barcode_tool.services.debug_preview import export_debug_previews
from barcode_tool.services.label_analyzer import analyze_pdf_to_labels
from barcode_tool.services.manifest_writer import write_manifest


@dataclass(slots=True)
class LabelExportPipelineResult:
    labels: list[BarcodeLabel] = field(default_factory=list)
    export_results: list[LabelExportResult] = field(default_factory=list)
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
) -> LabelExportPipelineResult:
    """Run full workflow: detect labels -> export JPG -> write report -> optional preview."""
    labels = analyze_pdf_to_labels(
        pdf_path=pdf_path,
        use_fallback_cluster=use_fallback_cluster,
        debug=debug,
    )

    export_results = export_labels_from_pdf(
        pdf_path=pdf_path,
        labels=labels,
        output_dir=output_dir,
        target_width=image_width,
        target_height=image_height,
        jpeg_quality=jpg_quality,
    )

    manifest_path = write_manifest(report_path=report_path, labels=labels, results=export_results)

    preview_paths: list[str] = []
    if debug_preview:
        preview_output_dir = debug_dir if debug_dir is not None else output_dir / "debug"
        preview_paths = [
            str(path)
            for path in export_debug_previews(pdf_path=pdf_path, labels=labels, output_dir=preview_output_dir)
        ]

    return LabelExportPipelineResult(
        labels=labels,
        export_results=export_results,
        report_path=str(manifest_path),
        preview_paths=preview_paths,
    )
