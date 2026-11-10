from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    admin_username: str
    admin_password: str
    session_secret: str

    storage_dir: Path = Path("data/storage")
    model_dir: Path = Path("data/models")
    content_dir: Path = Path("../content")

    max_image_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    max_request_bytes: int = 70 * 1024 * 1024

    # Starting values. Tune them on real phone photos.
    min_sharpness: float = 30.0
    min_brightness: float = 40.0
    gate_min_score: float = 0.6

    app_rate_limit_per_minute: int = 60
    login_rate_limit_per_minute: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
