# PDF 条码块裁图导出模块设计方案

> 目标：在既有“PDF 原始文本 + 坐标聚类 + candidate_filename 提取”能力之上，新增稳定的裁图导出与清单输出能力，并确保**文本识别结果与裁图结果同源同对象**。

## 1) 建议新增的数据结构

建议在 `src/barcode_tool/models/types.py` 中补充以下 dataclass（或按你当前命名风格拆分多个 model 文件）。

### 1.1 基础几何与页面引用

- `BBox`
  - 字段：`x0, y0, x1, y1`（统一使用 PDF 坐标系，float）
  - 方法（可选）：`width`, `height`, `expand(margin)`
- `PageRef`
  - 字段：`pdf_path: Path`, `page_index: int`, `page_width_pt: float`, `page_height_pt: float`

### 1.2 识别侧对象（与现有验证逻辑对齐）

- `TextLine`
  - 字段：`text: str`, `bbox: BBox`, `line_index_in_page: int`
- `BarcodeTextTriplet`
  - 字段：
    - `line1_x0: TextLine`
    - `line2_desc_filename: TextLine`
    - `line3_footer: TextLine`
  - 说明：与现有 `pdf_barcode_text_block_validator.py` 的“三行块”概念保持一致。
- `FilenameCandidate`
  - 字段：`raw_text: str`, `normalized: str`, `confidence: float`, `rule_name: str`

### 1.3 新增：导出主对象（核心）

- `BarcodeBlock`
  - 字段：
    - `block_id: str`（建议 `p{page}_b{seq}`，用于全链路追踪）
    - `page: PageRef`
    - `triplet: BarcodeTextTriplet`
    - `candidate_filename: FilenameCandidate`
    - `barcode_bbox: BBox | None`（若可从文本或图形对象估计）
    - `text_bbox: BBox`（三行文本并集）
    - `label_bbox: BBox`（最终裁图框，通常包含条码 + 三行文本）
    - `debug: dict[str, Any]`（阈值、规则命中等调试信息）
  - 关键点：**识别与裁图都围绕同一个 `BarcodeBlock` 进行**。

- `CropSpec`
  - 字段：
    - `target_cm_w: float = 4.99`
    - `target_cm_h: float = 3.27`
    - `dpi: int = 300`
    - `target_px_w: int = 589`
    - `target_px_h: int = 386`
    - `fit_mode: Literal["cover", "contain"] = "contain"`
    - `background: tuple[int, int, int] = (255, 255, 255)`

- `ExportTask`
  - 字段：`block: BarcodeBlock`, `output_dir: Path`, `crop_spec: CropSpec`

- `ExportRecord`
  - 字段：
    - `block_id, page_index, candidate_filename, output_image_path`
    - `label_bbox_json, text_line1, text_line2, text_line3`
    - `status, error_message`

- `PipelineResult`
  - 字段：`records: list[ExportRecord]`, `success_count`, `fail_count`, `manifest_path`

## 2) 建议新增的函数列表

建议“尽量复用现有 validator 的核心逻辑”，把已有脚本中的可复用部分抽到 `services`，validator 改为调用 service（而不是并行维护两套算法）。

### 2.1 识别阶段（复用现有）

- `services/pdf_parser.py`
  - `extract_page_text_lines(pdf_path) -> list[TextLine]`
- `services/block_cluster.py`
  - `cluster_text_lines_to_triplets(lines) -> list[BarcodeTextTriplet]`
- `services/filename_extractor.py`
  - `extract_candidate_filename(line2_text) -> FilenameCandidate`

### 2.2 新增：块对象组装

- `services/block_assembler.py`
  - `build_barcode_blocks(pdf_path, page_lines, triplets, filename_fn, bbox_policy) -> list[BarcodeBlock]`
  - `compute_text_bbox(triplet) -> BBox`
  - `compute_label_bbox(text_bbox, barcode_bbox=None, policy=None) -> BBox`

### 2.3 新增：裁图导出

- `services/crop_exporter.py`
  - `render_page_region(pdf_path, page_index, label_bbox, dpi) -> PIL.Image`
  - `resize_or_pad_to_target(image, target_px_w=589, target_px_h=386, fit_mode="contain") -> PIL.Image`
  - `export_block_to_jpg(task: ExportTask) -> ExportRecord`
  - `export_blocks(tasks: list[ExportTask]) -> list[ExportRecord]`

### 2.4 新增：清单导出

- `services/manifest_writer.py`
  - `write_manifest_csv(records, output_csv_path) -> Path`
  - `write_manifest_excel(records, output_xlsx_path) -> Path`（可选，依赖 pandas/openpyxl）

