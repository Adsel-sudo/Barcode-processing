# 重构方案（结构优先版）

本次重构目标：把“零散验证脚本”演进为“可持续开发的 Python 内部工具项目”，仅做工程结构整理，不一次性实现完整业务功能。

## 分层原则

- `scripts/legacy`：历史验证脚本与实验入口。
- `src/barcode_tool`：正式开发代码。
- `tests`：正式代码测试。
- `docs`：方案、约定、流程文档。

## 模块职责（正式代码）

- `pipeline/`：组织端到端步骤，不承载底层细节。
- `services/`：承载 PDF 解析、条码块识别、裁图导出等能力。
- `models/`：统一输入输出数据结构，避免跨模块字典乱传。
- `utils/`：日志、路径、文本清洗等通用工具。
- `cli.py`：单一入口，命令解析与调度。

## 旧脚本处理原则

- 保留：作为经验资产与回归参考。
- 移动：从仓库根目录迁移到 `scripts/legacy`。
- 标记：在 README 明确“legacy，仅参考，不再扩展”。

## 下一步建议（不在本次提交实现）

1. 在 `models` 中定义 `TextLine`, `LabelBlock`, `ExtractionResult`。
2. 在 `services` 中落地：
   - PDF 文本抓取服务；
   - 三行识别服务；
   - bbox 计算与裁图服务。
3. 在 `pipeline` 中增加 `run_pdf_pipeline()`，并由 CLI 调用。
4. 增加最小单元测试与样例数据夹具。
