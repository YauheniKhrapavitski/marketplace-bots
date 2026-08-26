from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    telegram_bot_token: str = ""
    questions_telegram_bot_token: str = ""
    ozon_telegram_bot_token: str = ""
    telegram_admin_ids: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/wb_assistant"
    wb_api_base_url: str = "https://feedbacks-api-sandbox.wildberries.ru"
    wb_api_token: str = ""
    wb_environment: Literal["sandbox", "production"] = "sandbox"
    ozon_api_base_url: str = "https://api-seller.ozon.ru"
    ozon_client_id: str = ""
    ozon_api_key: str = ""
    ozon_environment: Literal["production"] = "production"
    app_encryption_key: str = ""
    brand_name: str = ""
    answer_signature: str = ""
    sync_interval_minutes: int = Field(default=10, ge=5, le=1440)
    feedback_scheduler_enabled: bool = False
    question_scheduler_enabled: bool = False
    question_auto_send_enabled: bool = False
    postpone_hours: int = Field(default=24, ge=1, le=720)
    http_connect_timeout: float = 10
    http_read_timeout: float = 30
    http_max_retries: int = Field(default=5, ge=0, le=10)
    wb_api_min_interval_seconds: float = 0
    ozon_http_connect_timeout: float = 5
    ozon_http_read_timeout: float = 10
    ozon_http_max_retries: int = Field(default=1, ge=0, le=3)

    @field_validator("database_url")
    @classmethod
    def reject_sqlite_database(cls, value: str) -> str:
        if value.startswith("sqlite"):
            msg = "SQLite is not allowed for application configuration"
            raise ValueError(msg)
        return value

    @property
    def admin_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.telegram_admin_ids.split(","):
            item = raw.strip()
            if item:
                ids.add(int(item))
        return ids

    @property
    def telegram_configured(self) -> bool:
        return bool(
            self.telegram_bot_token
            or self.questions_telegram_bot_token
            or self.ozon_telegram_bot_token
        )

    @property
    def required_configured(self) -> bool:
        return bool(
            (
                self.telegram_bot_token
                or self.questions_telegram_bot_token
                or self.ozon_telegram_bot_token
            )
            and self.admin_ids
            and self.app_encryption_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
