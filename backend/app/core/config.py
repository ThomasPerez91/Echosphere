"""Validated process configuration; secrets never enter frontend configuration."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra="ignore", hide_input_in_errors=True
    )

    postgres_host: str = Field(default="localhost", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = Field(default="echosphere", min_length=1)
    postgres_user: str = Field(default="echosphere", min_length=1)
    postgres_password: SecretStr = SecretStr("")
    database_connect_timeout: int = Field(default=3, ge=1, le=10)
    database_statement_timeout_ms: int = Field(default=3000, ge=100, le=10000)

    control_cert: Path = Path("/run/game-control/server.pem")
    control_key: Path = Path("/run/game-control/server.key")
    control_client_ca: Path = Path("/run/game-control/portal-ca.pem")
    control_peer_cert: Path = Path("/run/game-control/portal-client.pem")
    control_next_peer_cert: Path | None = None

    game_public_origin: str = "https://game.echosphere.localhost:8443"
    portal_public_origin: str = "https://portal.echosphere.localhost:8443"
    handoff_public_keys: dict[str, Path] = {"local-v1": Path("/run/game-handoff/local-v1.pem")}
    pre_auth_ip_limit: int = Field(default=60, ge=1, le=1000)
    trusted_proxy_host: str | None = None
    game_universe_session_limit: int = Field(default=10, ge=1, le=100)

    @field_validator("game_public_origin", "portal_public_origin")
    @classmethod
    def public_origin(cls, value):
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("An exact HTTPS origin is required")
        return value

    @model_validator(mode="after")
    def isolated_cookie_hosts(self):
        from urllib.parse import urlsplit

        if (
            urlsplit(self.game_public_origin).hostname
            == urlsplit(self.portal_public_origin).hostname
        ):
            raise ValueError("Portal and Game require distinct cookie hosts, not only ports")
        return self

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
