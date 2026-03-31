#!/usr/bin/env python3
"""
基于 PDF 原始文本 + 坐标的条码块三行文本验证脚本（无需 OCR）。

目标：
1) 在 PDF 中识别每个条码块对应的三行文字；
2) 利用坐标把属于同一个条码块的文本聚合；
3) 定位第二行文本；
4) 解析候选文件名：
   - 有逗号 -> 取最后一个逗号后的内容
   - 无逗号 -> 取最后一个空格后的内容
5) 输出每个条码块的：第一行/第二行/第三行/候选文件名

依赖：
    pip install pymupdf

用法：
    # 单文件
    python pdf_barcode_text_block_validator.py /path/to/file.pdf

    # 批量（目录下所有 PDF）
    python pdf_barcode_text_block_validator.py /path/to/pdf_dir --batch

    # 输出 JSON 供后续处理
    python pdf_barcode_text_block_validator.py /path/to/file.pdf --json-out result.json

说明：
- 默认以“文本块(block)内行聚合”为主；
- 当 block 拆分异常时，可用 --line-cluster-fallback 开启“全页行聚类兜底”。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    print("[ERROR] 未安装 PyMuPDF，请先执行: pip install pymupdf", file=sys.stderr)
    raise


BBox = Tuple[float, float, float, float]


@dataclass
class PDFLine:
    text: str
    bbox: BBox


@dataclass
class BarcodeBlockResult:
    page_index: int
    source: str  # block / fallback-line-cluster
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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def round_bbox(bbox: BBox, digits: int = 2) -> BBox:
    return tuple(round(v, digits) for v in bbox)  # type: ignore[return-value]


def extract_candidate_filename(line2: str) -> str:
    """根据规则提取候选文件名。"""
    value = clean_text(line2)
    if not value:
        return ""

    normalized = value.replace("，", ",")
    if "," in normalized:
        return clean_text(normalized.rsplit(",", 1)[-1])

    if " " in normalized:
        return clean_text(normalized.rsplit(" ", 1)[-1])

    return normalized


def parse_page_lines(page: fitz.Page) -> List[PDFLine]:
    raw = page.get_text("dict")
    lines: List[PDFLine] = []

    for block in raw.get("blocks", []):
        if int(block.get("type", -1)) != 0:
            continue
        for ln in block.get("lines", []):
            spans = ln.get("spans", [])
            text = clean_text("".join(str(sp.get("text", "")) for sp in spans))
            if not text:
                continue
            lines.append(
                PDFLine(
                    text=text,
                    bbox=tuple(ln.get("bbox", (0.0, 0.0, 0.0, 0.0))),  # type: ignore[arg-type]
                )
            )

    lines.sort(key=lambda x: (x.bbox[1], x.bbox[0]))
    return lines


def parse_page_blocks(page: fitz.Page) -> List[Tuple[BBox, List[PDFLine]]]:
    """提取文本块，并把块内 line 按 y/x 排序。"""
    raw = page.get_text("dict")
    blocks: List[Tuple[BBox, List[PDFLine]]] = []

    for block in raw.get("blocks", []):
        if int(block.get("type", -1)) != 0:
            continue

        block_bbox = tuple(block.get("bbox", (0.0, 0.0, 0.0, 0.0)))  # type: ignore[arg-type]
        lines: List[PDFLine] = []
        for ln in block.get("lines", []):
            spans = ln.get("spans", [])
            text = clean_text("".join(str(sp.get("text", "")) for sp in spans))
            if not text:
                continue
            lines.append(
                PDFLine(
                    text=text,
                    bbox=tuple(ln.get("bbox", (0.0, 0.0, 0.0, 0.0))),  # type: ignore[arg-type]
                )
            )

        if not lines:
            continue

        lines.sort(key=lambda x: (x.bbox[1], x.bbox[0]))
        blocks.append((block_bbox, lines))

    blocks.sort(key=lambda x: (x[0][1], x[0][0]))
    return blocks


def choose_three_lines(lines: Sequence[PDFLine]) -> Optional[Tuple[str, str, str]]:
    """从聚合后的行中拿三行：默认取前 3 行（自上而下）。"""
    if len(lines) < 3:
        return None
    return lines[0].text, lines[1].text, lines[2].text


def cluster_lines_by_x(lines: Sequence[PDFLine], x_threshold: float = 80.0) -> List[List[PDFLine]]:
    """兜底：当 block 切分异常时，按 x 左边界聚类（同一列区域倾向属于同条码块）。"""
    if not lines:
        return []

    ordered = sorted(lines, key=lambda ln: (ln.bbox[0], ln.bbox[1]))
    clusters: List[List[PDFLine]] = []
    anchors: List[float] = []

    for ln in ordered:
        x0 = ln.bbox[0]
        if not clusters:
            clusters.append([ln])
            anchors.append(x0)
            continue

        distances = [abs(x0 - a) for a in anchors]
        idx = min(range(len(distances)), key=distances.__getitem__)
        if distances[idx] <= x_threshold:
            clusters[idx].append(ln)
            anchors[idx] = sum(item.bbox[0] for item in clusters[idx]) / len(clusters[idx])
        else:
            clusters.append([ln])
            anchors.append(x0)

    for c in clusters:
        c.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))

    return clusters


def bbox_union(lines: Sequence[PDFLine]) -> BBox:
    x0 = min(ln.bbox[0] for ln in lines)
    y0 = min(ln.bbox[1] for ln in lines)
    x1 = max(ln.bbox[2] for ln in lines)
    y1 = max(ln.bbox[3] for ln in lines)
    return (x0, y0, x1, y1)


def analyze_pdf(pdf_path: Path, use_fallback: bool = False) -> FileResult:
    doc = fitz.open(pdf_path)
    results: List[BarcodeBlockResult] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]

        # 主流程：直接使用 block
        for block_bbox, lines in parse_page_blocks(page):
            chosen = choose_three_lines(lines)
            if chosen is None:
                continue
            first, second, third = chosen
            results.append(
                BarcodeBlockResult(
                    page_index=page_idx + 1,
                    source="block",
                    block_bbox=round_bbox(block_bbox),
                    first_line=first,
                    second_line=second,
                    third_line=third,
                    candidate_filename=extract_candidate_filename(second),
                    line_count=len(lines),
                )
            )

        if not use_fallback:
            continue

        # 兜底流程：全页按 x 聚类后再取前 3 行
        page_lines = parse_page_lines(page)
        for cluster in cluster_lines_by_x(page_lines):
            chosen = choose_three_lines(cluster)
            if chosen is None:
                continue
            first, second, third = chosen
            results.append(
                BarcodeBlockResult(
                    page_index=page_idx + 1,
                    source="fallback-line-cluster",
                    block_bbox=round_bbox(bbox_union(cluster)),
                    first_line=first,
                    second_line=second,
                    third_line=third,
                    candidate_filename=extract_candidate_filename(second),
                    line_count=len(cluster),
                )
            )

    return FileResult(
        file_path=str(pdf_path),
        total_pages=len(doc),
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
        "--line-cluster-fallback",
        action="store_true",
        help="开启全页按 x 坐标聚类兜底（当原始 block 切分异常时有帮助）",
    )
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
            file_result = analyze_pdf(pdf_path, use_fallback=args.line_cluster_fallback)
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
