from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import probes
from app.main import create_app


def test_health_does_not_require_database(monkeypatch):
    def fail(engine):
        raise AssertionError("Liveness must not query PostgreSQL")

    monkeypatch.setattr(probes, "check_database", fail)
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_ready_when_database_responds(monkeypatch):
    monkeypatch.setattr(probes, "check_database", lambda engine: None)
    with TestClient(create_app()) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_ready_when_database_is_unavailable(monkeypatch):
    def fail(engine):
        raise OperationalError("SELECT 1", {}, Exception("internal connection details"))

    monkeypatch.setattr(probes, "check_database", fail)
    with TestClient(create_app()) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert client.get("/health").status_code == 200
