#!/usr/bin/env python3
"""
更稳健的条码 OCR 验证脚本：
- 先把 OCR 检测框按几何位置整理成“行”
- 自动识别第一/第二/第三行
- 提取并校验候选文件名
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple


THIRD_LINE_KEYWORDS = ["new", "新品", "made in china"]


@dataclass
class OCRToken:
    """OCR 文本块。"""

    text: str
    x1: float
    y1: float
    x2: float
    y2: float
    score: Optional[float] = None

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def h(self) -> float:
        return max(1.0, self.y2 - self.y1)


@dataclass
class OCRResult:
    """统一 OCR 输出结构。"""

    raw: Any
    tokens: List[OCRToken]


@dataclass
class MergedLine:
    """由多个 token 合并得到的一行。"""

    text: str
    tokens: List[OCRToken]
    y_center: float


@dataclass
class LineSelection:
    """自动判断的三行结果。"""

    first_line: Optional[MergedLine]
    second_line: Optional[MergedLine]
    third_line: Optional[MergedLine]
    debug: Dict[str, Any]


def clean_text(text: str) -> str:
    """清洗字符串首尾符号与空白。"""
    if text is None:
        return ""
    value = str(text).strip()
    value = value.strip(" \t\r\n,，.。:：;；|/\\-_·")
    return value


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_compare(text: str) -> str:
    """用于匹配的规范化：大小写、空白、常见 OCR 标点误差。"""
    value = clean_text(text).lower()
    # 常见 OCR 标点混淆归一
    value = value.replace("，", ",").replace("。", ".").replace("：", ":")
    value = normalize_spaces(value)
    return value


def normalize_alnum(text: str) -> str:
    """保留字母数字和中文，去除空格/标点，便于模糊匹配。"""
    value = normalize_for_compare(text)
    # 仅保留英文数字中文
    return "".join(ch for ch in value if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def levenshtein_distance(a: str, b: str) -> int:
    """最小编辑距离（小字符串足够快）。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            rep = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, dele, rep))
        prev = cur
    return prev[-1]


def is_probable_third_line(text: str) -> Tuple[bool, str]:
    """第三行判定：大小写不敏感 + 轻微 OCR 偏差容忍。"""
    norm = normalize_for_compare(text)
    compact = normalize_alnum(text)

    # 精确/包含优先
    if norm in THIRD_LINE_KEYWORDS:
        return True, f"exact:{norm}"
    for kw in THIRD_LINE_KEYWORDS:
        if kw.replace(" ", "") in compact:
            return True, f"contains:{kw}"

    # 轻微偏差：编辑距离阈值（随长度变化）
    for kw in THIRD_LINE_KEYWORDS:
        target = normalize_alnum(kw)
        dist = levenshtein_distance(compact, target)
        threshold = 1 if len(target) <= 4 else 2
        if dist <= threshold:
            return True, f"fuzzy:{kw},dist={dist}"

    return False, "no-match"


def is_probable_first_line(text: str) -> Tuple[bool, str]:
    """第一行判定：X0 开头，允许 O/0 混淆与轻微噪声。"""
    raw = normalize_for_compare(text)
    compact = "".join(ch for ch in raw if ch.isalnum())
    if not compact:
        return False, "empty"

    # 纠正第二位常见混淆 O->0 / Q->0 / D->0
    chars = list(compact)
    if len(chars) >= 2 and chars[1] in {"o", "q", "d"}:
        chars[1] = "0"
    fixed = "".join(chars)

    if fixed.startswith("x0"):
        return True, f"prefix:{fixed[:4]}"

    # 再做微弱模糊，防止首字符被识别成 K/H 等
    if len(fixed) >= 2:
        dist = levenshtein_distance(fixed[:2], "x0")
        if dist <= 1:
            return True, f"fuzzy-prefix:{fixed[:2]},dist={dist}"

    return False, f"prefix-miss:{fixed[:4]}"


