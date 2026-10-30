"""Verify both local HTTPS origins and database isolation; never change host CA trust.

Run on a local/test stack: this deliberately stops and restarts each PostgreSQL.
No volumes/data are removed. A retry uses the existing absolute test deadline.
"""

import http.client
import json
import socket
import ssl
import subprocess
import time


def compose(*args):
    return subprocess.run(
        ["docker", "compose", *args], check=True, capture_output=True, text=True
    ).stdout


def tls_context():
    # Only the public development CA certificate leaves Docker, in memory.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            root = compose(
                "exec", "-T", "local-edge", "cat", "/data/caddy/pki/authorities/local/root.crt"
            )
            return ssl.create_default_context(cadata=root)
        except subprocess.CalledProcessError:
            time.sleep(1)
    raise AssertionError("The local development CA was not initialized within 30 seconds")



def get(context, host, path, method="GET", headers=None):
    connection = http.client.HTTPSConnection(host, 8443, context=context, timeout=10)
    try:
        connection.sock = context.wrap_socket(
            socket.create_connection(("127.0.0.1", 8443), timeout=10), server_hostname=host
        )
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        connection.close()


def wait_ready(context, host):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if get(context, host, "/api/ready")[0] == 200:
                return
        except (OSError, http.client.HTTPException):
            pass
        time.sleep(1)
    raise AssertionError(f"{host} did not become ready within 60 seconds")


def query(service, sql):
    return compose(
        "exec", "-T", service, "sh", "-c",
        'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"', "sh", sql,
    ).strip()


def main():
    context = tls_context()
    for host in ("portal.echosphere.localhost", "game.echosphere.localhost"):
        wait_ready(context, host)
        status, page, _ = get(context, host, "/")
        assert status == 200 and "Echosphere" in page
    assert json.loads(get(context, "portal.echosphere.localhost", "/api/ready")[1]) == {
        "status": "ready", "service": "portal"
    }
    assert json.loads(get(context, "game.echosphere.localhost", "/api/ready")[1]) == {
        "status": "ready"
    }

    # Exercise real TLS routing/cookie flags without creating a runtime account.
    status, body, cookie_headers = get(
        context, "portal.echosphere.localhost", "/api/auth/challenge",
        headers={"X-Portal-Request": "bootstrap"},
    )
    assert status == 200 and len(json.loads(body)["csrf_token"]) == 64
    protected = {key.lower(): value for key, value in cookie_headers.items()}
    cookie = protected["set-cookie"]
    assert cookie.startswith("__Host-portal-login=")
    assert all(flag in cookie for flag in ("Secure", "HttpOnly", "SameSite=strict", "Path=/"))
    assert "Domain=" not in cookie and protected["cache-control"] == "no-store"
    assert get(context, "portal.echosphere.localhost", "/api/auth/session",
        headers={"X-Portal-Request": "bootstrap"})[0] == 401
    assert get(context, "portal.echosphere.localhost", "/api/auth/session", headers={
        "X-Portal-Request": "bootstrap", "Origin": "https://game.echosphere.localhost:8443"
    })[0] == 403

    # A real preflight through the Portal origin does not open credentialed CORS.
    _, _, headers = get(
        context, "portal.echosphere.localhost", "/api/ready", method="OPTIONS", headers={
            "Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {name.lower() for name in headers}
    assert "access-control-allow-credentials" not in {name.lower() for name in headers}

    # Mailpit stays internal; only its UI is proxied on the explicit loopback host.
    receiver = http.client.HTTPConnection("127.0.0.1", 8025, timeout=5)
    try:
        receiver.request("GET", "/api/v1/info")
        response = receiver.getresponse()
        assert response.status == 200
        assert isinstance(json.loads(response.read()), dict)
    finally:
        receiver.close()

    identity = "SELECT current_database() || '/' || current_user"
    assert query("portal-postgres", identity) != query("postgres", identity)
    assert query("portal-postgres", "SELECT version_num FROM portal_alembic_version") == (
        "p0003_account_security"
    )
    assert query("postgres", "SELECT version_num FROM alembic_version") == "0004_colony_economy"
    tables = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    assert set(query("portal-postgres", tables).splitlines()) == {
        "portal_alembic_version", "users", "password_credentials", "account_tokens",
        "email_outbox", "abuse_counters", "security_events",
        "browser_profiles", "account_devices", "portal_sessions",
        "login_challenges", "logout_requests",
        "security_email_outbox", "account_revocations", "step_up_grants",
        "email_change_requests", "password_reset_requests",
    }
    assert "portal_alembic_version" not in query("postgres", tables).splitlines()

    compose("stop", "portal-postgres")
    try:
        assert get(context, "portal.echosphere.localhost", "/api/health")[0] == 200
        status, body, _ = get(context, "portal.echosphere.localhost", "/api/ready")
        assert status == 503 and json.loads(body) == {"detail": "Database unavailable"}
        assert get(context, "game.echosphere.localhost", "/api/ready")[0] == 200
    finally:
        compose("start", "portal-postgres")
    wait_ready(context, "portal.echosphere.localhost")

    compose("stop", "postgres")
    try:
        assert get(context, "game.echosphere.localhost", "/api/health")[0] == 200
        assert get(context, "game.echosphere.localhost", "/api/ready")[0] == 503
        assert get(context, "portal.echosphere.localhost", "/api/ready")[0] == 200
    finally:
        compose("start", "postgres")
    wait_ready(context, "game.echosphere.localhost")
    print("Portal smoke passed: verified HTTPS, routing, separate Accounts/Game histories, "
          "CORS denied, independent PostgreSQL failure and recovery")


if __name__ == "__main__":
    main()
