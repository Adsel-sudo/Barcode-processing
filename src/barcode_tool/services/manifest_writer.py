"""Write export manifest files (CSV / Excel)."""

from __future__ import annotations

import csv
import importlib
import importlib.util
from pathlib import Path

from barcode_tool.models.types import BarcodeLabel, LabelExportResult


MANIFEST_FIELDS = [
    "page_index",
    "group_index",
    "candidate_filename",
    "first_line",
    "second_line",
    "third_line",
    "text_bbox",
    "label_bbox",
    "output_path",
    "success",
    "error_message",
]


def _to_row(label: BarcodeLabel, result: LabelExportResult) -> dict[str, object]:
    return {
        "page_index": label.page_index,
        "group_index": label.group_index,
        "candidate_filename": label.candidate_filename,
        "first_line": label.first_line,
        "second_line": label.second_line,
        "third_line": label.third_line,
        "text_bbox": label.text_bbox,
        "label_bbox": label.label_bbox,
        "output_path": result.output_path,
        "success": result.success,
        "error_message": result.error_message,
    }


def write_manifest_csv(report_path: Path, labels: list[BarcodeLabel], results: list[LabelExportResult]) -> Path:
    """Write manifest as CSV."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for label, result in zip(labels, results):
            writer.writerow(_to_row(label, result))
    return report_path


def write_manifest_excel(report_path: Path, labels: list[BarcodeLabel], results: list[LabelExportResult]) -> Path:
    """Write manifest as Excel (.xlsx)."""
    if importlib.util.find_spec("pandas") is None:
        raise RuntimeError("Excel export requires pandas/openpyxl. Please install optional dependencies.")

    pandas = importlib.import_module("pandas")
    rows = [_to_row(label, result) for label, result in zip(labels, results)]
    df = pandas.DataFrame(rows, columns=MANIFEST_FIELDS)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(report_path, index=False)
    return report_path


def write_manifest(report_path: Path, labels: list[BarcodeLabel], results: list[LabelExportResult]) -> Path:
    """Write manifest by file extension: .csv or .xlsx."""
    suffix = report_path.suffix.lower()
    if suffix == ".xlsx":
        return write_manifest_excel(report_path, labels, results)
    return write_manifest_csv(report_path, labels, results)
