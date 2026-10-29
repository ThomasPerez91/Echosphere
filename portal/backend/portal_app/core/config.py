"""Portal-only configuration; Game POSTGRES_* variables are never consumed."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PORTAL_", case_sensitive=False, extra="ignore", hide_input_in_errors=True
    )

    postgres_host: str = Field(default="localhost", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = Field(default="echosphere_accounts", min_length=1)
    postgres_user: str = Field(default="echosphere_accounts", min_length=1)
    postgres_password: SecretStr = SecretStr("")
    database_connect_timeout: int = Field(default=3, ge=1, le=10)
    database_statement_timeout_ms: int = Field(default=3000, ge=100, le=10000)
    database_pool_size: int = Field(default=3, ge=1, le=20)

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
