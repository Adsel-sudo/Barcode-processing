# Barcode Processing

用于处理 PDF 条码标签的内部工具项目（内部使用）。

## 当前主路线

> 已确定采用：**PDF 原始文本 + 坐标聚类**。

- 每个条码块识别三行文本：
  - 第一行通常 `X0...`
  - 第二行是商品描述 + 候选文件名
  - 第三行通常 `New / 新品 / Made in China`
- OCR 不再是主路线，但历史 OCR 脚本保留在 `scripts/legacy/ocr/`。

## 推荐目录（轻量可扩展）

```text
project/
  README.md
  pyproject.toml
  docs/
    repo_structure.md
  src/
    barcode_tool/
      cli.py
      models/
      services/
      pipeline/
      utils/
  scripts/
    experiments/
      pdf_text/
    legacy/
      ocr/
  tests/
    unit/
    integration/
  samples/
    pdf/
    expected/
```

## 当前仓库落地情况

- 已完成：`src/barcode_tool` 分层骨架与 CLI 入口。
- 已完成：脚本分层为 `scripts/experiments`（当前路线实验）和 `scripts/legacy`（历史方案）。
- 尚未实现：完整裁图导出、清单导出、飞书机器人。

## 后续功能分阶段

1. PDF 文本提取（含坐标）
2. 条码块三行识别
3. candidate_filename 提取
4. text_bbox / label_bbox 计算
5. 局部裁图与固定尺寸 JPG 导出
6. 调试预览图输出
7. 结果清单导出（CSV/JSON）
8. 飞书机器人（后续阶段）


## 最小依赖安装

```bash
pip install -r requirements.txt
```

说明：默认不包含 OCR 依赖；当前主路线只需要 PDF 文本坐标提取与图像导出相关依赖。

## 快速开始

```bash
PYTHONPATH=src python -m barcode_tool.cli --help
```

详细分层规范见 `docs/repo_structure.md`。
