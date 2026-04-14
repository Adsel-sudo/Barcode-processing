from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from barcode_tool.api.routes.feishu import build_feishu_router
from barcode_tool.config.settings import Settings
from barcode_tool.services.feishu_dedupe_store import FeishuDedupeStore


def _build_settings(tmp_path: Path, *, app_env: str) -> Settings:
    temp_dir = tmp_path / "tmp"
    settings = Settings(
        app_env=app_env,
        output_base_dir=tmp_path / "outputs",
        temp_dir=temp_dir,
        feishu_dedupe_db_path=temp_dir / "feishu_dedupe.sqlite3",
        feishu_app_id="dummy_app_id" if app_env == "prod" else "",
        feishu_app_secret="dummy_app_secret" if app_env == "prod" else "",
    )
    settings.validate()
    return settings


def test_debug_messages_endpoints_return_records(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, app_env="dev")
    store = FeishuDedupeStore(settings.feishu_dedupe_db_path)

    _, _ = store.get_or_create_message_record("om_1")
    store.mark_message_processing("om_1", "t1", "fk_1", "chat_1")
    store.mark_message_done("om_1", "t1", "/tmp/a.zip")

    _, _ = store.get_or_create_message_record("om_2")
    store.mark_message_processing("om_2", "t2", "fk_2", "chat_2")
    store.mark_message_failed("om_2", "t2", "boom")

    app = FastAPI()
    app.include_router(build_feishu_router(settings))
    client = TestClient(app)

    list_resp = client.get("/feishu/debug/messages", params={"limit": 2})
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["ok"] is True
    assert payload["count"] == 2
    first = payload["messages"][0]
    assert set(first.keys()) == {
        "message_id",
        "task_id",
        "file_key",
        "chat_id",
        "status",
        "created_at",
        "updated_at",
        "result_path",
        "error_message",
    }

    one_resp = client.get("/feishu/debug/messages/om_1")
    assert one_resp.status_code == 200
    one_payload = one_resp.json()
    assert one_payload["message"]["message_id"] == "om_1"
    assert one_payload["message"]["status"] == "done"


def test_debug_messages_endpoints_hidden_in_prod(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, app_env="prod")
    app = FastAPI()
    app.include_router(build_feishu_router(settings))
    client = TestClient(app)

    assert client.get("/feishu/debug/messages").status_code == 404
    assert client.get("/feishu/debug/messages/om_1").status_code == 404
