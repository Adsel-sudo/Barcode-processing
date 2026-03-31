#!/usr/bin/env python3
"""
批量样本验证脚本

用途：
- 遍历目录中的条码块图片
- 调用 ocr_filename_validator 的核心能力做逐图识别
- 导出 CSV / Excel 明细，并输出整体统计

说明：
- 默认把“图片文件名（不含扩展名）”作为标准答案
- 便于后续接 PDF：目前核心是 process_single_image，可在 PDF 切图后复用
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ocr_filename_validator import (
    build_lines_from_tokens,
    classify_three_lines,
    extract_candidate_filename,
    run_ocr,
    validate_candidate,
)


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class SampleResult:
    image_filename: str
    first_line: str
    second_line: str
    third_line: str
    extracted_filename: str
    is_valid: bool
    reasons: str
    expected_answer: str
    is_match_expected: Optional[bool]


@dataclass
class BatchStats:
    total: int
    success: int
    fail: int
    recognized: int
    with_expected: int
    matched_expected: int

    @property
    def recognition_rate(self) -> float:
        return (self.recognized / self.total) if self.total else 0.0

    @property
    def pass_rate(self) -> float:
        return (self.success / self.total) if self.total else 0.0

    @property
    def hit_rate(self) -> float:
        """命中率：仅在有标准答案样本中计算。"""
        return (self.matched_expected / self.with_expected) if self.with_expected else 0.0


def list_images(input_dir: Path) -> List[Path]:
    files = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    return sorted(files, key=lambda p: p.name)


def bool_to_cn(value: Optional[bool]) -> str:
    if value is None:
        return ""
    return "是" if value else "否"


def process_single_image(image_path: Path, backend: str, compare_with_filename: bool) -> SampleResult:
    """单图处理（后续可直接被 PDF 拆图流程复用）。"""
    try:
        ocr_result = run_ocr(image_path=image_path, backend=backend)
        lines, _line_debug = build_lines_from_tokens(ocr_result.tokens)
        selection = classify_three_lines(lines)

        first_line = selection.first_line.text if selection.first_line else ""
        second_line = selection.second_line.text if selection.second_line else ""
        third_line = selection.third_line.text if selection.third_line else ""

        candidate = extract_candidate_filename(second_line)
        passed, reasons = validate_candidate(candidate)

        expected = image_path.stem if compare_with_filename else ""
        is_match: Optional[bool] = None
        if compare_with_filename:
            is_match = candidate.strip().lower() == expected.strip().lower()

        return SampleResult(
            image_filename=image_path.name,
            first_line=first_line,
            second_line=second_line,
            third_line=third_line,
            extracted_filename=candidate,
            is_valid=passed,
            reasons="; ".join(reasons),
            expected_answer=expected,
            is_match_expected=is_match,
        )
    except Exception as exc:
        expected = image_path.stem if compare_with_filename else ""
        return SampleResult(
            image_filename=image_path.name,
            first_line="",
            second_line="",
            third_line="",
            extracted_filename="",
            is_valid=False,
            reasons=f"OCR/处理异常: {exc}",
            expected_answer=expected,
            is_match_expected=False if compare_with_filename else None,
        )


def build_stats(results: Sequence[SampleResult]) -> BatchStats:
    total = len(results)
    success = sum(1 for r in results if r.is_valid)
    fail = total - success
    recognized = sum(1 for r in results if bool(r.extracted_filename))

    with_expected = sum(1 for r in results if r.expected_answer != "")
    matched_expected = sum(1 for r in results if r.is_match_expected is True)

    return BatchStats(
        total=total,
        success=success,
        fail=fail,
        recognized=recognized,
        with_expected=with_expected,
        matched_expected=matched_expected,
    )


def write_csv(results: Sequence[SampleResult], out_path: Path) -> None:
    fieldnames = [
        "图片文件名",
        "OCR整理后的第一行",
        "OCR整理后的第二行",
        "OCR整理后的第三行",
        "提取结果",
        "是否通过合法性校验",
        "异常原因",
        "标准答案(文件名去扩展)",
        "是否与标准答案一致",
    ]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "图片文件名": r.image_filename,
                    "OCR整理后的第一行": r.first_line,
                    "OCR整理后的第二行": r.second_line,
                    "OCR整理后的第三行": r.third_line,
                    "提取结果": r.extracted_filename,
                    "是否通过合法性校验": "是" if r.is_valid else "否",
                    "异常原因": r.reasons,
                    "标准答案(文件名去扩展)": r.expected_answer,
                    "是否与标准答案一致": bool_to_cn(r.is_match_expected),
                }
            )


def write_excel(results: Sequence[SampleResult], out_path: Path) -> None:
    """按需导出 Excel（可选依赖 pandas/openpyxl）。"""
    try:
        import pandas as pd
    except Exception as exc:
        raise RuntimeError("导出 Excel 需要安装 pandas 与 openpyxl") from exc

    rows: List[Dict[str, Any]] = []
    for r in results:
        rows.append(
            {
                "图片文件名": r.image_filename,
                "OCR整理后的第一行": r.first_line,
                "OCR整理后的第二行": r.second_line,
                "OCR整理后的第三行": r.third_line,
                "提取结果": r.extracted_filename,
                "是否通过合法性校验": "是" if r.is_valid else "否",
                "异常原因": r.reasons,
                "标准答案(文件名去扩展)": r.expected_answer,
                "是否与标准答案一致": bool_to_cn(r.is_match_expected),
            }
        )

    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False)


def export_results(results: Sequence[SampleResult], output_path: Path) -> None:
    suffix = output_path.suffix.lower()
    if suffix == ".csv":
        write_csv(results, output_path)
        return
    if suffix in {".xlsx", ".xls"}:
        write_excel(results, output_path)
        return
    raise ValueError("输出文件仅支持 .csv / .xlsx / .xls")


def print_stats(stats: BatchStats) -> None:
    print("=" * 80)
    print("批量验证统计")
    print("=" * 80)
    print(f"样本总数: {stats.total}")
    print(f"成功数(通过合法性校验): {stats.success}")
    print(f"失败数(未通过合法性校验): {stats.fail}")
    print(f"识别率(提取结果非空): {stats.recognition_rate:.2%} ({stats.recognized}/{stats.total})")
    print(f"通过率: {stats.pass_rate:.2%} ({stats.success}/{stats.total})")
    if stats.with_expected:
        print(f"命中率(与标准答案一致): {stats.hit_rate:.2%} ({stats.matched_expected}/{stats.with_expected})")
    else:
        print("命中率: N/A（未启用或无标准答案）")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="条码 OCR 批量样本验证")
    parser.add_argument("input_dir", type=Path, help="图片目录")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("batch_validation_report.csv"),
        help="输出文件路径（.csv 或 .xlsx）",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "paddle", "tesseract"],
        default="auto",
        help="OCR 后端（默认 auto）",
    )
    parser.add_argument(
        "--no-compare-filename",
        action="store_true",
        help="关闭“文件名(去扩展)作为标准答案”比对",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_path: Path = args.output
    compare_with_filename = not args.no_compare_filename

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"[ERROR] 输入目录不存在或不是目录: {input_dir}")
        return 2

    images = list_images(input_dir)
    if not images:
        print(f"[ERROR] 目录中未找到支持的图片文件: {input_dir}")
        return 3

    print(f"发现样本数: {len(images)}")
    results: List[SampleResult] = []
    for idx, image_path in enumerate(images, start=1):
        print(f"[{idx}/{len(images)}] 处理: {image_path.name}")
        item = process_single_image(
            image_path=image_path,
            backend=args.backend,
            compare_with_filename=compare_with_filename,
        )
        results.append(item)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_results(results, output_path)
    print(f"\n明细已导出: {output_path}")

    stats = build_stats(results)
    print_stats(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