def merge_token_texts(tokens: Sequence[OCRToken]) -> str:
    """同一行 token 拼接，尽量减少错误空格。"""
    parts: List[str] = []
    for idx, tk in enumerate(tokens):
        t = clean_text(tk.text)
        if not t:
            continue
        if not parts:
            parts.append(t)
            continue

        prev = parts[-1]
        # 当前片段如果是标点，直接贴上
        if re.fullmatch(r"[,.，。:：;；)\]】]+", t):
            parts[-1] = prev + t
            continue
        # 上一片段如果以左括号结束，不加空格
        if re.search(r"[(\[【]$", prev):
            parts[-1] = prev + t
            continue

        parts.append(" " + t)

    return normalize_spaces("".join(parts))


def build_lines_from_tokens(tokens: Sequence[OCRToken]) -> Tuple[List[MergedLine], Dict[str, Any]]:
    """
    根据 y 坐标聚类并按 x 拼接。
    返回合并后的行与调试信息。
    """
    debug: Dict[str, Any] = {
        "token_count": len(tokens),
        "cluster_threshold": None,
        "clusters": [],
    }
    if not tokens:
        return [], debug

    sorted_tokens = sorted(tokens, key=lambda t: (t.cy, t.cx))
    heights = [t.h for t in sorted_tokens]
    base_h = median(heights) if heights else 12.0
    y_threshold = max(8.0, base_h * 0.6)
    debug["cluster_threshold"] = y_threshold

    clusters: List[List[OCRToken]] = []
    cluster_y: List[float] = []

    for tk in sorted_tokens:
        if not clusters:
            clusters.append([tk])
            cluster_y.append(tk.cy)
            continue

        # 找最近的行中心
        distances = [abs(tk.cy - cy) for cy in cluster_y]
        min_idx = min(range(len(distances)), key=lambda i: distances[i])
        if distances[min_idx] <= y_threshold:
            clusters[min_idx].append(tk)
            cluster_y[min_idx] = sum(x.cy for x in clusters[min_idx]) / len(clusters[min_idx])
        else:
            clusters.append([tk])
            cluster_y.append(tk.cy)

    merged_lines: List[MergedLine] = []
    for idx, row_tokens in enumerate(clusters):
        row_tokens.sort(key=lambda t: t.x1)
        text = merge_token_texts(row_tokens)
        y_center = sum(t.cy for t in row_tokens) / len(row_tokens)
        if text:
            merged_lines.append(MergedLine(text=text, tokens=row_tokens, y_center=y_center))

        debug["clusters"].append(
            {
                "index": idx,
                "token_count": len(row_tokens),
                "texts": [t.text for t in row_tokens],
                "y_center": round(y_center, 2),
                "merged_text": text,
            }
        )

    merged_lines.sort(key=lambda x: x.y_center)
    return merged_lines, debug


def classify_three_lines(lines: Sequence[MergedLine]) -> LineSelection:
    """第一/第二/第三行自动识别，并输出调试依据。"""
    debug: Dict[str, Any] = {
        "line_count": len(lines),
        "line_scores": [],
        "selected": {},
    }

    first_idx: Optional[int] = None
    third_idx: Optional[int] = None

    for i, line in enumerate(lines):
        first_hit, first_reason = is_probable_first_line(line.text)
        third_hit, third_reason = is_probable_third_line(line.text)
        debug["line_scores"].append(
            {
                "index": i,
                "text": line.text,
                "first_hit": first_hit,
                "first_reason": first_reason,
                "third_hit": third_hit,
                "third_reason": third_reason,
            }
        )

    # 第一行：第一个命中 X0 规则的行
    for i, score in enumerate(debug["line_scores"]):
        if score["first_hit"]:
            first_idx = i
            break

    # 第三行：最后一个命中状态词的行（通常在下方）
    for i in range(len(debug["line_scores"]) - 1, -1, -1):
        if debug["line_scores"][i]["third_hit"]:
            third_idx = i
            break

    second_idx: Optional[int] = None
    if first_idx is not None and third_idx is not None and first_idx < third_idx:
        for i in range(first_idx + 1, third_idx):
            second_idx = i
            break

    # 回退策略
    if second_idx is None and first_idx is not None:
        for i in range(first_idx + 1, len(lines)):
            if i != third_idx:
                second_idx = i
                break

    if second_idx is None and third_idx is not None:
        for i in range(third_idx - 1, -1, -1):
            if i != first_idx:
                second_idx = i
                break

    if second_idx is None and lines:
        for i in range(len(lines)):
            if i not in {first_idx, third_idx}:
                second_idx = i
                break

    debug["selected"] = {
        "first_idx": first_idx,
        "second_idx": second_idx,
        "third_idx": third_idx,
    }

    return LineSelection(
        first_line=lines[first_idx] if first_idx is not None else None,
        second_line=lines[second_idx] if second_idx is not None else None,
        third_line=lines[third_idx] if third_idx is not None else None,
        debug=debug,
    )


