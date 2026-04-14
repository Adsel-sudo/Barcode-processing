"""Feishu webhook route.

Synchronous minimal closed-loop:
1) receive event
2) download PDF
3) run existing pipeline
4) package outputs
5) upload result + send summary
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from barcode_tool.config.settings import Settings
from barcode_tool.integrations.feishu_client import FeishuClient
from barcode_tool.pipeline.label_export_pipeline import try_delete_source_pdf
from barcode_tool.services.feishu_dedupe_store import FeishuDedupeStore, MessageRecord
from barcode_tool.services.result_packager import pack_run_output_dir
from barcode_tool.services.task_runner import TaskResult, run_pdf_task


logger = logging.getLogger(__name__)


class FeishuWebhookPayload(BaseModel):
    """Loose payload model for Feishu event subscription requests."""

    header: dict[str, Any] | None = None
    event: dict[str, Any] | None = None
    challenge: str | None = None
    token: str | None = None
    type: str | None = None


@dataclass(slots=True)
class ParsedFeishuFileEvent:
    message_id: str
    file_key: str
    chat_id: str
    user_id: str
    receive_id_type: str = "chat_id"


def _record_to_dict(record: MessageRecord) -> dict[str, Any]:
    return {
        "message_id": record.message_id,
        "task_id": record.task_id,
        "file_key": record.file_key,
        "chat_id": record.chat_id,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "result_path": record.result_path,
        "error_message": record.error_message,
    }


def _parse_content_json(raw_content: Any) -> dict[str, Any]:
    if isinstance(raw_content, dict):
        return raw_content
    if isinstance(raw_content, str) and raw_content.strip():
        try:
            payload = json.loads(raw_content)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_event_type(payload: FeishuWebhookPayload) -> str:
    header = payload.header or {}
    return str(header.get("event_type") or payload.type or "")


def _parse_file_event(payload: FeishuWebhookPayload) -> ParsedFeishuFileEvent:
    event = payload.event or {}
    sender = event.get("sender", {})
    message = event.get("message", {})
    content = _parse_content_json(message.get("content"))

    message_type = message.get("message_type") or content.get("message_type")
    if message_type and message_type != "file":
        raise HTTPException(status_code=400, detail=f"unsupported message_type: {message_type}")

    file_key = message.get("file_key") or content.get("file_key") or ""
    chat_id = message.get("chat_id") or event.get("chat_id") or ""
    message_id = message.get("message_id") or event.get("message_id") or ""
    user_id = sender.get("sender_id", {}).get("open_id") or sender.get("id") or ""

    if not file_key:
        raise HTTPException(status_code=400, detail="missing file_key")
    if not chat_id:
        raise HTTPException(status_code=400, detail="missing chat_id")
    if not message_id:
        raise HTTPException(status_code=400, detail="missing message_id")

    return ParsedFeishuFileEvent(
        message_id=message_id,
        file_key=file_key,
        chat_id=chat_id,
        user_id=user_id,
    )


def _validate_verification_token(payload: FeishuWebhookPayload, settings: Settings) -> None:
    if settings.feishu_verification_token and payload.token != settings.feishu_verification_token:
        raise HTTPException(status_code=403, detail="invalid verification token")


def _build_summary(task_id: str, result: TaskResult) -> str:
    deleted_text = "是" if result.source_pdf_deleted else "否"
    report_text = "是" if result.report_generated else "否"
    warning_text = (
        f"\n删除警告: {result.source_pdf_delete_error}" if result.source_pdf_delete_error else ""
    )
    return (
        f"任务完成 task_id={task_id}\n"
        f"成功数量: {result.exported_count}\n"
        f"失败数量: {result.failed_count}\n"
        f"report已生成: {report_text}\n"
        "结果文件已上传\n"
        f"原始PDF已删除: {deleted_text}"
        f"{warning_text}"
    )


def _build_task_id(message_id: str) -> str:
    message_hash = hashlib.sha1(message_id.encode("utf-8")).hexdigest()[:4]
    random_part = uuid.uuid4().hex[:8]
    return f"{message_hash}{random_part}"


def process_feishu_file_message(settings: Settings, file_event: ParsedFeishuFileEvent, task_id: str) -> None:
    """Background job for heavy file processing and Feishu reply."""
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        api_base=settings.feishu_api_base,
    )
    dedupe_store = FeishuDedupeStore(settings.feishu_dedupe_db_path)
    source_pdf = settings.inbox_dir / f"{task_id}.pdf"

    try:
        client.download_file(
            message_id=file_event.message_id,
            file_key=file_event.file_key,
            target_path=source_pdf,
        )

        task_result = run_pdf_task(
            task_id=task_id,
            pdf_path=source_pdf,
            output_base_dir=settings.output_base_dir,
            delete_source_on_success=False,
            debug_preview=settings.debug_preview_enabled,
        )

        zip_path = pack_run_output_dir(task_result.run_output_dir, settings.archive_dir)
        uploaded_key = client.upload_file(file_path=zip_path)
        client.send_file_message(receive_id=file_event.chat_id, file_key=uploaded_key)

        if settings.delete_source_on_success and task_result.all_exports_succeeded:
            deleted, delete_error = try_delete_source_pdf(task_result.source_pdf_path, enabled=True)
            task_result.source_pdf_deleted = deleted
            task_result.source_pdf_delete_error = delete_error

        summary = _build_summary(task_id, task_result)
        client.send_text_message(receive_id=file_event.chat_id, text=summary)

        dedupe_store.mark_message_done(
            message_id=file_event.message_id,
            task_id=task_id,
            result_path=str(zip_path),
        )
        logger.info(
            "feishu_webhook background task finished message_id=%s file_key=%s chat_id=%s task_id=%s duplicate=%s final_status=%s",
            file_event.message_id,
            file_event.file_key,
            file_event.chat_id,
            task_id,
            False,
            "done",
        )
    except Exception as exc:  # noqa: BLE001
        dedupe_store.mark_message_failed(
            message_id=file_event.message_id,
            task_id=task_id,
            error_message=str(exc),
        )
        logger.exception(
            "feishu_webhook background task failed message_id=%s file_key=%s chat_id=%s task_id=%s duplicate=%s final_status=%s",
            file_event.message_id,
            file_event.file_key,
            file_event.chat_id,
            task_id,
            False,
            "failed",
        )
        try:
            client.send_text_message(
                receive_id=file_event.chat_id,
                text=f"任务失败 task_id={task_id}\nmessage_id={file_event.message_id}\n错误: {exc}",
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "feishu_webhook failed to send failure notice message_id=%s chat_id=%s task_id=%s",
                file_event.message_id,
                file_event.chat_id,
                task_id,
            )


def build_feishu_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/feishu", tags=["feishu"])
    dedupe_store = FeishuDedupeStore(settings.feishu_dedupe_db_path)

    @router.post("/webhook")
    def feishu_webhook(payload: FeishuWebhookPayload, background_tasks: BackgroundTasks) -> dict[str, Any]:
        """Handle Feishu webhook (challenge + file event)."""
        event_type = _extract_event_type(payload)

        # URL verification callback.
        if payload.challenge or event_type == "url_verification":
            _validate_verification_token(payload, settings)
            if not payload.challenge:
                raise HTTPException(status_code=400, detail="missing challenge")
            return {"challenge": payload.challenge}

        file_event = _parse_file_event(payload)
        dedupe_record, created = dedupe_store.get_or_create_message_record(file_event.message_id)

        if not created and dedupe_record.status in {"processing", "done"}:
            logger.info(
                "feishu_webhook duplicate event ignored message_id=%s file_key=%s chat_id=%s task_id=%s duplicate=%s final_status=%s",
                file_event.message_id,
                file_event.file_key,
                file_event.chat_id,
                dedupe_record.task_id or "",
                True,
                dedupe_record.status,
            )
            return {
                "ok": True,
                "duplicate": True,
                "status": dedupe_record.status,
                "message_id": file_event.message_id,
            }

        task_id = _build_task_id(file_event.message_id)
        dedupe_store.mark_message_processing(
            message_id=file_event.message_id,
            task_id=task_id,
            file_key=file_event.file_key,
            chat_id=file_event.chat_id,
        )

        background_tasks.add_task(process_feishu_file_message, settings, file_event, task_id)
        logger.info(
            "feishu_webhook accepted event message_id=%s file_key=%s chat_id=%s task_id=%s duplicate=%s final_status=%s",
            file_event.message_id,
            file_event.file_key,
            file_event.chat_id,
            task_id,
            False,
            "processing",
        )
        return {
            "ok": True,
            "accepted": True,
            "duplicate": False,
            "status": "processing",
            "message_id": file_event.message_id,
            "task_id": task_id,
        }

    @router.get("/debug/messages")
    def list_debug_messages(limit: int = 50) -> dict[str, Any]:
        if settings.app_env == "prod":
            raise HTTPException(status_code=404, detail="not found")
        records = dedupe_store.list_recent_message_records(limit=limit)
        return {
            "ok": True,
            "count": len(records),
            "messages": [_record_to_dict(record) for record in records],
        }

    @router.get("/debug/messages/{message_id}")
    def get_debug_message(message_id: str) -> dict[str, Any]:
        if settings.app_env == "prod":
            raise HTTPException(status_code=404, detail="not found")
        record = dedupe_store.get_message_record(message_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"message_id not found: {message_id}")
        return {"ok": True, "message": _record_to_dict(record)}

    return router
