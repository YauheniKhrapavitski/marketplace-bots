from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    allowed_user_ids: list[int] = Field(default_factory=list, alias="ALLOWED_USER_IDS")
    max_file_size_mb: int = Field(default=30, alias="MAX_FILE_SIZE_MB")
    temp_file_lifetime_hours: int = Field(default=24, alias="TEMP_FILE_LIFETIME_HOURS")
    max_concurrent_jobs: int = Field(default=2, alias="MAX_CONCURRENT_JOBS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_path: Path = Field(default=Path("data/bot.sqlite3"), alias="DATABASE_PATH")
    ttn_template_path: Path = Field(
        default=Path("config/ttn_templates/ozon_ttn_a4.json"), alias="TTN_TEMPLATE_PATH"
    )
    font_path: Path = Field(default=Path("assets/fonts/DejaVuSans.ttf"), alias="FONT_PATH")
    temp_dir: Path = Field(default=Path("tmp/ttn_jobs"), alias="TEMP_DIR")

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        raise TypeError("ALLOWED_USER_IDS must be empty or comma-separated Telegram IDs")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
