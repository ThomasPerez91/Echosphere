"""5D playable loop and Portal outage in an owned disposable Compose project, never retained data.

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
assert settings.postgres_db=='echosphere_colony_accounts_test'
engine=create_database_engine(settings)
a=Accounts(create_session_factory(engine),settings)
with a.factory.begin() as s:
    u=User(email='colony@example.org',email_key='colony@example.org',created_at=a.clock(),email_verified_at=a.clock())
    s.add(u);s.flush()
    s.add(PasswordCredential(user_id=u.id,password_hash=a.passwords.hasher.hash('A long test passphrase 2026 !'),changed_at=a.clock()))
    print(u.id)
Lobby(a).provision(UUID('__UNIVERSE__'),'Univers de recette 5D','test','primary')
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
assert settings.postgres_db=='echosphere_colony_accounts_test'
engine=create_database_engine(settings)
a=Accounts(create_session_factory(engine),settings)
Lobby(a).set_access(UUID('__USER__'),UUID('__UNIVERSE__'),'active',
    [{'empire_id':'__EMPIRE__','permissions':['colony.read','colony.construct','colony.cancel']}])
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
    project = f"echosphere-colony-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_colony_game_test",
        "POSTGRES_USER": "colony_test",
        "POSTGRES_PASSWORD": "colony_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_colony_accounts_test",
        "PORTAL_POSTGRES_USER": "colony_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "colony_accounts_local_test_only",
    }
    fixture = (ROOT / "scripts/colony_game_fixture.py").read_text()
    with tempfile.TemporaryDirectory(prefix="echosphere-colony-") as folder:
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
            print("Colony recipe: starting isolated project", flush=True)
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
                "Colony recipe: test-only account, universe, colony and Empire binding ready",
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
                os.environ.get("COLONY_ARTIFACTS", "/tmp/echosphere-colony-artifacts")
            )
            artifacts.mkdir(parents=True, exist_ok=True)
            names = (
                "built",
                "completed",
                "portal-stop",
                "portal-stopped",
                "expire",
                "expired",
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
                str(ROOT / "scripts/colony_browser.mjs") + ":/browser/colony.mjs:ro",
                "-v",
                str(artifacts.resolve()) + ":/artifacts",
                "-e",
                "COLONY_UNIVERSE=" + universe,
                "-e",
                "COLONY_ID=" + created["colony_id"],
                "-e",
                "COLONY_EDGE_IP=" + ip,
                "echosphere-handoff-browser:dev",
                "node",
                "/browser/colony.mjs",
            )
            done = set()
            deadline = time.monotonic() + 300
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
                            "Colony browser coordination exceeded its deadline"
                        )
                    if (artifacts / "built").exists() and "built" not in done:
                        # The page is closed: only the live worker can complete the order.
                        for _ in range(60):
                            rows = json.loads(
                                game(f"orders({created['colony_id']!r})").splitlines()[
                                    -1
                                ]
                            )
                            if rows and all(row[2] == "completed" for row in rows):
                                break
                            time.sleep(1)
                        else:
                            raise RuntimeError(
                                "Worker did not complete the accepted order"
                            )
                        (artifacts / "completed").write_text("ready")
                        done.add("built")
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
                    if (artifacts / "expire").exists() and "expire" not in done:
                        game(f"expire({universe!r})")
                        (artifacts / "expired").write_text("ready")
                        done.add("expire")
                    time.sleep(0.2)
                stdout, stderr = browser.communicate(timeout=10)
                if browser.returncode:
                    Path("/tmp/echosphere-colony-failure.log").write_text(
                        redacted(stdout + stderr)
                    )
                    raise RuntimeError("5D real browser scenario failed")
                assert done == {"built", "portal", "expire"}
                print(stdout)
        finally:
            if started:
                # This project and all its volumes were created by this recipe only (*_test, no port).
                run(*compose, "down", "--volumes", "--remove-orphans", env=environment)
    print(
        "Colony smoke passed; owned temporary project/volumes removed, retained stack preserved"
    )


if __name__ == "__main__":
    main()
