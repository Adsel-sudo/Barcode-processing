"""Task runner adapter: call existing label export pipeline with minimal wrapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from barcode_tool.pipeline.label_export_pipeline import run_label_export_pipeline


@dataclass(slots=True)
class TaskResult:
    task_id: str
    source_pdf_path: Path
    run_output_dir: Path
    report_path: Path
    exported_count: int
    failed_count: int
    all_exports_succeeded: bool
    report_generated: bool
    source_pdf_deleted: bool
    source_pdf_delete_error: str
    elapsed_seconds: float



def run_pdf_task(
    *,
    task_id: str,
    pdf_path: Path,
    output_base_dir: Path,
    delete_source_on_success: bool = False,
    debug_preview: bool = False,
) -> TaskResult:
    """Run current PDF label pipeline without changing core behavior.

    For Feishu closed-loop safety we default to `delete_source_on_success=False`.
    Caller may decide final deletion policy after upload succeeds.
    """
    started = perf_counter()

    result = run_label_export_pipeline(
        pdf_path=pdf_path,
        output_dir=output_base_dir,
        delete_source_on_success=delete_source_on_success,
        debug_preview=debug_preview,
    )

    exported_count = sum(1 for item in result.export_results if item.success)
    failed_count = sum(1 for item in result.export_results if not item.success)

    report_path = Path(result.report_path)
    return TaskResult(
        task_id=task_id,
        source_pdf_path=pdf_path,
        run_output_dir=Path(result.run_output_dir),
        report_path=report_path,
        exported_count=exported_count,
        failed_count=failed_count,
        all_exports_succeeded=(failed_count == 0 and len(result.export_results) > 0),
        report_generated=report_path.exists(),
        source_pdf_deleted=result.source_pdf_deleted,
        source_pdf_delete_error=result.source_pdf_delete_error,
        elapsed_seconds=perf_counter() - started,
    )
