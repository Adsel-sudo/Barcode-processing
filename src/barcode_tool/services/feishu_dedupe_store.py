"""Lightweight SQLite-backed dedupe store for Feishu message events."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class MessageRecord:
    message_id: str
    status: str
    task_id: str | None = None
    file_key: str | None = None
    chat_id: str | None = None
    result_path: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeishuDedupeStore:
    """SQLite store for idempotency of Feishu message callbacks."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feishu_message_dedupe (
                    message_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    task_id TEXT,
                    file_key TEXT,
                    chat_id TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_record(self, row: sqlite3.Row | None) -> MessageRecord | None:
        if row is None:
            return None
        return MessageRecord(
            message_id=row["message_id"],
            status=row["status"],
            task_id=row["task_id"],
            file_key=row["file_key"],
            chat_id=row["chat_id"],
            result_path=row["result_path"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_message_record(self, message_id: str) -> MessageRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM feishu_message_dedupe WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return self._row_to_record(row)

    def list_recent_message_records(self, limit: int = 50) -> list[MessageRecord]:
        safe_limit = max(1, min(limit, 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM feishu_message_dedupe
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]

    def get_or_create_message_record(self, message_id: str) -> tuple[MessageRecord, bool]:
        """Create a processing record atomically when message_id is first seen."""
        now = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO feishu_message_dedupe (
                    message_id, status, created_at, updated_at
                ) VALUES (?, 'processing', ?, ?)
                """,
                (message_id, now, now),
            )
            created = cursor.rowcount == 1
            row = conn.execute(
                "SELECT * FROM feishu_message_dedupe WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        record = self._row_to_record(row)
        if record is None:
            raise RuntimeError(f"failed to get/create dedupe record for message_id={message_id}")
        return record, created

    def mark_message_processing(self, message_id: str, task_id: str, file_key: str, chat_id: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE feishu_message_dedupe
                SET status = 'processing',
                    task_id = ?,
                    file_key = ?,
                    chat_id = ?,
                    result_path = NULL,
                    error_message = NULL,
                    updated_at = ?
                WHERE message_id = ?
                """,
                (task_id, file_key, chat_id, now, message_id),
            )

    def mark_message_done(self, message_id: str, task_id: str, result_path: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE feishu_message_dedupe
                SET status = 'done',
                    task_id = ?,
                    result_path = ?,
                    updated_at = ?
                WHERE message_id = ?
                """,
                (task_id, result_path, now, message_id),
            )

    def mark_message_failed(self, message_id: str, task_id: str, error_message: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE feishu_message_dedupe
                SET status = 'failed',
                    task_id = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE message_id = ?
                """,
                (task_id, error_message[:1000], now, message_id),
            )

    def is_duplicate_message(self, message_id: str) -> bool:
        record = self.get_message_record(message_id)
        return record is not None and record.status in {"processing", "done"}
