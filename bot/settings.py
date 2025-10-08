# bot/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, Field
from typing import Optional


class Settings(BaseSettings):
    # Telegram
    TG_TOKEN: str = Field(..., description="Telegram Bot Token")

    # Aviasales (раскомментируешь, когда подключим API)
    AVIASALES_API_TOKEN: str

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_TZ: str = "Europe/Istanbul"

    @property
    def DB_DSN(self) -> str:
        """
        Составляем DSN для asyncpg/SQLAlchemy.
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    REDIS_PASSWORD: str = ""
    REDIS_HOST: str
    REDIS_PORT: int = 6379

    @property
    def REDIS_DSN(self) -> str:
        return f"redis://default:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"


    # Scheduler / Timezone
    TIMEZONE: str = Field("Europe/Istanbul", description="Default timezone for scheduler and user TZ fallback")

    # Logging
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    WORKER_LOG_FILE: str = Field("worker.log", description="Worker log file path")

    # Feature toggles
    DEBUG: bool = Field(False, description="Enable debug mode")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
