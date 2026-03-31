# 依赖说明（最小可用版）

## requirements.txt（第一版）

- `pymupdf>=1.24,<2.0`
  - **用途**：读取 PDF 原始文本、line/span/bbox 坐标，是当前主路线核心依赖。
  - **状态**：当前必须。

- `Pillow>=10.0,<12.0`
  - **用途**：后续局部裁图、JPG 导出、调试预览图绘制。
  - **状态**：当前建议安装（即使导出层尚未完全实现，也会很快使用）。

## 可选/后续阶段依赖（默认不装）

- `pandas>=2.2,<3.0` + `openpyxl>=3.1,<4.0`
  - **用途**：导出 Excel 清单（`.xlsx`）；
  - **状态**：可选，只有需要 Excel 时再安装。
  - 备注：CSV/JSON 清单可使用标准库，不依赖它们。

## 明确不作为默认必需依赖

- OCR 相关库（如 easyocr / paddleocr / pytesseract）
  - 原因：当前主路线不是 OCR。

## 与 pyproject.toml 的关系

- 当前仓库已有 `pyproject.toml` 可用于包安装和 CLI 入口。
- 为“快速落地”与团队上手，保留 `requirements.txt` 作为最小运行依赖清单即可。
