from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Resolve .env relative to this file so it works regardless of cwd
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    openai_key: Optional[str] = Field(default=None)
    gcp_key: Optional[str] = Field(default=None)
    database_url: str = Field(default="sqlite+aiosqlite:////app/data/apda.db")

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        extra="ignore",
    )


settings = Settings()
