"""Fleet loop, GET non-mutation and Portal outage in an owned disposable Compose project.

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

RIGHTS = "['colony.read','galaxy.read','fleet.read','fleet.build','fleet.command']"
M = 1_000_000


def main():
    project = f"echosphere-fleet-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_fleet_game_test",
        "POSTGRES_USER": "fleet_test",
        "POSTGRES_PASSWORD": "fleet_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_fleet_accounts_test",
        "PORTAL_POSTGRES_USER": "fleet_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "fleet_accounts_local_test_only",
    }
    portal_fixture = (
        PORTAL_FIXTURE.replace("echosphere_galaxy_accounts_test", "echosphere_fleet_accounts_test")
        .replace("galaxy@example.org", "fleet@example.org")
        .replace("Univers de recette Galaxie", "Univers de recette Flottes")
    )
    portal_access = PORTAL_ACCESS.replace(
        "echosphere_galaxy_accounts_test", "echosphere_fleet_accounts_test"
    ).replace("['colony.read','galaxy.read','exploration.read','exploration.start']", RIGHTS)
    assert RIGHTS in portal_access, "Fleet rights must reach the binding"
    fixture = (ROOT / "scripts/fleet_game_fixture.py").read_text()
    with tempfile.TemporaryDirectory(prefix="echosphere-fleet-") as folder:
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

        def state():
            return json.loads(game(f"state({created['empire_id']!r})"))

        def wait(check, label, timeout=150):
            for _ in range(timeout):
                current = state()
                if check(current):
                    return current
                time.sleep(1)
            raise RuntimeError(f"Fleet recipe: {label} not reached: {current}")

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
            print("Fleet recipe: starting isolated project", flush=True)
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
            user = portal(portal_fixture.replace("__UNIVERSE__", universe)).splitlines()[-1]
            created = json.loads(game(f"setup({universe!r})"))
            portal(
                portal_access.replace("__USER__", user)
                .replace("__UNIVERSE__", universe)
                .replace("__EMPIRE__", created["empire_id"])
            )
            print(
                "Fleet recipe: test-only account, v0.4 universe, colony and Fleet rights",
                flush=True,
            )
            edge = json.loads(
                run("docker", "inspect", run(*compose, "ps", "-q", "local-edge", env=environment))
            )[0]
            network = project + "_default"
            ip = edge["NetworkSettings"]["Networks"][network]["IPAddress"]
            artifacts = Path(os.environ.get("FLEET_ARTIFACTS", "/tmp/echosphere-fleet-artifacts"))
            artifacts.mkdir(parents=True, exist_ok=True)
            names = [
                "ordered",
                "produced",
                "stop-worker",
                "worker-stopped",
                "orders-cancelled",
                "orders-checked",
                "gets-checked",
                "surveyed",
                "second-colony",
                "colony-ready",
                "portal-stop",
                "portal-stopped",
                "expire",
                "expired",
                "summary",
                "expiry-checked",
                "expiry-completed",
            ]
            for name in names:
                (artifacts / name).unlink(missing_ok=True)
            args = ("docker", "run", "--rm", "--network", network, "--ipc=host")
            args += ("-v", str(ROOT / "scripts/fleet_browser.mjs") + ":/browser/fleet.mjs:ro")
            args += ("-v", str(artifacts.resolve()) + ":/artifacts")
            for key, value in [
                ("UNIVERSE", universe),
                ("COLONY", created["colony_id"]),
                ("EMPIRE", created["empire_id"]),
                ("EDGE_IP", ip),
            ]:
                args += ("-e", f"FLEET_{key}={value}")
            args += ("echosphere-handoff-browser:dev", "node", "/browser/fleet.mjs")
            done = set()
            deadline = time.monotonic() + 600
            with subprocess.Popen(
                args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as browser:
                while browser.poll() is None:
                    if time.monotonic() >= deadline:
                        browser.terminate()
                        raise RuntimeError("Fleet browser coordination exceeded its deadline")
                    if (artifacts / "ordered").exists() and "ordered" not in done:
                        # Page closed; the restarted worker alone builds both batches.
                        run(*compose, "restart", "--timeout", "5", "worker", env=environment)
                        wait(
                            lambda s: any(
                                f["kind"] == "GARRISON"
                                and f["stacks"] == {"freighter": 1, "probe": 1}
                                for f in s["fleets"]
                            ),
                            "offline production in the garrison",
                        )
                        (artifacts / "produced").write_text("ready")
                        done.add("ordered")
                    if (artifacts / "stop-worker").exists() and "stop" not in done:
                        run(*compose, "stop", "--timeout", "5", "worker", env=environment)
                        (artifacts / "worker-stopped").write_text("ready")
                        done.add("stop")
                    if (artifacts / "orders-cancelled").exists() and "orders" not in done:
                        ids = json.loads((artifacts / "orders-cancelled").read_text())
                        queued = json.loads(game(f"order({ids['queued']!r})"))
                        active = json.loads(game(f"order({ids['active']!r})"))
                        # Cancelled once in DB: 100 % queued, 80 % active, event acknowledged.
                        assert queued == {
                            "status": "cancelled",
                            "refunded": {"alloys": 80 * M, "data": 40 * M, "flux": 40 * M},
                            "event": None,
                        }, queued
                        assert active == {
                            "status": "cancelled",
                            "refunded": {"alloys": 640 * M, "data": 320 * M, "flux": 320 * M},
                            "event": ["completed", "cancelled"],
                        }, active
                        (artifacts / "orders-checked").write_text("ready")
                        done.add("orders")
                    if (artifacts / "gets-checked").exists() and "gets" not in done:
                        mission = (artifacts / "gets-checked").read_text().strip()
                        # Past due after several GETs: still active, its event still pending.
                        row = next(m for m in state()["missions"] if m["id"] == mission)
                        assert row["status"] == "active" and row["destination_state"] == "DETECTED"
                        assert row["events"] == [["FLEET_ARRIVAL", "pending", None]], row
                        run(*compose, "start", "worker", env=environment)
                        wait(
                            lambda s, mission=mission: any(
                                m["id"] == mission
                                and m["status"] == "completed"
                                and m["destination_state"] == "MAPPED"
                                and m["report"]
                                and m["events"] == [["FLEET_ARRIVAL", "completed", None]]
                                for m in s["missions"]
                            ),
                            "worker-only SURVEY mapping",
                        )
                        (artifacts / "surveyed").write_text("ready")
                        done.add("gets")
                    if (artifacts / "second-colony").exists() and "colony" not in done:
                        system = (artifacts / "second-colony").read_text().strip()
                        second = json.loads(
                            game(
                                f"second_colony({universe!r}, {created['empire_id']!r}, {system!r})"
                            )
                        )
                        (artifacts / "colony-ready").write_text(second["colony_id"])
                        done.add("colony")
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
                    if (artifacts / "expiry-checked").exists() and "expiry" not in done:
                        summary = json.loads((artifacts / "summary").read_text())
                        # Accepted before expiry: the RETURN still completes afterwards.
                        final = wait(
                            lambda s, summary=summary: any(
                                m["id"] == summary["last"] and m["status"] == "completed"
                                for m in s["missions"]
                            ),
                            "RETURN after session expiry",
                        )
                        recall = next(m for m in final["missions"] if m["id"] == summary["recall"])
                        assert recall["events"] == [
                            ["FLEET_ARRIVAL", "completed", "cancelled"],
                            ["FLEET_RETURN", "completed", None],
                        ], recall
                        freighter = next(
                            f for f in final["fleets"] if f["id"] == summary["freighter"]
                        )
                        assert freighter["cargo"] == {"alloys": 200_000_000}, freighter
                        stock = json.loads(game(f"stock({summary['second']!r}, 'alloys')"))
                        assert stock["stock"] == 10_000_000_000, stock
                        (artifacts / "expiry-completed").write_text("ready")
                        done.add("expiry")
                    time.sleep(0.2)
                stdout, stderr = browser.communicate(timeout=10)
                if browser.returncode:
                    Path("/tmp/echosphere-fleet-failure.log").write_text(redacted(stdout + stderr))
                    print(redacted(stdout + stderr)[-12000:], flush=True)
                    raise RuntimeError("Fleet real browser scenario failed")
                expected = {
                    "ordered",
                    "stop",
                    "orders",
                    "gets",
                    "colony",
                    "portal",
                    "expire",
                    "expiry",
                }
                assert done == expected, done
                print(stdout)
        finally:
            if started:
                # This project and all its volumes were created by this recipe only (*_test, no port).
                run(*compose, "down", "--volumes", "--remove-orphans", env=environment)
    print("Fleet smoke passed; owned temporary project/volumes removed, retained stack preserved")


if __name__ == "__main__":
    main()
