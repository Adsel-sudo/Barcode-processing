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
- 已完成：标签裁图导出、清单导出、调试预览图能力。
- 已完成：导出图底部 `Made in China` 独立精修（字重调轻为“略重于正文”、主内容轻微上移、与第三行间距收紧、底边安全留白增加；不影响条码与前三行字号及业务流程）。
- 已完成：飞书 webhook 接入（去重、异步处理、回传压缩包与摘要消息）。
- 已完成：开发排查接口（最近 message_id 状态查询）。

## 后续功能分阶段

1. PDF 文本提取（含坐标）
2. 条码块三行识别
3. candidate_filename 提取
4. text_bbox / label_bbox 计算
5. 局部裁图与固定尺寸 JPG 导出
6. 调试预览图输出
7. 结果清单导出（CSV/JSON）
8. 飞书机器人（已落地基础能力，持续迭代）


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

## 开发自检（建议提交前执行）

```bash
PYTHONPATH=src pytest -q
python -m compileall -q src
```

说明：项目采用 `src/` 布局，本地直接执行测试时请显式设置 `PYTHONPATH=src`。


## Webhook 服务（飞书接入）

```bash
PYTHONPATH=src barcode-tool-server
# 或
PYTHONPATH=src uvicorn barcode_tool.api.app:app --host 0.0.0.0 --port 8000
```

健康检查：`GET /healthz`

飞书回调：`POST /feishu/webhook`

调试接口（仅 `APP_ENV != prod` 可用）：

- `GET /feishu/debug/messages?limit=50`
- `GET /feishu/debug/messages/{message_id}`

调试字段：

- `message_id`
- `task_id`
- `file_key`
- `chat_id`
- `status`（`processing` / `done` / `failed`）
- `created_at`
- `updated_at`
- `result_path`
- `error_message`

推荐先复制环境变量模板：

```bash
cp .env.example .env
```

`.env` 已在 `.gitignore` 中，默认不会被提交到仓库。

关键变量：`APP_HOST` `APP_PORT` `APP_ENV` `FEISHU_APP_ID` `FEISHU_APP_SECRET` `OUTPUT_BASE_DIR` `TEMP_DIR` `FEISHU_DEDUPE_DB_PATH`。

### 飞书 webhook 处理流程（当前实现）

1. 接收事件并解析 `message_id / file_key / chat_id`；
2. 先做 `message_id` 幂等去重（SQLite）；
3. 命中重复（`processing/done`）立即返回；
4. 新事件登记 `processing`，立即返回 `200`；
5. 后台任务继续执行：下载 PDF → 跑 pipeline → 打包 zip → 上传飞书 → 发送摘要；
6. 最终更新状态为 `done` 或 `failed`。

这样可降低 webhook 同步耗时，减少飞书重试带来的重复投递。



## Docker 最小部署（单服务）

### 本地构建

```bash
docker build -t barcode-processing:latest .
```

### 本地启动

```bash
cp .env.example .env
docker run --rm -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data/outputs:/data/outputs \
  -v $(pwd)/data/tmp:/data/tmp \
  barcode-processing:latest
```

### 使用 docker compose 启动（推荐）

```bash
cp .env.example .env
docker compose up -d --build
```

### 服务器启动

```bash
docker compose up -d
```

### 查看日志

```bash
docker compose logs -f barcode-service
```
