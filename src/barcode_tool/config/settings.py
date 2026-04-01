"""Centralized environment settings for Feishu webhook + Docker deployment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path



def _as_bool(value: str, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    # App runtime
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "dev"

    # Feishu credentials / verification
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_api_base: str = "https://open.feishu.cn/open-apis"

    # Runtime directories
    output_base_dir: Path = Path("./outputs")
    temp_dir: Path = Path("./tmp")

    # Pipeline behavior
    delete_source_on_success: bool = True
    debug_preview_enabled: bool = False

    # Optional runtime
    log_level: str = "INFO"

    @property
    def inbox_dir(self) -> Path:
        return self.temp_dir / "inbox"

    @property
    def archive_dir(self) -> Path:
        return self.temp_dir / "archive"

    def validate(self) -> None:
        if not (1 <= self.app_port <= 65535):
            raise ValueError(f"APP_PORT out of range: {self.app_port}")

        allowed_env = {"dev", "test", "prod"}
        if self.app_env not in allowed_env:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed_env)}, got: {self.app_env}")

        if self.app_env == "prod":
            if not self.feishu_app_id:
                raise ValueError("FEISHU_APP_ID is required in prod")
            if not self.feishu_app_secret:
                raise ValueError("FEISHU_APP_SECRET is required in prod")

        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)



def load_settings() -> Settings:
    settings = Settings(
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        app_env=os.getenv("APP_ENV", "dev").strip().lower(),
        feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        feishu_verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN", ""),
        feishu_encrypt_key=os.getenv("FEISHU_ENCRYPT_KEY", ""),
        feishu_api_base=os.getenv("FEISHU_API_BASE", "https://open.feishu.cn/open-apis"),
        output_base_dir=Path(os.getenv("OUTPUT_BASE_DIR", "./outputs")),
        temp_dir=Path(os.getenv("TEMP_DIR", "./tmp")),
        delete_source_on_success=_as_bool(os.getenv("DELETE_SOURCE_ON_SUCCESS"), default=True),
        debug_preview_enabled=_as_bool(os.getenv("DEBUG_PREVIEW_ENABLED"), default=False),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    settings.validate()
    return settings
