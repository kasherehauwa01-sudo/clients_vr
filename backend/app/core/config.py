from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clients VR"
    database_url: str = "sqlite:///./clients.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CLIENTS_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
