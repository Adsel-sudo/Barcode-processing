# 推荐仓库结构（中小型内部工具版）

```text
project/
  README.md
  pyproject.toml              # 或 requirements.txt（二选一即可）
  docs/
    repo_structure.md         # 仓库结构与分层约定
  src/
    barcode_tool/
      cli.py                  # 统一命令入口（薄层）
      models/                 # 数据模型（line/block/result/bbox）
      services/               # 纯能力模块：提取、识别、裁图、导出
      pipeline/               # 任务编排：串联各 services
      utils/                  # 通用工具（日志、路径、文本清洗）
  scripts/
    README.md
    experiments/
      pdf_text/               # 当前主路线实验脚本
    legacy/
      ocr/                    # 旧 OCR 路线脚本归档
  tests/
    unit/
    integration/
  samples/
    pdf/                      # 脱敏样例 PDF
    expected/                 # 对照结果（JSON/CSV）
```

## 放置原则

### 应放在 `src/` 的内容（核心模块）

- 可复用且会长期维护的业务能力：
  - `pdf_text_extractor`（PDF 文本与坐标提取）
  - `label_block_detector`（条码块三行识别）
  - `filename_parser`（候选文件名提取）
  - `bbox_calculator`（text_bbox / label_bbox 计算）
  - `crop_exporter`（局部裁图与固定尺寸 JPG 导出）
  - `manifest_writer`（结果清单导出 CSV/JSON）
  - `preview_renderer`（调试预览图生成）

### 应放在 `scripts/` 的内容（验证/调试）

- 一次性、手工触发、用于验证假设的脚本：
  - 阈值实验、参数对比、抽样检查
  - 批量回归对比（非正式 pipeline）
  - 调试可视化脚本

## OCR 旧脚本归档建议

- 移入 `scripts/legacy/ocr/`：
  - `ocr_filename_validator.py`
  - `batch_ocr_sample_validator.py`
- 理由：OCR 已非主路线，但可留作边界场景兜底参考。

## 与后续“裁图导出模块”对齐

建议把“裁图导出”设计为独立 service：

1. 输入：`label_bbox`, `text_bbox`, page info, export config；
2. 输出：固定尺寸 JPG + 裁切元数据；
3. 与识别逻辑解耦，便于单独测试与替换；
4. 在 pipeline 里只负责编排，不把图像细节写入 CLI 层。
