"""Feishu OpenAPI lightweight client for single-service flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass(slots=True)
class FeishuClient:
    app_id: str
    app_secret: str
    api_base: str = "https://open.feishu.cn/open-apis"
    timeout_seconds: int = 30

    def _request(self, method: str, path: str, *, headers: dict[str, str] | None = None, **kwargs) -> httpx.Response:
        url = f"{self.api_base.rstrip('/')}/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response

    def get_tenant_access_token(self) -> str:
        response = self._request(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"get_tenant_access_token failed: {payload}")
        token = payload.get("tenant_access_token", "")
        if not token:
            raise RuntimeError("missing tenant_access_token")
        return token

    def download_file(self, *, message_id: str, file_key: str, target_path: Path) -> Path:
        """Download file from message resource API and save to target path."""
        token = self.get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        # Official path for message resources (file/image/audio/media).
        response = self._request(
            "GET",
            f"/im/v1/messages/{message_id}/resources/{file_key}",
            headers=headers,
            params={"type": "file"},
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(response.content)
        return target_path

    def upload_file(self, *, file_path: Path, file_name: str | None = None) -> str:
        token = self.get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        real_name = file_name or file_path.name
        with file_path.open("rb") as fh:
            files = {"file": (real_name, fh, "application/zip")}
            data = {"file_type": "stream", "file_name": real_name}
            response = self._request("POST", "/im/v1/files", headers=headers, data=data, files=files)
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"upload_file failed: {payload}")
        file_key = payload.get("data", {}).get("file_key", "")
        if not file_key:
            raise RuntimeError("missing uploaded file_key")
        return file_key

    def send_text_message(self, *, receive_id: str, text: str, receive_id_type: str = "chat_id") -> None:
        token = self.get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        body = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": '{"text": "%s"}' % text.replace('"', "'"),
        }
        response = self._request(
            "POST",
            f"/im/v1/messages?receive_id_type={receive_id_type}",
            headers=headers,
            json=body,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"send_text_message failed: {payload}")

    def send_file_message(self, *, receive_id: str, file_key: str, receive_id_type: str = "chat_id") -> None:
        token = self.get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        body = {
            "receive_id": receive_id,
            "msg_type": "file",
            "content": '{"file_key": "%s"}' % file_key,
        }
        response = self._request(
            "POST",
            f"/im/v1/messages?receive_id_type={receive_id_type}",
            headers=headers,
            json=body,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"send_file_message failed: {payload}")