def extract_candidate_filename(second_line: Optional[str]) -> str:
    """
    第二行提取规则：
    - 有逗号（中英文）取最后一个逗号后
    - 无逗号取最后一个空格后
    """
    if not second_line:
        return ""

    text = normalize_spaces(second_line)
    # 统一部分易混淆标点
    text = text.replace("，", ",").replace("、", ",").replace("；", ",")

    if "," in text:
        candidate = text.rsplit(",", 1)[-1]
    elif " " in text:
        candidate = text.rsplit(" ", 1)[-1]
    else:
        candidate = text

    return clean_text(candidate)


def validate_candidate(candidate: str) -> Tuple[bool, List[str]]:
    """候选文件名合法性校验。"""
    reasons: List[str] = []
    value = clean_text(candidate)
    norm = normalize_for_compare(value)

    if not value:
        reasons.append("候选值为空")

    # 排除状态词（含轻微偏差）
    third_hit, third_reason = is_probable_third_line(norm)
    if third_hit:
        reasons.append(f"候选值命中排除词: {third_reason}")

    first_hit, first_reason = is_probable_first_line(norm)
    if first_hit:
        reasons.append(f"候选值疑似以 X0 开头: {first_reason}")

    if not (4 <= len(value) <= 30):
        reasons.append("长度不在建议范围 4~30")

    if re.search(r'[<>:"/\\|?*]', value):
        reasons.append("包含文件名常见非法字符")

    return (len(reasons) == 0), reasons


