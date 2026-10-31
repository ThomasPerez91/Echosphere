"""Galaxy/Exploration loop and Portal outage in an owned disposable Compose project, never retained data.

Requires the images of the current tree (`docker compose build` or the CI `up --build` step).
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from smoke_handoff_compose import ROOT, redacted, run

PORTAL_FIXTURE = """
from uuid import UUID
from portal_app.accounts.models import User,PasswordCredential
from portal_app.accounts.service import Accounts
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine,create_session_factory
from portal_app.control.service import Lobby
settings=Settings()
assert settings.postgres_db=='echosphere_galaxy_accounts_test'
engine=create_database_engine(settings)
a=Accounts(create_session_factory(engine),settings)
with a.factory.begin() as s:
    u=User(email='galaxy@example.org',email_key='galaxy@example.org',created_at=a.clock(),email_verified_at=a.clock())
    s.add(u);s.flush()
    s.add(PasswordCredential(user_id=u.id,password_hash=a.passwords.hasher.hash('A long test passphrase 2026 !'),changed_at=a.clock()))
    print(u.id)
Lobby(a).provision(UUID('__UNIVERSE__'),'Univers de recette Galaxie','test','primary')
engine.dispose()
"""

PORTAL_ACCESS = """
import time
from uuid import UUID
from sqlalchemy import select
from portal_app.accounts.service import Accounts
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine,create_session_factory
from portal_app.control.service import Lobby
from portal_app.control.models import UniverseMembership
settings=Settings()
assert settings.postgres_db=='echosphere_galaxy_accounts_test'
engine=create_database_engine(settings)
a=Accounts(create_session_factory(engine),settings)
Lobby(a).set_access(UUID('__USER__'),UUID('__UNIVERSE__'),'active',
    [{'empire_id':'__EMPIRE__','permissions':['colony.read','galaxy.read','exploration.read','exploration.start']}])
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
    project = f"echosphere-galaxy-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_galaxy_game_test",
        "POSTGRES_USER": "galaxy_test",
        "POSTGRES_PASSWORD": "galaxy_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_galaxy_accounts_test",
        "PORTAL_POSTGRES_USER": "galaxy_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "galaxy_accounts_local_test_only",
    }
    fixture = (ROOT / "scripts/galaxy_game_fixture.py").read_text()
    with tempfile.TemporaryDirectory(prefix="echosphere-galaxy-") as folder:
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

        def game(call):
            return run(
                *compose,
                "exec",
                "-T",
                "backend",
                "python",
                "-",
                env=environment,
                input=fixture + "\n" + call + "\n",
            )

        started = False
        try:
            run(
                "docker",
                "build",
                "-t",
                "echosphere-handoff-browser:dev",
                "-f",
                "-",
                str(ROOT / "portal/frontend"),
                input="FROM mcr.microsoft.com/playwright:v1.56.1-noble\nWORKDIR /browser\n"
                "COPY package.json package-lock.json ./\nRUN npm ci\n",
            )
            print("Galaxy recipe: starting isolated project", flush=True)
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
            user = run(
                *compose,
                "exec",
                "-T",
                "portal-backend",
                "python",
                "-",
                env=environment,
                input=PORTAL_FIXTURE.replace("__UNIVERSE__", universe),
            ).splitlines()[-1]
            created = json.loads(game(f"setup({universe!r})").splitlines()[-1])
            run(
                *compose,
                "exec",
                "-T",
                "portal-backend",
                "python",
                "-",
                env=environment,
                input=PORTAL_ACCESS.replace("__USER__", user)
                .replace("__UNIVERSE__", universe)
                .replace("__EMPIRE__", created["empire_id"]),
            )
            print(
                "Galaxy recipe: test-only account, universe, generated galaxy, colony and Empire binding ready",
                flush=True,
            )
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
                os.environ.get("GALAXY_ARTIFACTS", "/tmp/echosphere-galaxy-artifacts")
            )
            artifacts.mkdir(parents=True, exist_ok=True)
            names = (
                "launched",
                "completed",
                "portal-stop",
                "portal-stopped",
                "outage-launched",
                "outage-completed",
                "expire",
                "expired",
                "expiry-checked",
                "expiry-completed",
            )
            for name in names:
                (artifacts / name).unlink(missing_ok=True)
            args = (
                "docker",
                "run",
                "--rm",
                "--network",
                network,
                "--ipc=host",
                "-v",
                str(ROOT / "scripts/galaxy_browser.mjs") + ":/browser/galaxy.mjs:ro",
                "-v",
                str(artifacts.resolve()) + ":/artifacts",
                "-e",
                "GALAXY_UNIVERSE=" + universe,
                "-e",
                "GALAXY_COLONY=" + created["colony_id"],
                "-e",
                "GALAXY_EMPIRE=" + created["empire_id"],
                "-e",
                "GALAXY_EDGE_IP=" + ip,
                "echosphere-handoff-browser:dev",
                "node",
                "/browser/galaxy.mjs",
            )

            def settled(count):
                # Proof read in Game DB while the page is closed: no GET can catch up lazily.
                for _ in range(90):
                    rows = json.loads(
                        game(f"missions({created['empire_id']!r})").splitlines()[-1]
                    )
                    if len(rows) == count and all(
                        row[:5] == ["completed", "MAPPED", True, True, True]
                        for row in rows
                    ):
                        return
                    time.sleep(1)
                raise RuntimeError(
                    f"Worker did not complete exploration {count}: {rows}"
                )

            done = set()
            deadline = time.monotonic() + 420
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
                            "Galaxy browser coordination exceeded its deadline"
                        )
                    if (artifacts / "launched").exists() and "launched" not in done:
                        # Page closed; the worker is restarted and alone completes the mission.
                        run(
                            *compose,
                            "restart",
                            "--timeout",
                            "5",
                            "worker",
                            env=environment,
                        )
                        settled(1)
                        (artifacts / "completed").write_text("ready")
                        done.add("launched")
                    if (artifacts / "portal-stop").exists() and "portal" not in done:
                        run(
                            *compose,
                            "stop",
                            "--timeout",
                            "3",
                            "portal-backend",
                            "portal-control-worker",
                            env=environment,
                        )
                        (artifacts / "portal-stopped").write_text("ready")
                        done.add("portal")
                    if (
                        artifacts / "outage-launched"
                    ).exists() and "outage" not in done:
                        settled(2)
                        (artifacts / "outage-completed").write_text("ready")
                        done.add("outage")
                    if (artifacts / "expire").exists() and "expire" not in done:
                        game(f"expire({universe!r})")
                        (artifacts / "expired").write_text("ready")
                        done.add("expire")
                    if (artifacts / "expiry-checked").exists() and "expiry" not in done:
                        # Accepted before expiry: the expedition still completes afterwards.
                        settled(3)
                        (artifacts / "expiry-completed").write_text("ready")
                        done.add("expiry")
                    time.sleep(0.2)
                stdout, stderr = browser.communicate(timeout=10)
                if browser.returncode:
                    Path("/tmp/echosphere-galaxy-failure.log").write_text(
                        redacted(stdout + stderr)
                    )
                    print(redacted(stdout + stderr)[-12000:], flush=True)
                    raise RuntimeError("Galaxy real browser scenario failed")
                assert done == {"launched", "portal", "outage", "expire", "expiry"}
                print(stdout)
        finally:
            if started:
                # This project and all its volumes were created by this recipe only (*_test, no port).
                run(*compose, "down", "--volumes", "--remove-orphans", env=environment)
    print(
        "Galaxy smoke passed; owned temporary project/volumes removed, retained stack preserved"
    )


if __name__ == "__main__":
    main()
