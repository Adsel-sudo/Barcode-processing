"""FastAPI service entry for Feishu webhook processing."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from barcode_tool.api.routes.feishu import build_feishu_router
from barcode_tool.config.settings import load_settings


settings = load_settings()


def create_app() -> FastAPI:
    app = FastAPI(title="Barcode Processing Service", version="0.1.0")
    app.include_router(build_feishu_router(settings))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Backward-compatible health endpoint.
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> int:
    uvicorn.run(
        "barcode_tool.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
    return 0
