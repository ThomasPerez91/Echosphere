"""Portal-only configuration; Game POSTGRES_* variables are never consumed."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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

    public_origin: str = "https://portal.echosphere.localhost:8443"
    mail_key_file: Path = Path("/run/portal-secrets/email.key")
    mail_transport: str = "disabled"
    mail_host: str = "portal-mailpit"
    mail_port: int = Field(default=1025, ge=1, le=65535)
    mail_poll_seconds: int = Field(default=2, ge=1, le=60)
    registration_ip_limit: int = Field(default=20, ge=1, le=1000)
    email_request_limit: int = Field(default=5, ge=1, le=100)
    verification_ip_limit: int = Field(default=30, ge=1, le=1000)
    verification_token_limit: int = Field(default=10, ge=1, le=100)
    connected_device_limit: int = Field(default=10, ge=1, le=100)
    login_ip_limit: int = Field(default=30, ge=1, le=1000)
    login_account_limit: int = Field(default=10, ge=1, le=100)
    bootstrap_ip_limit: int = Field(default=60, ge=1, le=1000)
    security_ip_limit: int = Field(default=30, ge=1, le=1000)
    security_subject_limit: int = Field(default=10, ge=1, le=100)
    reset_response_floor_ms: int = Field(default=150, ge=50, le=1000)
    security_notice_hours: int = Field(default=24, ge=1, le=168)
    trusted_proxy_host: str | None = None

    @field_validator("public_origin")
    @classmethod
    def check_origin(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError("Portal origin must be an HTTPS origin without userinfo/path/query")
        return value.rstrip("/")

    @field_validator("mail_transport")
    @classmethod
    def check_transport(cls, value: str) -> str:
        if value not in ("disabled", "smtp_local"):
            raise ValueError("No production email provider has been selected")
        return value

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
