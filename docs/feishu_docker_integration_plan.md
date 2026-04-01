# 飞书机器人 + PDF 条码处理（单服务 Docker）设计方案

> 目标：基于**当前已完成的 Python 项目能力**，新增飞书机器人接入能力，并以**单服务容器**部署到服务器；不拆 worker/queue/redis，不重写核心处理逻辑。

---

## 0. 当前能力基线（已存在，可复用）

当前仓库已经具备以下端到端核心能力：

- PDF 文本解析 + 聚类识别 + 三行文本提取。
- `candidate_filename` 提取。
- 基于 `label_bbox` 裁图并导出固定尺寸 JPG。
- manifest/report 导出（CSV/Excel）与 debug preview。
- pipeline 已支持：
  - 在用户指定输出目录下自动创建本次任务目录；
  - 全部导出成功后可删除原始 PDF。

因此本次接入重点是“新增飞书入口与上传回传适配层”，而不是改造识别与导出核心。

---

## 1) 整体架构设计（单进程单容器）

### 架构原则

- **单服务**：一个 Python 进程同时提供 HTTP webhook 与本地 pipeline 调用能力。
- **双入口同内核**：Webhook 入口与 CLI 入口都调用同一 pipeline。
- **适配层隔离**：飞书协议/鉴权/上传下载全部放在 `integrations` 层。

### 逻辑架构图

```text
Feishu Group Bot
   -> Webhook Event
      -> app/webhook endpoint
         -> integrations.feishu_webhook (事件解析/验签)
         -> integrations.feishu_file_client (下载 PDF 到本地临时目录)
         -> pipeline.job_runner (调用现有 run_label_export_pipeline)
         -> integrations.result_packager (打包 images/report/debug)
         -> integrations.feishu_sender (回传 zip + 摘要消息)

Local CLI
   -> cli command
      -> pipeline.job_runner
```

### 运行时目录建议（容器内）

- `/data/inbox`：待处理 PDF（下载落地）。
- `/data/runs`：每次任务产物目录（沿用现有 run 目录逻辑）。
- `/data/outbox`：可选，临时 zip。
- `/data/logs`：应用日志（stdout + 可选文件）。

---

## 2) 单服务职责边界

### 服务应负责

1. 接收飞书 webhook（HTTP）。
2. 校验并解析事件（最小必要字段）。
3. 下载 PDF 到本地工作目录。
4. 调用既有 pipeline 执行处理。
5. 打包结果并上传回飞书。
6. 输出统一任务日志与状态。

### 服务不负责

- 异步队列编排（Celery / Redis / MQ）。
- 多实例分布式锁。
- 复杂任务调度中心。

> 说明：先用单进程串行/轻并发模型即可，符合“轻量、低风险、直接演进”的目标。

---

## 3) 飞书机器人与本地处理逻辑调用关系

### 推荐调用链（Webhook）

1. `POST /webhook/feishu`
2. 解析事件（拿到 `chat_id`、`file_token`、`event_id`）
3. `download_pdf(file_token) -> local_pdf_path`
4. `run_job(local_pdf_path, base_output_dir)`
   - 内部调用现有 `run_label_export_pipeline(...)`
5. `pack_run_outputs(run_output_dir) -> zip_path`
6. 上传 zip 到飞书 + 发送执行摘要
7. 返回 200（或错误码 + 简述）

### 推荐调用链（CLI）

- CLI 继续直接调用 `run_job(...)`（或直接调 `run_label_export_pipeline`），保持离线可用。

### 关键约束

- `services/*` 与 `pipeline/*` 不依赖飞书 SDK。
- 飞书字段只存在于 `app` / `integrations` / `job models`。

---

## 4) 需要新增哪些模块（轻量最小集）

> 先做最小闭环可用，再补安全与鲁棒性细节。

### A. 接入层

- `src/barcode_tool/app.py`
  - 启动 HTTP 服务。
  - 提供 `/healthz` 与 `/webhook/feishu`。

- `src/barcode_tool/integrations/feishu_webhook.py`
  - 事件解析（message/file 事件）。
  - 可选：签名校验、event_id 幂等键生成。

### B. 飞书文件与消息能力

- `src/barcode_tool/integrations/feishu_file_client.py`
  - 通过 `file_token` 下载 PDF。
  - 基础超时与重试（最小实现即可）。

- `src/barcode_tool/integrations/feishu_sender.py`
  - 上传文件（zip）。
  - 发送文本摘要（成功数/失败数/耗时/run_id）。

### C. 编排与结果包装

- `src/barcode_tool/pipeline/job_runner.py`
  - 把“下载文件路径 -> pipeline -> 结果摘要”封装成稳定入口。
  - 统一返回 `JobResultSummary`。

