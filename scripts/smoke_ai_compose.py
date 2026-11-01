"""First AI recipe: v0.6 operator bootstrap, human + 2 AI, autonomous play, owned Compose project.

Requires the images of the current tree (`docker compose build` or the CI `up --build` step).
Only *_test databases and this project's own volumes are created, then removed.
After the operator bootstrap nothing is credited, placed or revealed: the long horizon is driven
by an injected test clock through the real TimeEngine/Orchestrator, then the real worker and two
ai-worker processes take over on the system clock with Portal stopped and the human page closed.
"""

import json
import os
import subprocess
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from smoke_galaxy_compose import PORTAL_ACCESS, PORTAL_FIXTURE
from smoke_handoff_compose import ROOT, redacted, run

RIGHTS = "['colony.read','galaxy.read','fleet.read']"
M = 1_000_000
PRODUCERS = ["extraction_complex", "flux_reactor", "data_node"]


def main():
    project = f"echosphere-ai-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_ai_game_test",
        "POSTGRES_USER": "ai_test",
        "POSTGRES_PASSWORD": "ai_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_ai_accounts_test",
        "PORTAL_POSTGRES_USER": "ai_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "ai_accounts_local_test_only",
    }
    rules = json.loads((ROOT / "game_data/rulesets/v0.6/colonization.json").read_text())
    package = {r: v * M for r, v in rules["minimum_package"].items()}
    portal_fixture = (
        PORTAL_FIXTURE.replace("echosphere_galaxy_accounts_test", "echosphere_ai_accounts_test")
        .replace("galaxy@example.org", "ai@example.org")
        .replace("Univers de recette Galaxie", "Univers de recette IA")
    )
    portal_access = PORTAL_ACCESS.replace(
        "echosphere_galaxy_accounts_test", "echosphere_ai_accounts_test"
    ).replace("['colony.read','galaxy.read','exploration.read','exploration.start']", RIGHTS)
    assert RIGHTS in portal_access, "Human rights must reach the binding"
    fixture = (ROOT / "scripts/ai_game_fixture.py").read_text()
    with tempfile.TemporaryDirectory(prefix="echosphere-ai-") as folder:
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
            return json.loads(
                run(
                    *compose,
                    "exec",
                    "-T",
                    "backend",
                    "python",
                    "-",
                    env=environment,
                    input=fixture + "\n" + call + "\n",
                ).splitlines()[-1]
            )

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

        def operator(*args):
            # The real operator CLI of the Game image, never a recipe import.
            command = ("exec", "-T", "backend", "python", "-m", "app.ai.worker", *args)
            return json.loads(run(*compose, *command, env=environment).splitlines()[-1])

        def controllers(state):
            return {a["profile"]: a["controller"] for a in state["actors"] if a["profile"]}

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
            print("AI recipe: starting isolated project", flush=True)
            started = True
            up = ("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
            run(*compose, *up, env=environment)
            user = portal(portal_fixture.replace("__UNIVERSE__", universe)).splitlines()[-1]
            provisioned = game(f"provisioned({universe!r})")
            # The injected recipe clock drives time below: no system-clock worker meanwhile.
            run(*compose, "stop", "--timeout", "5", "worker", env=environment)
            at = (datetime.now(UTC) - timedelta(hours=72)).isoformat()
            bootstrap = ("--bootstrap", universe, "--name", provisioned["name"])
            bootstrap += ("--seed", provisioned["seed"], "--at", at)
            created = operator(*bootstrap)
            assert operator(*bootstrap) == created, "Bootstrap replay must return the same start"
            human, *ais = created["actors"]
            assert human["profile"] is None and human["controller_id"] is None, created
            assert [a["profile"] for a in ais] == ["economic_cautious", "expansionist"], created
            starts = game(f"starts({universe!r})")
            assert [s["controller_type"] for s in starts] == ["human", "ai", "ai"], starts
            assert len({json.dumps([s["balances"], s["buildings"]]) for s in starts}) == 1, starts
            assert all(s["fleets"] == 0 for s in starts), starts
            print("AI recipe: v0.6 operator bootstrap, human + 2 AI, equal starts", flush=True)
            portal(
                portal_access.replace("__USER__", user)
                .replace("__UNIVERSE__", universe)
                .replace("__EMPIRE__", human["empire_id"])
            )
            edge = json.loads(
                run("docker", "inspect", run(*compose, "ps", "-q", "local-edge", env=environment))
            )[0]
            network = project + "_default"
            ip = edge["NetworkSettings"]["Networks"][network]["IPAddress"]
            artifacts = Path(os.environ.get("AI_ARTIFACTS", "/tmp/echosphere-ai-artifacts"))
            artifacts.mkdir(parents=True, exist_ok=True)
            for name in ["entered", "reopen", "reopened", "expired"]:
                (artifacts / name).unlink(missing_ok=True)
            args = ("docker", "run", "--rm", "--network", network, "--ipc=host")
            args += ("-v", str(ROOT / "scripts/ai_browser.mjs") + ":/browser/ai.mjs:ro")
            args += ("-v", str(artifacts.resolve()) + ":/artifacts")
            for key, value in [
                ("UNIVERSE", universe),
                ("COLONY", human["colony_id"]),
                ("PLANET", starts[0]["planet"]),
                ("EDGE_IP", ip),
            ]:
                args += ("-e", f"AI_{key}={value}")
            args += ("echosphere-handoff-browser:dev", "node", "/browser/ai.mjs")

            def until(name, browser, timeout=300):
                deadline = time.monotonic() + timeout
                while not (artifacts / name).exists():
                    if browser.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(f"AI recipe: browser marker {name} not reached")
                    time.sleep(0.2)

            with subprocess.Popen(
                args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as browser:
                try:
                    until("entered", browser)
                    run(
                        *compose,
                        "stop",
                        "--timeout",
                        "3",
                        "portal-backend",
                        "portal-control-worker",
                        env=environment,
                    )
                    print("AI recipe: human page closed, Portal stopped", flush=True)
                    driven = game(f"drive({universe!r}, 72)")
                    assert set(driven["reached"]) == {"economic_cautious", "expansionist"}, driven
                    before = game(f"proof({universe!r})")
                    for actor in before["actors"]:
                        progress = actor["progress"]
                        if actor["profile"] is None:
                            # The human did nothing: no AI ever acts on its Empire.
                            assert progress["builds"] == 0 and actor["keys"] == [], actor
                            continue
                        assert actor["keys"] == ["ai"], actor
                        assert {"probe", "colonizer"} <= set(progress["ships"]), actor
                        assert progress["surveys"] and progress["acquired"], actor
                        assert progress["research_orders"] and progress["colonizations"], actor
                        first = progress["founded"][0]
                        assert first["cargo"] == package, actor
                        assert first["first_builds"] == PRODUCERS and first["built"] >= 3, actor
                    assert all(
                        any(rate > 0 for rate in rates.values())
                        for rates in before["balances_of_founded"]
                    ), before
                    assert before["principals"] == 1, before
                    assert before["bound_empires"] == [human["empire_id"]], before
                    print(
                        "AI recipe: "
                        + "; ".join(
                            f"{a['profile']}: {a['progress']['builds']} builds, "
                            f"{a['progress']['research_orders']} research, "
                            f"{a['progress']['surveys']} SURVEY, "
                            f"{len(a['progress']['founded'])} founded"
                            for a in before["actors"]
                            if a["profile"]
                        )
                        + f" in {driven['turns']} common-service turns",
                        flush=True,
                    )
                    # Real processes on the system clock: one coalesced turn per controller.
                    real = datetime.now(UTC)
                    ai = ("--profile", "ai", "up", "--no-build", "-d", "--scale", "ai-worker=2")
                    run(*compose, *ai, "worker", "ai-worker", env=environment)
                    old = controllers(before)
                    for _ in range(120):
                        state = game(f"proof({universe!r})")
                        now = controllers(state)
                        if all(now[p]["sequence"] > old[p]["sequence"] for p in old):
                            break
                        time.sleep(1)
                    else:
                        raise RuntimeError(f"AI recipe: no real ai-worker turn: {state}")
                    for profile, row in now.items():
                        assert row["sequence"] == old[profile]["sequence"] + 1, (profile, row)
                        assert row["state"] == "enabled", row
                        observed = datetime.fromisoformat(row["last_observed_at"])
                        following = datetime.fromisoformat(row["next_decision_at"])
                        assert row["last_planned_at"] == old[profile]["next_decision_at"], row
                        assert observed >= real and observed < following, row
                        assert following - observed <= timedelta(seconds=600), row
                    print(
                        "AI recipe: two ai-worker processes, Portal down: exactly one coalesced "
                        "turn per controller, next slot on the future 600 s grid",
                        flush=True,
                    )
                    run(*compose, "--profile", "ai", "restart", "ai-worker", env=environment)
                    time.sleep(12)
                    state = game(f"proof({universe!r})")
                    checked = datetime.fromisoformat(state["now"])
                    for profile, row in controllers(state).items():
                        if checked < datetime.fromisoformat(now[profile]["next_decision_at"]):
                            assert row["sequence"] == now[profile]["sequence"], (profile, row)
                    print("AI recipe: ai-worker restart, no duplicate turn", flush=True)
                    (artifacts / "reopen").write_text("ready")
                    until("reopened", browser)
                    game(f"expire({universe!r})")
                    (artifacts / "expired").write_text("ready")
                    stdout, stderr = browser.communicate(timeout=120)
                except BaseException:
                    browser.kill()
                    raise
                if browser.returncode:
                    log = redacted(stdout + stderr)
                    Path("/tmp/echosphere-ai-failure.log").write_text(log)
                    print(log[-12000:], flush=True)
                    raise RuntimeError("AI recipe real browser scenario failed")
                print(stdout)
        finally:
            if started:
                # This project and all its volumes were created by this recipe only (*_test).
                down = ("--profile", "ai", "down", "--volumes", "--remove-orphans")
                run(*compose, *down, env=environment)
    print("AI smoke passed; owned project/volumes removed, retained stack preserved")


if __name__ == "__main__":
    main()
