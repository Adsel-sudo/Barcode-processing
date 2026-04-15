from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from barcode_tool.api.routes import feishu as feishu_route
from barcode_tool.api.routes.feishu import build_feishu_router
from barcode_tool.config.settings import Settings
from barcode_tool.services.feishu_dedupe_store import FeishuDedupeStore


def _build_settings(tmp_path: Path) -> Settings:
    temp_dir = tmp_path / "tmp"
    settings = Settings(
        app_env="dev",
        output_base_dir=tmp_path / "outputs",
        temp_dir=temp_dir,
        feishu_dedupe_db_path=temp_dir / "feishu_dedupe.sqlite3",
    )
    settings.validate()
    return settings


def _build_payload(message_id: str) -> dict[str, object]:
    return {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_x"}},
            "message": {
                "message_type": "file",
                "file_key": "file_x",
                "chat_id": "oc_x",
                "message_id": message_id,
            },
        },
    }


def test_webhook_duplicate_message_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    app = FastAPI()
    app.include_router(build_feishu_router(settings))
    client = TestClient(app)

    monkeypatch.setattr(
        feishu_route,
        "process_feishu_file_message",
        lambda settings, file_event, task_id: None,
    )

    first = client.post("/feishu/webhook", json=_build_payload("om_same"))
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["accepted"] is True
    assert first_payload["duplicate"] is False
    assert first_payload["status"] == "processing"

    second = client.post("/feishu/webhook", json=_build_payload("om_same"))
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["ok"] is True
    assert second_payload["duplicate"] is True
    assert second_payload["status"] == "processing"
    assert "task_id" not in second_payload


def test_webhook_keeps_failed_message_idempotent(monkeypatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    store = FeishuDedupeStore(settings.feishu_dedupe_db_path)
    _, _ = store.get_or_create_message_record("om_failed")
    store.mark_message_processing("om_failed", "task_1", "file_x", "oc_x")
    store.mark_message_failed("om_failed", "task_1", "boom")

    app = FastAPI()
    app.include_router(build_feishu_router(settings))
    client = TestClient(app)

    monkeypatch.setattr(
        feishu_route,
        "process_feishu_file_message",
        lambda settings, file_event, task_id: None,
    )

    retry_same_message = client.post("/feishu/webhook", json=_build_payload("om_failed"))
    assert retry_same_message.status_code == 200
    payload = retry_same_message.json()
    assert payload["ok"] is True
    assert payload["duplicate"] is True
    assert payload["status"] == "failed"
    assert payload["message_id"] == "om_failed"
