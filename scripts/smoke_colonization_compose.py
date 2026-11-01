"""Colonization loop, two-Empire contest with two workers, Portal outage, owned Compose project.

Requires the images of the current tree (`docker compose build` or the CI `up --build` step).
Only *_test databases and this project's own volumes are created, then removed.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from smoke_galaxy_compose import PORTAL_ACCESS, PORTAL_FIXTURE
from smoke_handoff_compose import ROOT, redacted, run

RIGHTS = "['colony.read','galaxy.read','fleet.read','fleet.build','fleet.command','colony.expand']"
M = 1_000_000


def main():
    project = f"echosphere-colonization-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_colonization_game_test",
        "POSTGRES_USER": "colonization_test",
        "POSTGRES_PASSWORD": "colonization_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_colonization_accounts_test",
        "PORTAL_POSTGRES_USER": "colonization_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "colonization_accounts_local_test_only",
    }
    portal_fixture = (
        PORTAL_FIXTURE.replace(
            "echosphere_galaxy_accounts_test", "echosphere_colonization_accounts_test"
        )
        .replace("galaxy@example.org", "colonization@example.org")
        .replace("Univers de recette Galaxie", "Univers de recette Colonisation")
    )
    portal_access = PORTAL_ACCESS.replace(
        "echosphere_galaxy_accounts_test", "echosphere_colonization_accounts_test"
    ).replace("['colony.read','galaxy.read','exploration.read','exploration.start']", RIGHTS)
    assert RIGHTS in portal_access, "Colonization rights must reach the binding"
    fixture = (ROOT / "scripts/colonization_game_fixture.py").read_text()
    with tempfile.TemporaryDirectory(prefix="echosphere-colonization-") as folder:
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
        compose = ("docker", "compose", "-p", project, "-f", str(ROOT / "docker-compose.yml"))
        compose += ("-f", str(override))

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
            ).splitlines()[-1]

        def portal(source):
            return run(
                *compose,
                "exec",
                "-T",
                "portal-backend",
                "python",
                "-",
                env=environment,
                input=source,
            )

        def wait(check, label, call, timeout=120):
            for _ in range(timeout):
                current = json.loads(game(call))
                if check(current):
                    return current
                time.sleep(1)
            raise RuntimeError(f"Colonization recipe: {label} not reached: {current}")

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
            print("Colonization recipe: starting isolated project", flush=True)
            started = True
            up = ("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
            run(*compose, *up, env=environment)
            user = portal(portal_fixture.replace("__UNIVERSE__", universe)).splitlines()[-1]
            created = json.loads(game(f"setup({universe!r})"))
            portal(
                portal_access.replace("__USER__", user)
                .replace("__UNIVERSE__", universe)
                .replace("__EMPIRE__", created["empire_id"])
            )
            print("Colonization recipe: test-only account, v0.5 universe and rights", flush=True)
            edge = json.loads(
                run("docker", "inspect", run(*compose, "ps", "-q", "local-edge", env=environment))
            )[0]
            network = project + "_default"
            ip = edge["NetworkSettings"]["Networks"][network]["IPAddress"]
            default = "/tmp/echosphere-colonization-artifacts"
            artifacts = Path(os.environ.get("COLONIZATION_ARTIFACTS", default))
            artifacts.mkdir(parents=True, exist_ok=True)
            names = ["ordered", "produced", "launched", "founded", "portal-stop", "portal-stopped"]
            names += ["contested", "expire", "expired"]
            for name in names:
                (artifacts / name).unlink(missing_ok=True)
            args = ("docker", "run", "--rm", "--network", network, "--ipc=host")
            args += ("-v", str(ROOT / "scripts/colonization_browser.mjs") + ":/browser/c.mjs:ro")
            args += ("-v", str(artifacts.resolve()) + ":/artifacts")
            for key, value in [
                ("UNIVERSE", universe),
                ("COLONY", created["colony_id"]),
                ("EMPIRE", created["empire_id"]),
                ("SYSTEM", created["system_id"]),
                ("EDGE_IP", ip),
            ]:
                args += ("-e", f"COLONIZATION_{key}={value}")
            args += ("echosphere-handoff-browser:dev", "node", "/browser/c.mjs")
            done = set()
            deadline = time.monotonic() + 600
            empire = created["empire_id"]
            with subprocess.Popen(
                args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as browser:
                while browser.poll() is None:
                    if time.monotonic() >= deadline:
                        browser.terminate()
                        raise RuntimeError("Colonization browser exceeded its deadline")
                    if (artifacts / "ordered").exists() and "ordered" not in done:
                        time.sleep(4)  # 2 s test build, completed by the worker alone
                        (artifacts / "produced").write_text("ready")
                        done.add("ordered")
                    if (artifacts / "launched").exists() and "launched" not in done:
                        # Founded by the worker from the package only: real planet capacities.
                        rows = wait(
                            lambda r: len(r) == 1, "worker founding", f"founded({empire!r})"
                        )
                        (row,) = rows
                        assert row["stocks"] == {
                            "alloys": 600 * M,
                            "flux": 300 * M,
                            "data": 100 * M,
                        }
                        assert row["rates"] == [0, 0, 0], row
                        (artifacts / "founded").write_text(json.dumps(row))
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
                        # Two Empires, one world, one frozen instant, then two racing workers.
                        run(*compose, "stop", "--timeout", "5", "worker", env=environment)
                        contest = json.loads(
                            game(
                                f"contest({universe!r}, {empire!r}, {created['colony_id']!r}, "
                                f"{created['system_id']!r})"
                            )
                        )
                        scale = ("up", "--no-build", "-d", "--scale", "worker=2", "worker")
                        run(*compose, *scale, env=environment)
                        call = f"outcome({contest['planet']!r}, {contest['missions']!r})"
                        result = wait(
                            lambda r: set(r["statuses"].values()) == {"completed"},
                            "two-worker contest resolution",
                            call,
                        )
                        assert len(result["owners"]) == 1, result
                        winner = min(result["ranks"], key=lambda e: result["ranks"][e])
                        loser = next(e for e in result["ranks"] if e != winner)
                        assert result["owners"] == [winner], result
                        assert result["reports"][winner]["outcome"] == "founded", result
                        assert result["reports"][loser] == {
                            "kind": "COLONIZE",
                            "destination_id": created["system_id"],
                            "planet_id": contest["planet"],
                            "outcome": "failed",
                            "reason": "target_unavailable",
                        }, result
                        assert result["fleets"][loser] == ["STATIONED", True], result
                        assert result["fleets"][winner] == ["SETTLED", False], result
                        print(
                            "Colonization: two Empires, equal due_at, two workers: exactly one "
                            "owner, the best persisted rank; loser stationed, Portal down",
                            flush=True,
                        )
                        (artifacts / "portal-stopped").write_text(
                            json.dumps({"mine": contest["missions"][empire], "winner": winner})
                        )
                        done.add("portal")
                    if (artifacts / "expire").exists() and "expire" not in done:
                        game(f"expire({universe!r})")
                        (artifacts / "expired").write_text("ready")
                        done.add("expire")
                    time.sleep(0.2)
                stdout, stderr = browser.communicate(timeout=10)
                if browser.returncode:
                    log = redacted(stdout + stderr)
                    Path("/tmp/echosphere-colonization-failure.log").write_text(log)
                    print(log[-12000:], flush=True)
                    raise RuntimeError("Colonization real browser scenario failed")
                assert done == {"ordered", "launched", "portal", "expire"}, done
                print(stdout)
        finally:
            if started:
                # This project and all its volumes were created by this recipe only (*_test).
                run(*compose, "down", "--volumes", "--remove-orphans", env=environment)
    print("Colonization smoke passed; owned project/volumes removed, retained stack preserved")


if __name__ == "__main__":
    main()
