import ssl

from fastapi.testclient import TestClient

from app.control.http import create_internal_app, fingerprint
from app.core.config import Settings
from app.main import create_app


def test_headers_and_https_scheme_do_not_authenticate_an_internal_caller(tmp_path):
    certificate = tmp_path / "public.pem"
    # ASGI trust-boundary test only; real certificate validation is exercised over TLS by the smoke.
    certificate.write_text(ssl.DER_cert_to_PEM_cert(b"unit-public-identity"))
    settings = Settings(control_peer_cert=certificate)
    app = create_internal_app(settings)
    with TestClient(app, base_url="https://game-control:9443") as client:
        response = client.get(
            "/internal/v1/health",
            headers={
                "X-Control-Service": "portal-control",
                "X-Forwarded-Proto": "https",
                "X-Client-Cert": certificate.read_text(),
            },
        )
        assert response.status_code == 403

    async def verified(scope, receive, send):
        await app({**scope, "control_peer": fingerprint(certificate)}, receive, send)

    with TestClient(verified, base_url="https://game-control:9443") as client:
        assert client.get("/internal/v1/health").json() == {"status": "ok"}
        assert client.post("/internal/v1/operations", content="x" * 65537).status_code == 413
    with TestClient(create_app(), base_url="https://game.example.org") as client:
        assert (
            client.get(
                "/internal/v1/health", headers={"X-Control-Service": "portal-control"}
            ).status_code
            == 404
        )
