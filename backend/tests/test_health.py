import psycopg
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_health_does_not_require_database(monkeypatch):
    def fail():
        raise AssertionError("Liveness must not query PostgreSQL")

    monkeypatch.setattr(main, "check_database", fail)
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_when_database_responds(monkeypatch):
    monkeypatch.setattr(main, "check_database", lambda: None)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_when_database_is_unavailable(monkeypatch):
    def fail():
        raise psycopg.OperationalError("internal connection details")

    monkeypatch.setattr(main, "check_database", fail)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert client.get("/health").status_code == 200
