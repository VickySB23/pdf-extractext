"""Application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    upload_dir: Path = Path("uploads")
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "pdf-extractext"
    max_upload_size_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
