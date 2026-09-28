from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from core.config import CoreSettings


class Settings(CoreSettings):
    """Service-level configuration.

    Extends :class:`core.config.settings.CoreSettings` with settings that
    are specific to the ``washy_washy`` HTTP service (app metadata, API
    prefix, host/port, CORS) rather than shared infrastructure.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Washy Washy API"
    service_name: str = "washy-washy"

    api_v1_prefix: str = "/api/v1"

    service_host: str = "0.0.0.0"
    service_port: int = 8000

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    payment_webhook_secret: str = "change_me"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