def _bbox_from_quad(quad: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return min(xs), min(ys), max(xs), max(ys)


def run_paddle_ocr(image_path: Path, lang: str = "ch") -> OCRResult:
    """使用 PaddleOCR 识别，并保留检测框。"""
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        raise RuntimeError(f"PaddleOCR 不可用: {exc}") from exc

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    result = ocr.ocr(str(image_path), cls=True)

    tokens: List[OCRToken] = []
    if isinstance(result, list) and result:
        page = result[0] if isinstance(result[0], list) else result
        for item in page:
            if not item or len(item) < 2:
                continue
            box = item[0]
            txt_tuple = item[1]
            if not isinstance(txt_tuple, (tuple, list)) or not txt_tuple:
                continue
            text = str(txt_tuple[0])
            score = float(txt_tuple[1]) if len(txt_tuple) > 1 else None
            x1, y1, x2, y2 = _bbox_from_quad(box)
            if clean_text(text):
                tokens.append(OCRToken(text=text, x1=x1, y1=y1, x2=x2, y2=y2, score=score))

    return OCRResult(raw=result, tokens=tokens)


def run_tesseract_ocr(image_path: Path, lang: str = "chi_sim+eng") -> OCRResult:
    """使用 pytesseract 备选（支持 box 信息）。"""
    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(f"Tesseract 依赖不可用: {exc}") from exc

    image = Image.open(image_path)
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

    tokens: List[OCRToken] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = data["text"][i]
        if not clean_text(text):
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        conf = data.get("conf", [None] * n)[i]
        score: Optional[float] = None
        try:
            score = float(conf) if conf is not None and conf != "-1" else None
        except Exception:
            score = None
        tokens.append(OCRToken(text=text, x1=x, y1=y, x2=x + w, y2=y + h, score=score))

    return OCRResult(raw=data, tokens=tokens)


def run_ocr(image_path: Path, backend: str) -> OCRResult:
    if backend == "paddle":
        return run_paddle_ocr(image_path)
    if backend == "tesseract":
        return run_tesseract_ocr(image_path)
    if backend == "auto":
        try:
            return run_paddle_ocr(image_path)
        except Exception as paddle_error:
            print(f"[WARN] PaddleOCR 失败，尝试 Tesseract。原因: {paddle_error}", file=sys.stderr)
            return run_tesseract_ocr(image_path)
    raise ValueError(f"不支持的 OCR 后端: {backend}")


def format_report(
    image_path: Path,
    ocr_result: OCRResult,
    merged_lines: Sequence[MergedLine],
    selection: LineSelection,
    candidate: str,
    passed: bool,
    reasons: Sequence[str],
    line_debug: Dict[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("=" * 90)
    lines.append(f"图片: {image_path}")
    lines.append("=" * 90)

    lines.append("\n[1] OCR 原始结果")
    lines.append(str(ocr_result.raw))

    lines.append("\n[2] OCR 文本块（含坐标）")
    if ocr_result.tokens:
        for i, tk in enumerate(sorted(ocr_result.tokens, key=lambda t: (t.cy, t.cx)), start=1):
            lines.append(
                f"  {i:02d}. text={tk.text!r}, box=({tk.x1:.1f},{tk.y1:.1f},{tk.x2:.1f},{tk.y2:.1f}), score={tk.score}"
            )
    else:
        lines.append("  (无 token)")

    lines.append("\n[3] 分行聚类结果（按 y 聚类 + 行内按 x 拼接）")
    lines.append(f"  y 聚类阈值: {line_debug.get('cluster_threshold')}")
    for row in line_debug.get("clusters", []):
        lines.append(
            f"  - 行#{row['index']} y={row['y_center']}, token={row['token_count']}, merged={row['merged_text']!r}"
        )
        lines.append(f"    tokens={row['texts']}")

    lines.append("\n[4] 识别出的分行文本（最终排序）")
    if merged_lines:
        for i, row in enumerate(merged_lines, start=1):
            lines.append(f"  {i:02d}. {row.text}")
    else:
        lines.append("  (无文本)")

    lines.append("\n[5] 三行识别调试")
    for score in selection.debug.get("line_scores", []):
        lines.append(
            f"  行#{score['index']} text={score['text']!r} | first={score['first_hit']}({score['first_reason']})"
            f" | third={score['third_hit']}({score['third_reason']})"
        )
    lines.append(f"  选中索引: {selection.debug.get('selected')}")

    lines.append("\n[6] 自动判断出的第一/第二/第三行")
    lines.append(f"  第一行: {selection.first_line.text if selection.first_line else None}")
    lines.append(f"  第二行: {selection.second_line.text if selection.second_line else None}")
    lines.append(f"  第三行: {selection.third_line.text if selection.third_line else None}")

    lines.append("\n[7] 提取出的候选文件名")
    lines.append(f"  候选值: {candidate}")

    lines.append("\n[8] 校验结果")
    lines.append(f"  是否通过: {'PASS' if passed else 'FAIL'}")
    if reasons:
        lines.append("  原因:")
        for reason in reasons:
            lines.append(f"    - {reason}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="条码图片 OCR + 文件名提取规则稳健验证脚本")
    parser.add_argument("image", type=Path, help="输入图片路径")
    parser.add_argument(
        "--backend",
        choices=["auto", "paddle", "tesseract"],
        default="auto",
        help="OCR 后端（默认 auto：优先 paddle，失败后 tesseract）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path: Path = args.image

    if not image_path.exists() or not image_path.is_file():
        print(f"[ERROR] 输入图片不存在或不是文件: {image_path}", file=sys.stderr)
        return 2

    try:
        ocr_result = run_ocr(image_path=image_path, backend=args.backend)
    except Exception as exc:
        print(f"[ERROR] OCR 执行失败: {exc}", file=sys.stderr)
        return 3

    merged_lines, line_debug = build_lines_from_tokens(ocr_result.tokens)
    selection = classify_three_lines(merged_lines)
    candidate = extract_candidate_filename(selection.second_line.text if selection.second_line else None)
    passed, reasons = validate_candidate(candidate)

    report = format_report(
        image_path=image_path,
        ocr_result=ocr_result,
        merged_lines=merged_lines,
        selection=selection,
        candidate=candidate,
        passed=passed,
        reasons=reasons,
        line_debug=line_debug,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