- `src/barcode_tool/integrations/result_packager.py`
  - 将 `images/`、`report/`、`debug/`（若有）打包为 zip。

### D. 运行支撑

- `src/barcode_tool/services/storage.py`
  - 工作目录初始化、路径规范、清理策略。

- `src/barcode_tool/models/job_types.py`
  - `JobRequest`、`JobResultSummary`、`FeishuReplyPayload` 等轻量 dataclass。

---

## 5) 哪些现有模块可以直接复用

以下模块建议“直接复用，不做侵入式改造”：

1. `pipeline/label_export_pipeline.py`
   - 已包含：run 目录创建、检测->导出->report->debug preview、成功后删除原 PDF 等主路径能力。

2. `services/label_analyzer.py` + `services/label_enricher.py`
   - 已覆盖识别与导出前数据增强。

3. `services/crop_exporter.py`
   - 已实现固定尺寸导图与错误隔离。

4. `services/manifest_writer.py`
   - 已实现 CSV/Excel 报告导出。

5. `services/debug_preview.py`
   - 已可输出可视化调试预览图。

> 结论：飞书接入只需“新增入口与适配器”，核心处理链无需推翻。

---

## 6) 推荐目录结构调整方案（最小改动版）

```text
src/barcode_tool/
  app.py                          # 新增：HTTP 入口（healthz + webhook）
  cli.py                          # 保留：本地命令入口

  integrations/                   # 新增：外部系统适配层
    __init__.py
    feishu_webhook.py
    feishu_file_client.py
    feishu_sender.py
    result_packager.py

  pipeline/
    label_export_pipeline.py      # 复用
    job_runner.py                 # 新增：统一任务入口

  services/
    storage.py                    # 新增：目录与文件生命周期管理
    ...                           # 其余现有 services 复用

  models/
    types.py                      # 复用核心领域模型
    job_types.py                  # 新增：任务与回传模型

Dockerfile                        # 新增
.dockerignore                     # 新增
```

### 为什么这么调

- `integrations` 集中外部协议，避免污染 `services`。
- `job_runner` 把“Web/CLI 双入口”收敛到一个编排函数。
- 目录调整幅度小，不影响现有测试与调用路径。

---

## 7) 交付顺序（先设计后编码）

### Step 1：接入口骨架

- 先让 `/healthz` 和 `/webhook/feishu` 跑起来。
- webhook 暂时返回“收到任务 + task_id”。

### Step 2：下载 + pipeline 串通

- 打通 `file_token -> local pdf -> run_label_export_pipeline`。
- 先不做复杂验签与幂等。

### Step 3：打包 + 回传

- 产物 zip 上传飞书。
- 发送简版执行摘要。

### Step 4：安全与稳定性加固（第二阶段）

- 签名校验。
- event_id 幂等。
- 重试与超时细化。
- 清理策略与监控告警。

---

## 8) 轻量化设计细节建议（避免过度工程化）

1. **不要提前拆微服务**：单进程足够。
2. **不要提前引入队列系统**：先同步处理或少量线程池。
3. **不要重建配置中心**：先环境变量 + `.env`。
4. **不要抽象过度**：只抽 `job_runner` 与 `integrations` 即可。
5. **日志先可读再完美**：`task_id`/`event_id` 全链路打印。

---

## 9) 单服务部署建议（Docker）

### Docker 运行方式

- 基础镜像：`python:3.11-slim`。
- 安装依赖 + 拷贝代码。
- 默认启动 web 服务（例如 `uvicorn barcode_tool.app:app`）。
- 通过 volume 挂载 `/data`，确保处理结果持久化。

### 必要环境变量（示例）

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BOT_WEBHOOK`（若需要主动发消息）
- `WORK_ROOT=/data`
- `OUTPUT_ROOT=/data/runs`
- `LOG_LEVEL=INFO`

---

## 10) 服务器验收闭环（上线前最小检查）

1. `GET /healthz` = 200。
2. 模拟 webhook 请求可拿到 task_id。
3. 能下载测试 PDF 到 `/data/inbox`。
4. 能在 `/data/runs/<task>` 看到：
   - `images/*.jpg`
   - `report/report.csv`（或 xlsx）
   - `debug/*.jpg`（开启时）
5. 能收到飞书回传 zip + 摘要消息。
6. 在“导出全成功”场景下，源 PDF 被按配置删除。

---

## 结论

该方案本质是：在现有 pipeline 之上新增一个**飞书适配入口层**与**结果回传层**，保持核心识别/导图/报告逻辑不动，以单服务 Docker 快速上线。实现路径清晰、改动面可控、风险低，适合当前项目直接演进。
