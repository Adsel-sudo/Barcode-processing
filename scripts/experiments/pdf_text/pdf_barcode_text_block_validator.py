#!/usr/bin/env python3
"""
基于 PDF 原始文本 + 坐标的条码块三行文本验证脚本（无需 OCR）。

工程化重构说明：
- 三行识别与 candidate_filename 提取逻辑已提炼到 `barcode_tool.services.label_analyzer`；
- 本脚本保留原有 CLI 调试/批量/JSON 输出能力；
- 后续导出模块可直接复用 `analyze_page_to_labels / analyze_pdf_to_labels`。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import fitz

from barcode_tool.models.types import DetectedLabel
from barcode_tool.services.label_analyzer import analyze_pdf_to_labels

BBox = Tuple[float, float, float, float]


@dataclass
class BarcodeBlockResult:
    page_index: int
    source: str
    block_bbox: BBox
    first_line: str
    second_line: str
    third_line: str
    candidate_filename: str
    line_count: int


@dataclass
class FileResult:
    file_path: str
    total_pages: int
    total_candidates: int
    results: List[BarcodeBlockResult]


def round_bbox(bbox: BBox, digits: int = 2) -> BBox:
    return tuple(round(v, digits) for v in bbox)  # type: ignore[return-value]


def _label_to_result(label: DetectedLabel) -> BarcodeBlockResult:
    return BarcodeBlockResult(
        page_index=label.page_index + 1,
        source=label.source,
        block_bbox=round_bbox(label.text_bbox),
        first_line=label.first_line,
        second_line=label.second_line,
        third_line=label.third_line,
        candidate_filename=label.candidate_filename,
        line_count=label.line_count,
    )


def analyze_pdf(pdf_path: Path, use_fallback: bool = True, debug: bool = True) -> FileResult:
    labels = analyze_pdf_to_labels(
        pdf_path=pdf_path,
        use_fallback_cluster=use_fallback,
        debug=debug,
    )

    with fitz.open(pdf_path) as doc:
        total_pages = len(doc)

    results = [_label_to_result(label) for label in labels]
    return FileResult(
        file_path=str(pdf_path),
        total_pages=total_pages,
        total_candidates=len(results),
        results=results,
    )


def iter_pdf_files(input_path: Path, batch: bool) -> Iterable[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        yield input_path
        return

    if input_path.is_dir() and batch:
        for path in sorted(input_path.glob("*.pdf")):
            yield path
        return

    raise ValueError("输入路径无效：单文件模式需要 PDF 文件；批量模式需要目录并加 --batch")


def print_human_report(file_result: FileResult) -> None:
    print("=" * 110)
    print(f"文件: {file_result.file_path}")
    print(f"页数: {file_result.total_pages} | 条码块候选: {file_result.total_candidates}")
    print("=" * 110)

    if not file_result.results:
        print("[提示] 未识别到满足“至少三行文本”的条码块候选。")
        return

    for idx, item in enumerate(file_result.results, start=1):
        print(f"\n[{idx}] page={item.page_index} source={item.source} line_count={item.line_count}")
        print(f"    block_bbox={item.block_bbox}")
        print(f"    第一行: {item.first_line}")
        print(f"    第二行: {item.second_line}")
        print(f"    第三行: {item.third_line}")
        print(f"    候选文件名: {item.candidate_filename}")


def save_json(all_results: List[FileResult], output: Path) -> None:
    payload: Dict[str, Any] = {
        "files": [
            {
                "file_path": item.file_path,
                "total_pages": item.total_pages,
                "total_candidates": item.total_candidates,
                "results": [asdict(row) for row in item.results],
            }
            for item in all_results
        ]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="条码块三行文本验证（基于 PDF 原始文本与坐标）")
    parser.add_argument("input_path", type=Path, help="PDF 文件路径，或批量模式下的目录")
    parser.add_argument("--batch", action="store_true", help="批量处理目录下所有 PDF")
    parser.add_argument(
        "--no-line-cluster-fallback",
        action="store_false",
        dest="line_cluster_fallback",
        default=True,
        help="关闭全页按 x 坐标列聚类主流程（默认开启）",
    )
    parser.add_argument("--no-debug", action="store_true", help="关闭按列与分组调试输出")
    parser.add_argument("--json-out", type=Path, default=None, help="输出结构化 JSON 结果")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        pdf_files = list(iter_pdf_files(args.input_path, batch=args.batch))
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if not pdf_files:
        print("[ERROR] 未找到 PDF 文件。", file=sys.stderr)
        return 3

    all_results: List[FileResult] = []

    for pdf_path in pdf_files:
        try:
            file_result = analyze_pdf(
                pdf_path,
                use_fallback=args.line_cluster_fallback,
                debug=not args.no_debug,
            )
        except Exception as exc:
            print(f"[ERROR] 处理失败: {pdf_path} -> {exc}", file=sys.stderr)
            continue

        all_results.append(file_result)
        print_human_report(file_result)

    if args.json_out is not None:
        save_json(all_results, args.json_out)
        print(f"\n已输出 JSON: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
