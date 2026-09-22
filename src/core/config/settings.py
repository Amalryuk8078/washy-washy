from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    """Shared infrastructure configuration.

    Only settings that belong to shared infra (database, security, logging)
    live here. Service-level settings (app name, API prefix, CORS) live in
    ``washy_washy.config``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = False

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "washy_washy"
    postgres_user: str = "washy"
    postgres_password: str = "change_me"

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    log_level: str = "INFO"


@lru_cache
def get_core_settings() -> CoreSettings:
    return CoreSettings()
