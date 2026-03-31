# 主路线模块边界与依赖方向

## 逻辑层与模块映射

1. PDF 文本解析层
   - `src/barcode_tool/services/pdf_parser.py`
2. 条码块聚类层
   - `src/barcode_tool/services/block_cluster.py`
3. 文件名提取层
   - `src/barcode_tool/services/filename_extractor.py`
4. 通用工具层
   - `src/barcode_tool/utils/bbox.py`
   - `src/barcode_tool/utils/text.py`
   - `src/barcode_tool/utils/filename.py`
5. 后续导出层（预留）
   - `src/barcode_tool/services/exporter.py`

## 数据模型

- `src/barcode_tool/models/types.py`
  - `TextLine`
  - `BarcodeTextTriplet`
  - `BarcodeBlock`
  - `FilenameCandidate`
  - `ExportTask`
  - `PipelineRecord`
  - `PipelineResult`

## 依赖方向（单向）

- `utils` -> 无业务依赖
- `models` -> 仅依赖 Python 标准库
- `services` -> 依赖 `models` + `utils`
- `pipeline` -> 依赖 `services` + `models`
- `cli` -> 依赖 `pipeline`

> 禁止反向依赖：`services` 不依赖 `pipeline`，`models` 不依赖 `services`。
