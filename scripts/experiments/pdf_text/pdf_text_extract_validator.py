#!/usr/bin/env python3
"""
验证 PDF 是否包含可直接提取的文本（非 OCR）。

功能：
1) 输出每页文本块（block）bbox + 文本内容
2) 输出每个 block 内的行（line）bbox + 文本
3) 输出每行内的 span（可选）bbox + 文本
4) 提供“如何按坐标定位第二行”的建议与示例候选

依赖：
    pip install pymupdf

用法：
    python pdf_text_extract_validator.py /path/to/file.pdf
    python pdf_text_extract_validator.py /path/to/file.pdf --show-spans
    python pdf_text_extract_validator.py /path/to/file.pdf --json-out result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError as e:
    print("[ERROR] 未安装 PyMuPDF，请先执行: pip install pymupdf", file=sys.stderr)
    raise


@dataclass
class SpanInfo:
    text: str
    bbox: Tuple[float, float, float, float]
    size: float
    font: str


@dataclass
class LineInfo:
    text: str
    bbox: Tuple[float, float, float, float]
    spans: List[SpanInfo]


@dataclass
class BlockInfo:
    block_no: int
    block_type: int
    bbox: Tuple[float, float, float, float]
    text: str
    lines: List[LineInfo]


@dataclass
class PageInfo:
    page_index: int
    page_width: float
    page_height: float
    text_block_count: int
    blocks: List[BlockInfo]


def clean_text(s: str) -> str:
    return " ".join((s or "").replace("\n", " ").split()).strip()


def parse_page(page: fitz.Page) -> PageInfo:
    raw = page.get_text("dict")
    blocks: List[BlockInfo] = []

    for b in raw.get("blocks", []):
        block_type = int(b.get("type", -1))
        # PyMuPDF: block_type == 0 表示文本块
        if block_type != 0:
            continue

        lines: List[LineInfo] = []
        block_text_parts: List[str] = []

        for ln in b.get("lines", []):
            spans: List[SpanInfo] = []
            line_text_parts: List[str] = []

            for sp in ln.get("spans", []):
                t = sp.get("text", "")
                line_text_parts.append(t)
                spans.append(
                    SpanInfo(
                        text=t,
                        bbox=tuple(sp.get("bbox", (0, 0, 0, 0))),
                        size=float(sp.get("size", 0.0)),
                        font=str(sp.get("font", "")),
                    )
                )

            line_text = clean_text("".join(line_text_parts))
            if line_text:
                lines.append(
                    LineInfo(
                        text=line_text,
                        bbox=tuple(ln.get("bbox", (0, 0, 0, 0))),
                        spans=spans,
                    )
                )
                block_text_parts.append(line_text)

        block_text = " | ".join(block_text_parts)
        blocks.append(
            BlockInfo(
                block_no=int(b.get("number", -1)),
                block_type=block_type,
                bbox=tuple(b.get("bbox", (0, 0, 0, 0))),
                text=block_text,
                lines=lines,
            )
        )

    page_rect = page.rect
    return PageInfo(
        page_index=page.number,
        page_width=float(page_rect.width),
        page_height=float(page_rect.height),
        text_block_count=len(blocks),
        blocks=blocks,
    )


def print_report(pages: List[PageInfo], show_spans: bool = False) -> None:
    print("=" * 100)
    print("PDF 文本可提取性验证报告（PyMuPDF）")
    print("说明：若能看到大量正确文本 block/line/span，通常说明 PDF 存在可直接提取文本对象（无需 OCR）。")
    print("=" * 100)

    total_blocks = 0
    total_lines = 0

    for p in pages:
        print(f"\n[PAGE {p.page_index + 1}] size=({p.page_width:.2f}, {p.page_height:.2f}) text_blocks={p.text_block_count}")
        total_blocks += p.text_block_count

        for bi, b in enumerate(p.blocks, start=1):
            print(f"  - Block #{bi} (block_no={b.block_no}, type={b.block_type})")
            print(f"    bbox={tuple(round(x, 2) for x in b.bbox)}")
            print(f"    text={b.text!r}")

            for li, ln in enumerate(b.lines, start=1):
                total_lines += 1
                print(f"      Line #{li}: bbox={tuple(round(x, 2) for x in ln.bbox)} text={ln.text!r}")
                if show_spans:
                    for si, sp in enumerate(ln.spans, start=1):
                        print(
                            " " * 8
                            + f"Span #{si}: bbox={tuple(round(x, 2) for x in sp.bbox)} "
                            + f"size={sp.size:.1f} font={sp.font!r} text={sp.text!r}"
                        )

    print("\n" + "=" * 100)
    print(f"汇总: pages={len(pages)}, text_blocks={total_blocks}, lines={total_lines}")

    if total_blocks == 0:
        print("结论倾向: 未检测到文本块（可能是扫描图像 PDF，需 OCR）。")
    else:
        print("结论倾向: 检测到文本块（优先尝试直接提取文本，而非 OCR）。")


def find_second_line_candidates(page: PageInfo) -> List[Dict[str, Any]]:
    """
    针对“每个条码块通常 3 行文字”的场景：
    在同一 block 中，如果 line 数 >= 2，取第 2 行作为候选。
    """
    candidates: List[Dict[str, Any]] = []

    for b in page.blocks:
        if len(b.lines) >= 2:
            l2 = b.lines[1]
            candidates.append(
                {
                    "page": page.page_index + 1,
                    "block_no": b.block_no,
                    "block_bbox": b.bbox,
                    "line2_bbox": l2.bbox,
                    "line2_text": l2.text,
                }
            )
    return candidates


def print_coordinate_strategy(pages: List[PageInfo]) -> None:
    print("\n" + "=" * 100)
    print("如何按坐标定位每个条码块中的第二行（建议）")
    print("=" * 100)
    print("1) 先按 block 分组：每个文本块常对应一个条码旁文字区域。")
    print("2) 对 block 内 lines 按 y0 从小到大排序（从上到下）。")
    print("3) 若该 block 至少有 2 行，lines[1] 即第二行候选（商品描述+目标文件名）。")
    print("4) 可结合规则增强：")
    print("   - 第一行常以 X0 开头；")
    print("   - 第三行常为 New / 新品 / Made in China；")
    print("   - 第二行一般介于两者之间。")
    print("5) 实际截取时，使用 line2_bbox 直接从 PDF 提取文本或做区域验证。")

    shown = 0
    for p in pages:
        cands = find_second_line_candidates(p)
        if not cands:
            continue
        print(f"\n[PAGE {p.page_index + 1}] 第二行候选示例（最多展示 8 条）")
        for c in cands[:8]:
            shown += 1
            print(
                f"  block_no={c['block_no']}, "
                f"block_bbox={tuple(round(x, 2) for x in c['block_bbox'])}, "
                f"line2_bbox={tuple(round(x, 2) for x in c['line2_bbox'])}, "
                f"line2_text={c['line2_text']!r}"
            )

    if shown == 0:
        print("未找到满足“block 内至少 2 行”的候选。可能文本并未按预期分块，可改用全页按 y 聚类方式识别 3 行结构。")


def to_json_ready(pages: List[PageInfo]) -> Dict[str, Any]:
    return {
        "pages": [asdict(p) for p in pages],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 PDF 文本是否可直接提取，并输出 block/line 坐标。")
    parser.add_argument("pdf_path", type=Path, help="PDF 文件路径")
    parser.add_argument("--show-spans", action="store_true", help="打印每行 span 级别信息")
    parser.add_argument("--json-out", type=Path, default=None, help="将完整结构化结果写入 JSON 文件")
    args = parser.parse_args()

    if not args.pdf_path.exists() or not args.pdf_path.is_file():
        print(f"[ERROR] 文件不存在: {args.pdf_path}", file=sys.stderr)
        return 2

    try:
        doc = fitz.open(args.pdf_path)
    except Exception as e:
        print(f"[ERROR] 打开 PDF 失败: {e}", file=sys.stderr)
        return 3

    pages: List[PageInfo] = []
    for i in range(len(doc)):
        pages.append(parse_page(doc[i]))

    print_report(pages, show_spans=args.show_spans)
    print_coordinate_strategy(pages)

    if args.json_out is not None:
        data = to_json_ready(pages)
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写出 JSON: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
