"""C07 real browser handoff in an owned disposable Compose project, never retained databases."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(*args, input=None, env=None):
    result = subprocess.run(
        args,
        cwd=ROOT,
        input=input,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode:
        Path("/tmp/echosphere-handoff-failure.log").write_text(
            result.stdout + result.stderr
        )
        # Never print command arguments, environment, credentials, tokens or raw DB exceptions.
        raise RuntimeError(
            f"Handoff recipe failed: {args[0]} (exit {result.returncode})"
        )
    return result.stdout.strip()


FIXTURE = """
from uuid import UUID
from sqlalchemy import select
from portal_app.accounts.models import User,PasswordCredential
from portal_app.accounts.service import Accounts
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine,create_session_factory
from portal_app.control.service import Lobby
import time
settings=Settings()
assert settings.postgres_db.endswith('_test')
engine=create_database_engine(settings)
a=Accounts(create_session_factory(engine),settings)
with a.factory.begin() as s:
    u=User(email='handoff@example.org',email_key='handoff@example.org',created_at=a.clock(),email_verified_at=a.clock())
    s.add(u);s.flush()
    s.add(PasswordCredential(user_id=u.id,password_hash=a.passwords.hasher.hash('A long test passphrase 2026 !'),changed_at=a.clock()))
    user=u.id
l=Lobby(a)
l.provision(UUID('__UNIVERSE__'),'C07 browser test only','test','primary')
l.set_access(user,UUID('__UNIVERSE__'),'active',[])
from portal_app.control.models import UniverseMembership
for _ in range(30):
    with a.factory() as s:
        m=s.scalar(select(UniverseMembership))
        done=m.applied_snapshot==m.desired_snapshot and not m.reconciliation_pending
    if done:break
    time.sleep(1)
assert done
engine.dispose()
"""


def main():
    suffix = uuid4().hex[:8]
    project = f"echosphere-handoff-{suffix}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_handoff_game_test",
        "POSTGRES_USER": "handoff_test",
        "POSTGRES_PASSWORD": "handoff_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_handoff_accounts_test",
        "PORTAL_POSTGRES_USER": "handoff_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "handoff_accounts_local_test_only",
    }
    with tempfile.TemporaryDirectory(prefix="echosphere-handoff-") as folder:
        override = Path(folder) / "compose.yml"
        override.write_text("""services:
  backend:
    ports: !reset []
  frontend:
    image: echosphere-frontend:latest
    ports: !reset []
  portal-frontend:
    image: echosphere-portal-frontend:latest
  local-edge:
    ports: !reset []
""")
        compose = (
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(override),
        )
        started = False
        try:
            dockerfile = """FROM mcr.microsoft.com/playwright:v1.56.1-noble
WORKDIR /browser
COPY package.json package-lock.json ./
RUN npm ci
"""
            run(
                "docker",
                "build",
                "-t",
                "echosphere-handoff-browser:dev",
                "-f",
                "-",
                str(ROOT / "portal/frontend"),
                input=dockerfile,
            )
            print("Handoff recipe: starting isolated project", flush=True)
            started = True
            run(
                *compose,
                "up",
                "--no-build",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                env=environment,
            )
            print("Handoff recipe: provisioning test-only membership", flush=True)
            # Test-only provisioning uses Accounts and the authenticated private Game interface.
            run(
                *compose,
                "exec",
                "-T",
                "portal-backend",
                "python",
                "-",
                env=environment,
                input=FIXTURE.replace("__UNIVERSE__", universe),
            )
            print("Handoff recipe: running real HTTPS Chromium", flush=True)
            edge = json.loads(
                run(
                    "docker",
                    "inspect",
                    run(*compose, "ps", "-q", "local-edge", env=environment),
                )
            )[0]
            network = project + "_default"
            ip = edge["NetworkSettings"]["Networks"][network]["IPAddress"]
            artifacts = Path(
                os.environ.get("HANDOFF_ARTIFACTS", "/tmp/echosphere-handoff-artifacts")
            )
            artifacts.mkdir(parents=True, exist_ok=True)
            print(
                run(
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    network,
                    "--ipc=host",
                    "-v",
                    str(ROOT / "scripts/handoff_browser.mjs")
                    + ":/browser/handoff.mjs:ro",
                    "-v",
                    str(artifacts.resolve()) + ":/artifacts",
                    "-e",
                    "HANDOFF_UNIVERSE=" + universe,
                    "-e",
                    "HANDOFF_EDGE_IP=" + ip,
                    "echosphere-handoff-browser:dev",
                    "node",
                    "/browser/handoff.mjs",
                )
            )
        finally:
            if started:
                # This project and all its volumes were created by this recipe only.
                # Its DB names are *_test and it publishes no host port.
                run(*compose, "down", "--volumes", "--remove-orphans", env=environment)
    print(
        "Handoff smoke passed; owned temporary project/volumes removed, retained stack preserved"
    )


if __name__ == "__main__":
    main()
