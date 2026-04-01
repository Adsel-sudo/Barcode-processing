#!/usr/bin/env python3
"""CLI entrypoint for batch exporting barcode labels from one PDF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_project_src_on_path() -> None:
    """从任意工作目录运行本脚本时，将仓库 `src` 加入 sys.path（无需先 pip install -e .）。"""
    src = Path(__file__).resolve().parents[3] / "src"
    if src.is_dir():
        s = str(src)
        if s not in sys.path:
            sys.path.insert(0, s)


_ensure_project_src_on_path()

from barcode_tool.pipeline.label_export_pipeline import run_label_export_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export barcode labels from PDF")
    parser.add_argument("input_pdf", type=Path, help="Input PDF path")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for JPG files")
    parser.add_argument("--report", type=Path, default=None, help="Report file path (.csv or .xlsx)")
    parser.add_argument("--image-width", type=int, default=589, help="Output image width in px")
    parser.add_argument("--image-height", type=int, default=386, help="Output image height in px")
    parser.add_argument("--jpg-quality", type=int, default=95, help="JPG quality")
    parser.add_argument("--debug-preview", action="store_true", help="Render debug preview with label_bbox overlays")
    parser.add_argument(
        "--use-fallback-cluster",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable x-coordinate fallback clustering logic",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_pdf: Path = args.input_pdf
    output_dir: Path = args.output_dir
    report_path: Path = args.report or output_dir / "report.csv"

    if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
        parser.error("input_pdf must be an existing PDF file")

    result = run_label_export_pipeline(
        pdf_path=input_pdf,
        output_dir=output_dir,
        report_path=report_path,
        image_width=args.image_width,
        image_height=args.image_height,
        jpg_quality=args.jpg_quality,
        use_fallback_cluster=args.use_fallback_cluster,
        debug_preview=args.debug_preview,
    )

    success_count = sum(1 for item in result.export_results if item.success)
    fail_count = len(result.export_results) - success_count

    print("=" * 88)
    print(f"PDF: {input_pdf}")
    print(
        f"detected: {len(result.detected_labels)} | exportable: {len(result.exportable_labels)} | "
        f"success: {success_count} | failed: {fail_count}"
    )
    print(f"report: {result.report_path}")
    if result.enrich_warnings:
        print(f"enrich warnings: {len(result.enrich_warnings)}")
        for w in result.enrich_warnings[:20]:
            print(f"  - {w}")
        if len(result.enrich_warnings) > 20:
            print(f"  ... and {len(result.enrich_warnings) - 20} more")
    if result.preview_paths:
        print(f"debug previews: {len(result.preview_paths)} files")
    print("=" * 88)

    for item in result.export_results:
        if item.success:
            print(f"[OK] page={item.page_index + 1} group={item.group_index} -> {item.output_path}")
        else:
            print(
                f"[ERR] page={item.page_index + 1} group={item.group_index} "
                f"name={item.candidate_filename} error={item.error_message}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
