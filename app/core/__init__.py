"""Core configuration module."""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
# Directorio de subidas (que ya usabas en main.py)
    upload_dir: Path = Path("uploads")
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "pdf-extractext"
    nvidia_api_key: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
