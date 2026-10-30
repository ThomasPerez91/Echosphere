from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from portal_app.accounts.security import PublicError
from portal_app.main import create_app
from portal_app.sessions.models import LogoutRequest
from portal_app.sessions.receipts import COOKIE, RevocationReceipts
from portal_app.sessions.service import SESSION_COOKIE, Sessions, csrf

pytestmark = pytest.mark.integration


def test_status_capability_is_limited_expires_and_cannot_authenticate(accounts):
    accounts.register("receipt@example.org", "Receipt strong test phrase 2026 !", "peer")
    service = Sessions(accounts)
    challenge = service.challenge("peer")
    raw, _, _ = service.login(
        "receipt@example.org",
        "Receipt strong test phrase 2026 !",
        challenge,
        csrf(challenge),
        None,
        None,
        "peer",
    )
    app = create_app(accounts.settings)
    app.state.accounts = accounts
    client = TestClient(app, base_url=accounts.settings.public_origin)
    client.cookies.set(SESSION_COOKIE, raw)
    result = client.post(
        "/auth/logout",
        json={},
        headers={"Origin": accounts.settings.public_origin, "X-CSRF-Token": csrf(raw)},
    )
    assert result.status_code == 200 and "revocation_id" not in result.json()
    proof = client.cookies.get(COOKIE)
    receipts = RevocationReceipts(accounts)
    assert receipts.read(proof)["state"] == "pending"
    with pytest.raises(PublicError):
        service.read(proof)
    assert client.get("/auth/revocation-status").status_code == 403
    result = client.get("/auth/revocation-status", headers={"X-Portal-Request": "bootstrap"})
    assert result.status_code == 200 and set(result.json()) == {"state", "scope", "expires_at"}
    assert "receipt@example.org" not in result.text
    with accounts.factory.begin() as session:
        from sqlalchemy import select

        source = session.scalar(select(LogoutRequest))
        source.state = "acknowledged"
    assert receipts.read(proof)["state"] == "acknowledged"
    with pytest.raises(PublicError):
        receipts.read(proof[:80] + ("x" if proof[80] != "x" else "y") + proof[81:])
    accounts.test_clock[0] += timedelta(minutes=15)
    with pytest.raises(PublicError, match="receipt_expired"):
        receipts.read(proof)
