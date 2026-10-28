"""Run after docker compose up --build -d --wait. Leaves cleanup to the caller."""

import json
import subprocess
import time
import urllib.error
import urllib.request


def get(path):
    try:
        with urllib.request.urlopen(path, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def wait_ready():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if get("http://localhost:8000/ready")[0] == 200:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(1)
    raise AssertionError("Backend did not recover PostgreSQL readiness within 60 seconds")


assert get("http://localhost:8000/health") == (200, '{"status":"ok"}')
assert json.loads(get("http://localhost:8000/ready")[1]) == {"status": "ready"}
status, page = get("http://localhost:5173")
assert status == 200 and "Echosphere" in page
status, body = get("http://localhost:5173/api/ready")
assert status == 200 and json.loads(body) == {"status": "ready"}
subprocess.run(["docker", "compose", "stop", "postgres"], check=True)
try:
    assert get("http://localhost:8000/health")[0] == 200
    status, body = get("http://localhost:8000/ready")
    assert status == 503 and json.loads(body) == {"detail": "Database unavailable"}
finally:
    subprocess.run(["docker", "compose", "start", "postgres"], check=True)
wait_ready()
assert get("http://localhost:5173/api/ready")[0] == 200
print("Compose smoke passed: frontend, proxy, API, PostgreSQL failure and recovery")
