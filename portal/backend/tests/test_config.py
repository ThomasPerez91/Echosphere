import pytest
from pydantic import ValidationError

from portal_app.core.config import Settings


def test_game_environment_cannot_configure_portal(monkeypatch):
    for name in ("HOST", "PORT", "DB", "USER", "PASSWORD"):
        monkeypatch.delenv(f"PORTAL_POSTGRES_{name}", raising=False)
        monkeypatch.setenv(f"POSTGRES_{name}", "game-only")
    settings = Settings()
    assert settings.postgres_db == "echosphere_accounts"
    assert settings.postgres_user == "echosphere_accounts"
    assert settings.postgres_password.get_secret_value() == ""


def test_portal_secret_is_not_interpreted_as_url_syntax_or_printed(monkeypatch):
    secret = "portal@:/%?password"
    monkeypatch.setenv("PORTAL_POSTGRES_PASSWORD", secret)
    settings = Settings()
    assert settings.database_url.password == secret
    assert secret not in repr(settings)
    assert secret not in str(settings.database_url)


def test_invalid_configuration_hides_environment_value(monkeypatch):
    monkeypatch.setenv("PORTAL_POSTGRES_PORT", "private-invalid-input")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "private-invalid-input" not in str(error.value)


@pytest.mark.parametrize("size", [0, 21])
def test_pool_is_bounded(size):
    with pytest.raises(ValidationError):
        Settings(database_pool_size=size)
