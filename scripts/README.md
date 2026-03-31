# scripts 目录说明

- `scripts/experiments/`：当前路线（PDF 原始文本 + 坐标聚类）下的验证脚本与调试入口。
- `scripts/legacy/`：历史方案脚本（主要是 OCR 路线），仅保留用于回溯，不作为主流程继续开发。

> 原则：可复用、可沉淀的业务能力进入 `src/`；一次性验证与手工调试命令放在 `scripts/`。
