"""C07 real browser handoff in an owned disposable Compose project, never retained databases."""

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def redacted(value):
    return re.sub(r"(?im)^.*(?:cookie|authorization):.*$", "[redacted credential header]", value)


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
            redacted(result.stdout + result.stderr)
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
            for name in (
                "outage-ready",
                "outage-stopped",
                "outage-checked",
                "outage-resumed",
                "revocation-ready",
                "revocation-acked",
            ):
                (artifacts / name).unlink(missing_ok=True)
            args = (
                "docker",
                "run",
                "--rm",
                "--network",
                network,
                "--ipc=host",
                "-v",
                str(ROOT / "scripts/handoff_browser.mjs") + ":/browser/handoff.mjs:ro",
                "-v",
                str(artifacts.resolve()) + ":/artifacts",
                "-e",
                "HANDOFF_UNIVERSE=" + universe,
                "-e",
                "HANDOFF_EDGE_IP=" + ip,
                "-e",
                "C09_OUTAGE=1",
                "echosphere-handoff-browser:dev",
                "node",
                "/browser/handoff.mjs",
            )
            stopped = resumed = acknowledged = False
            deadline = time.monotonic() + 180
            with subprocess.Popen(
                args,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as browser:
                while browser.poll() is None:
                    if time.monotonic() >= deadline:
                        browser.terminate()
                        raise RuntimeError(
                            "C09 browser coordination exceeded its deadline"
                        )
                    if (artifacts / "outage-ready").exists() and not stopped:
                        run(
                            *compose,
                            "stop",
                            "--timeout",
                            "3",
                            "portal-backend",
                            "portal-control-worker",
                            env=environment,
                        )
                        fixture = (ROOT / "scripts/c09_game_fixture.py").read_text()
                        run(
                            *compose,
                            "exec",
                            "-T",
                            "backend",
                            "python",
                            "-",
                            env=environment,
                            input=fixture + f"\nmain({universe!r})\n",
                        )
                        print(
                            "C09: Portal stopped; live Game worker completed an accepted action",
                            flush=True,
                        )
                        (artifacts / "outage-stopped").write_text("ready")
                        stopped = True
                    if (artifacts / "outage-checked").exists() and not resumed:
                        run(*compose, "start", "portal-backend", env=environment)
                        for _ in range(30):
                            # Wait inside its own service; no cross-origin request or SQL Game.
                            try:
                                run(
                                    *compose,
                                    "exec",
                                    "-T",
                                    "portal-backend",
                                    "python",
                                    "-c",
                                    "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')",
                                    env=environment,
                                )
                                break
                            except RuntimeError:
                                time.sleep(0.2)
                        (artifacts / "outage-resumed").write_text("ready")
                        resumed = True
                    if (artifacts / "revocation-ready").exists() and not acknowledged:
                        run(*compose, "start", "portal-control-worker", env=environment)
                        run(
                            *compose,
                            "exec",
                            "-T",
                            "portal-backend",
                            "python",
                            "-",
                            env=environment,
                            input="""import time
from sqlalchemy import select
from portal_app.main import app
from portal_app.sessions.models import LogoutRequest
for _ in range(30):
    with app.state.accounts.factory() as s:
        rows=list(s.scalars(select(LogoutRequest)))
        done=bool(rows) and all(r.state=='acknowledged' for r in rows)
    if done:break
    time.sleep(1)
assert done
""",
                        )
                        (artifacts / "revocation-acked").write_text("ready")
                        acknowledged = True
                    time.sleep(0.2)
                stdout, stderr = browser.communicate(timeout=10)
                if browser.returncode:
                    Path("/tmp/echosphere-handoff-failure.log").write_text(
                        stdout + stderr
                    )
                    raise RuntimeError("C09 real browser scenario failed")
                assert stopped and resumed and acknowledged
                print(stdout)
            # Verify independent DB backup/restore on disposable databases only; never bring the
            # restored snapshots online as authenticated services without a recovery barrier.
            for service, version_table, expected in (
                ("postgres", "alembic_version", "0007_empire_research"),
                ("portal-postgres", "portal_alembic_version", "p0005_control"),
            ):
                run(
                    *compose,
                    "exec",
                    "-T",
                    service,
                    "sh",
                    "-c",
                    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/c09.dump && '
                    'createdb -U "$POSTGRES_USER" echosphere_restore_test && '
                    'pg_restore -U "$POSTGRES_USER" -d echosphere_restore_test --no-owner /tmp/c09.dump',
                    env=environment,
                )
                restored = run(
                    *compose,
                    "exec",
                    "-T",
                    service,
                    "sh",
                    "-c",
                    'psql -U "$POSTGRES_USER" -d echosphere_restore_test -Atc "$1"',
                    "sh",
                    f"SELECT version_num FROM {version_table}",
                    env=environment,
                )
                assert restored == expected
                run(
                    *compose,
                    "exec",
                    "-T",
                    service,
                    "sh",
                    "-c",
                    'dropdb -U "$POSTGRES_USER" echosphere_restore_test && rm /tmp/c09.dump',
                    env=environment,
                )
            print(
                "C09: both disposable databases backed up/restored with correct migration heads",
                flush=True,
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
