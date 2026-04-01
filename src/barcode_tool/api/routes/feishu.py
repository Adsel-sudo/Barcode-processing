"""Feishu webhook route.

Synchronous minimal closed-loop:
1) receive event
2) download PDF
3) run existing pipeline
4) package outputs
5) upload result + send summary
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from barcode_tool.config.settings import Settings
from barcode_tool.integrations.feishu_client import FeishuClient
from barcode_tool.pipeline.label_export_pipeline import try_delete_source_pdf
from barcode_tool.services.result_packager import pack_run_output_dir
from barcode_tool.services.task_runner import TaskResult, run_pdf_task


router = APIRouter(prefix="/feishu", tags=["feishu"])


class FeishuWebhookPayload(BaseModel):
    """Loose payload model for Feishu event subscription requests."""

    schema: str | None = None
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



def build_feishu_router(settings: Settings) -> APIRouter:
    client = FeishuClient(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        api_base=settings.feishu_api_base,
    )

    @router.post("/webhook")
    def feishu_webhook(payload: FeishuWebhookPayload) -> dict[str, Any]:
        """Handle Feishu webhook (challenge + file event)."""
        event_type = _extract_event_type(payload)

        # URL verification callback.
        if payload.challenge or event_type == "url_verification":
            _validate_verification_token(payload, settings)
            if not payload.challenge:
                raise HTTPException(status_code=400, detail="missing challenge")
            return {"challenge": payload.challenge}

        # Event callback - currently only minimal file message flow.
        file_event = _parse_file_event(payload)

        task_id = uuid.uuid4().hex[:12]
        source_pdf = settings.inbox_dir / f"{task_id}.pdf"

        try:
            # 1) Download PDF from Feishu to temp dir.
            client.download_file(
                message_id=file_event.message_id,
                file_key=file_event.file_key,
                target_path=source_pdf,
            )

            # 2) Run current pipeline (sync version).
            task_result = run_pdf_task(
                task_id=task_id,
                pdf_path=source_pdf,
                output_base_dir=settings.output_base_dir,
                delete_source_on_success=False,
                debug_preview=settings.debug_preview_enabled,
            )

            # 3) Pack and upload result archive.
            zip_path = pack_run_output_dir(task_result.run_output_dir, settings.archive_dir)
            uploaded_key = client.upload_file(file_path=zip_path)
            client.send_file_message(receive_id=file_event.chat_id, file_key=uploaded_key)

            # 4) Delete source PDF only after full success (export + upload).
            if settings.delete_source_on_success and task_result.all_exports_succeeded:
                deleted, delete_error = try_delete_source_pdf(task_result.source_pdf_path, enabled=True)
                task_result.source_pdf_deleted = deleted
                task_result.source_pdf_delete_error = delete_error

            # 5) Send summary message.
            summary = _build_summary(task_id, task_result)
            client.send_text_message(receive_id=file_event.chat_id, text=summary)

            return {
                "ok": True,
                "task_id": task_id,
                "chat_id": file_event.chat_id,
                "user_id": file_event.user_id,
                "run_output_dir": str(task_result.run_output_dir),
                "report_path": str(task_result.report_path),
            }
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"task failed: {exc}") from exc

    return router
