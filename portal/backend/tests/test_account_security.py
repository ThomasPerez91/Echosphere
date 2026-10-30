import hashlib

import httpx
import pytest
from fastapi.testclient import TestClient

from portal_app.accounts.security import Passwords, PublicError, PwnedPasswords, normalize_email
from portal_app.main import create_app


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length_is_not_truncated(password):
    with pytest.raises(PublicError, match="password_rejected"):
        Passwords().new_hash(password)


def test_compromised_lookup_sends_only_prefix_and_requires_valid_padded_response():
    password = "Common compromised test password"
    fingerprint = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()

    def handler(request):
        assert str(request.url) == f"https://api.pwnedpasswords.com/range/{fingerprint[:5]}"
        assert request.headers["Add-Padding"] == "true"
        assert password not in str(request.url) and not request.content
        return httpx.Response(200, text=f"{fingerprint[5:]}:4\r\n{'0' * 35}:0")

    checker = PwnedPasswords(httpx.MockTransport(handler))
    with pytest.raises(PublicError, match="password_rejected"):
        Passwords(checker).new_hash(password)


@pytest.mark.parametrize(
    "response",
    [httpx.Response(503), httpx.Response(200, text="invalid"), httpx.Response(200, text="")],
)
def test_compromised_service_failure_refuses_without_weak_fallback(response):
    checker = PwnedPasswords(httpx.MockTransport(lambda request: response))
    with pytest.raises(PublicError, match="temporarily_unavailable"):
        checker.compromised("Strong test phrase with spaces")


def test_email_normalization_preserves_provider_aliases():
    address, key = normalize_email("Some.Name+label@EXAMPLE.org")
    assert address == "Some.Name+label@example.org"
    assert key == "some.name+label@example.org"


def test_request_errors_never_echo_passwords_or_tokens_and_origin_is_required():
    with TestClient(create_app()) as client:
        secret = "Never reflect this test input"
        wrong = client.post("/accounts/register", json={"email": 42, "password": secret})
        assert wrong.status_code == 422 and secret not in wrong.text
        large = client.post("/accounts/register", content=secret * 1000)
        assert large.status_code == 413 and secret not in large.text
        origin = client.post(
            "/accounts/register",
            json={"email": "player@example.org", "password": secret},
            headers={"Origin": "https://untrusted.invalid"},
        )
        assert origin.status_code == 403
        assert origin.headers["Cache-Control"] == "no-store"


def test_outbox_key_initialization_is_private_and_idempotent(tmp_path):
    from portal_app.core.init_secrets import initialize

    path = tmp_path / "secrets" / "email.key"
    initialize(path)
    first = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    initialize(path)
    assert path.read_bytes() == first
