from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from portal_app.api import probes
from portal_app.main import create_app


def test_health_is_available_without_accounts(monkeypatch):
    def fail(engine):
        raise AssertionError("Liveness must not query Accounts")

    monkeypatch.setattr(probes, "check_database", fail)
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok", "service": "portal"}


def test_readiness_and_failure_do_not_expose_connection_details(monkeypatch):
    monkeypatch.setattr(probes, "check_database", lambda engine: None)
    with TestClient(create_app()) as client:
        assert client.get("/ready").json() == {"status": "ready", "service": "portal"}

        def fail(engine):
            raise OperationalError("SELECT 1", {}, Exception("private-connection-details"))

        monkeypatch.setattr(probes, "check_database", fail)
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert client.get("/health").status_code == 200


def test_cross_origin_credentials_are_not_enabled():
    with TestClient(create_app()) as client:
        response = client.options(
            "/ready",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers
