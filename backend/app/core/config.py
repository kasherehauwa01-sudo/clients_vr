from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clients VR"
    database_url: str = "sqlite:///./clients.db"
    cors_origins: list[str] = ["https://kvasmix.ru", "http://localhost:5173", "http://localhost:8015"]
    auto_create_tables: bool = True
    public_base_path: str = "/vr/clients"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CLIENTS_", extra="ignore")

    @property
    def normalized_base_path(self) -> str:
        value = "/" + self.public_base_path.strip("/")
        return "" if value == "/" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
