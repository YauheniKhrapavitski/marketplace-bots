from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ttn_bot.models import TtnEditData


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_templates (
                    user_id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    source_pdf_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    error TEXT
                )
                """
            )

    def save_user_template(self, user_id: int, data: TtnEditData) -> None:
        payload = data.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_templates (user_id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, payload),
            )

    def get_user_template(self, user_id: int) -> TtnEditData | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM user_templates WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return TtnEditData.model_validate(json.loads(row["payload"]))

    def delete_user_template(self, user_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM user_templates WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0

    def create_job(self, job_id: str, user_id: int, source_pdf_path: Path) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, user_id, source_pdf_path, status)
                VALUES (?, ?, ?, 'uploaded')
                """,
                (job_id, user_id, str(source_pdf_path)),
            )

    def update_job(self, job_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                """,
                (status, error, job_id),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def template_to_user_text(data: TtnEditData) -> str:
    values: dict[str, Any] = data.model_dump()
    return "\n".join(
        [
            f"Автомобиль: {values['vehicle']}",
            f"Водитель: {values['driver']}",
            f"Серия и номер ТТН: {data.series_and_number}",
            f"Товар к перевозке принял: {values['goods_accepted_by']}",
            f"Отпуск разрешил: {values['release_allowed_by']}",
            f"Сдал грузоотправитель: {values['shipper_handed_over_by']}",
        ]
    )

