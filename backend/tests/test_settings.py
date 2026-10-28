import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_password_is_not_interpreted_as_url_syntax():
    secret = "a@b:/%?x#[]"
    settings = Settings(postgres_password=secret)
    assert settings.database_url.password == secret
    assert secret not in repr(settings)
    assert secret not in str(settings.database_url)


@pytest.mark.parametrize("port", [0, 65536, "not-a-port"])
def test_invalid_database_port_is_rejected(port):
    with pytest.raises(ValidationError):
        Settings(postgres_port=port)


def test_invalid_environment_is_rejected_without_printing_its_value(monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "sensitive-invalid-value")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "sensitive-invalid-value" not in str(error.value)