### 2.5 新增：流水线编排

- `pipeline/pdf_label_pipeline.py`
  - `run_pdf_label_export(pdf_path, output_dir, config) -> PipelineResult`

### 2.6 新增：一致性校验（防错位）

- `services/alignment_guard.py`
  - `assert_block_alignment(block: BarcodeBlock) -> None`
  - `validate_export_record(record: ExportRecord, block: BarcodeBlock) -> None`

> 核心约束：`export_block_to_jpg()` 只接收 `BarcodeBlock`，不接收“独立 bbox + 独立 filename”，从接口层避免错位。

## 3) 模块之间的调用关系

```text
CLI (extract-labels)
  -> pipeline.run_pdf_label_export()
      -> pdf_parser.extract_page_text_lines()
      -> block_cluster.cluster_text_lines_to_triplets()
      -> filename_extractor.extract_candidate_filename()
      -> block_assembler.build_barcode_blocks()
          -> compute_text_bbox()
          -> compute_label_bbox()
      -> alignment_guard.assert_block_alignment()
      -> crop_exporter.export_block_to_jpg() [for each block]
          -> render_page_region()
          -> resize_or_pad_to_target(589x386)
      -> manifest_writer.write_manifest_csv()/write_manifest_excel()
      -> return PipelineResult
```

### 防错位机制（重点）

1. `BarcodeBlock` 作为唯一主键实体（含 `block_id`）。
2. `candidate_filename` 与 `label_bbox` 同挂在同一对象。
3. 导出与写清单都基于同一 `ExportRecord(block_id=...)`。
4. manifest 中落 `block_id + page_index + 三行文本摘要`，便于人工抽检回溯。

## 4) 在现有项目中的推荐文件拆分方式

基于当前仓库骨架，建议按下面增量落地（不推翻现有）：

```text
src/barcode_tool/
  models/
    __init__.py
    types.py                      # 新增/扩展：上文数据结构
  services/
    __init__.py
    pdf_parser.py                 # 从 validator 中提炼
    block_cluster.py              # 从 validator 中提炼
    filename_extractor.py         # 从 validator 中提炼
    block_assembler.py            # 新增
    crop_exporter.py              # 新增（JPG导出 + 固定尺寸）
    manifest_writer.py            # 新增（CSV/Excel）
    alignment_guard.py            # 新增（一致性约束）
  pipeline/
    __init__.py
    pdf_label_pipeline.py         # 新增（总编排）
  cli.py                          # 增加 extract-labels 参数并调用 pipeline

scripts/experiments/pdf_text/
  pdf_text_extract_validator.py   # 保留，内部尽量改为调用 service
  pdf_barcode_text_block_validator.py

tests/
  unit/
    test_filename_extractor.py
    test_block_assembler.py
    test_crop_exporter.py
    test_alignment_guard.py
  integration/
    test_pdf_label_pipeline.py
```

## 5) 分阶段实现建议（先设计后编码）

### Phase A：最小可运行（建议先做）

- 接入 `run_pdf_label_export()` 主流程。
- 每个 block 输出 `candidate_filename.jpg`（先不处理重名策略时，可加 `_p{page}_b{seq}`）。
- 固定输出 589×386 px，300dpi 元数据。
- 生成 CSV 清单。

### Phase B：稳定性增强

- 文件名冲突策略（自动去重、非法字符清洗）。
- Excel 清单输出。
- 增强 label_bbox 估计策略（不同模板参数）。

### Phase C：可观测性

- 生成 debug 预览图（画出 text_bbox / label_bbox / block_id）。
- 抽样回归脚本（对比历史输出一致性）。

## 6) 关键配置建议

建议新增配置对象 `LabelExportConfig`：

- `dpi=300`
- `target_cm=(4.99, 3.27)`
- `target_px=(589, 386)`（显式写死，避免浮点换算偏差）
- `bbox_padding_pt`
- `fit_mode`
- `manifest_format = csv|xlsx|both`
- `filename_conflict_policy = suffix|overwrite|skip`

## 7) 与你当前项目现状的对齐说明

- 保持“PDF 文本 + 坐标聚类”为主线，不引回 OCR 主流程。
- 复用 `pdf_text_extract_validator.py`、`pdf_barcode_text_block_validator.py` 的成熟规则，优先抽函数复用。
- 新增模块重点放在：`BarcodeBlock` 对象化 + `crop_exporter` + `manifest_writer`。
- 通过对象主键 `block_id` 把“识别结果”和“裁图结果”强绑定，规避错位。
