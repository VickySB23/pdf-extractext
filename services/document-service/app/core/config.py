"""Application settings."""

from functools import lru_cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "pdf-extractext"
    extraction_url: str = "http://localhost:8001"
    consul_url: str | None = None
    max_upload_size_bytes: int = 10 * 1024 * 1024
    rate_limit_average: PositiveInt = 20
    rate_limit_burst: PositiveInt = 40

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

