"""Combat MVP recipe: v0.7 human + AI, real ATTACK, defender warning and reaction, two
combat-worker processes, deterministic ordering, reports, return. Owned Compose project.

Requires the images of the current tree (`docker compose build` or the CI `up --build` step).
Only *_test databases and this project's own volumes are created, then removed.
After the operator bootstrap nothing is credited, placed or revealed: an injected test clock
drives the real TimeEngine and AI Orchestrator and plays the human through the Fleet service;
the battles are then resolved by two real combat-worker processes with Portal stopped.
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

RIGHTS = (
    "['colony.read','galaxy.read','fleet.read','fleet.build','fleet.command',"
    "'combat.read','combat.attack']"
)


def main():
    project = f"echosphere-combat-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": "echosphere_combat_game_test",
        "POSTGRES_USER": "combat_test",
        "POSTGRES_PASSWORD": "combat_local_test_only",
        "PORTAL_POSTGRES_DB": "echosphere_combat_accounts_test",
        "PORTAL_POSTGRES_USER": "combat_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "combat_accounts_local_test_only",
    }
    portal_fixture = (
        PORTAL_FIXTURE.replace("echosphere_galaxy_accounts_test", "echosphere_combat_accounts_test")
        .replace("galaxy@example.org", "combat@example.org")
        .replace("Univers de recette Galaxie", "Univers de recette Combat")
    )
    portal_access = PORTAL_ACCESS.replace(
        "echosphere_galaxy_accounts_test", "echosphere_combat_accounts_test"
    ).replace("['colony.read','galaxy.read','exploration.read','exploration.start']", RIGHTS)
    assert RIGHTS in portal_access, "Combat rights must reach the binding"
    fixture = (ROOT / "scripts/combat_game_fixture.py").read_text()
    with tempfile.TemporaryDirectory(prefix="echosphere-combat-") as folder:
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
            command = ("exec", "-T", "backend", "python", "-m", "app.ai.worker", *args)
            return json.loads(run(*compose, *command, env=environment).splitlines()[-1])

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
            print("Combat recipe: starting isolated project", flush=True)
            started = True
            up = ("up", "--no-build", "-d", "--wait", "--wait-timeout", "180")
            run(*compose, *up, env=environment)
            user = portal(portal_fixture.replace("__UNIVERSE__", universe)).splitlines()[-1]
            provisioned = game(f"provisioned({universe!r})")
            # The injected recipe clock drives time first: no system-clock worker meanwhile.
            run(
                *compose,
                "stop",
                "--timeout",
                "5",
                "worker",
                "combat-worker",
                env=environment,
            )
            at = (datetime.now(UTC) - timedelta(hours=96)).isoformat()
            created = operator(
                "--bootstrap",
                universe,
                "--name",
                provisioned["name"],
                "--seed",
                provisioned["seed"],
                "--profiles",
                "economic_cautious",
                "--ruleset",
                "v0.7",
                "--at",
                at,
            )
            human, ai = created["actors"]
            assert human["controller_id"] is None and ai["profile"] == "economic_cautious"
            portal(
                portal_access.replace("__USER__", user)
                .replace("__UNIVERSE__", universe)
                .replace("__EMPIRE__", human["empire_id"])
            )
            print("Combat recipe: v0.7 operator bootstrap, human + AI, human rights", flush=True)
            # Human commands run on the backdated test clock first; the human's real-clock
            # visit comes after, so no stream is ever asked to move backwards.
            driven = game(f"drive({universe!r}, 96)")
            assert driven["launched"], driven
            before = game(f"proof({universe!r})")
            pending = before["engagements"]
            assert [e["state"] for e in pending] == ["pending", "pending"], before
            assert all(e["defender_bound"] for e in pending), before
            assert pending[0]["battle_at"] == pending[1]["battle_at"], before
            assert pending[0]["started_at"] == pending[1]["started_at"], before
            # The defender is warned with target and instant only, then reacts itself.
            assert before["ai_alerts"] and all(
                set(a) == {"planet_id", "battle_at", "state"} for a in before["ai_alerts"]
            ), before
            # Reaction: an alerted, under-defended AI orders interceptors (target 3 per colony).
            assert (
                before["ai_interceptor_orders_after_alert"] >= 1
                or before["ai_interceptors_held_before_alert"] >= 3
            ), before
            assert before["ai_attacks"] == 0 and before["open_fences"] == 4, before
            frozen = game(f"colony_snapshot({universe!r})")
            print(
                f"Combat recipe: SURVEY over {driven['route_hops']} hop(s), two ATTACKs "
                "launched at one instant, defender warned and producing interceptors; "
                "battles due, streams fenced",
                flush=True,
            )
            edge = json.loads(
                run("docker", "inspect", run(*compose, "ps", "-q", "local-edge", env=environment))
            )[0]
            network = project + "_default"
            ip = edge["NetworkSettings"]["Networks"][network]["IPAddress"]
            artifacts = Path(os.environ.get("COMBAT_ARTIFACTS", "/tmp/echosphere-combat-artifacts"))
            artifacts.mkdir(parents=True, exist_ok=True)
            for name in ["entered", "reopen", "reopened", "expired", "combat-reports.png"]:
                (artifacts / name).unlink(missing_ok=True)
            args = ("docker", "run", "--rm", "--network", network, "--ipc=host")
            args += ("-v", str(ROOT / "scripts/combat_browser.mjs") + ":/browser/c.mjs:ro")
            args += ("-v", str(artifacts.resolve()) + ":/artifacts")
            for key, value in [
                ("UNIVERSE", universe),
                ("EMPIRE", human["empire_id"]),
                ("EDGE_IP", ip),
            ]:
                args += ("-e", f"COMBAT_{key}={value}")
            args += ("echosphere-handoff-browser:dev", "node", "/browser/c.mjs")

            def until(name, browser, timeout=600):
                deadline = time.monotonic() + timeout
                while not (artifacts / name).exists():
                    if browser.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(f"Combat recipe: browser marker {name} not reached")
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
                    print("Combat recipe: human page closed, Portal stopped", flush=True)
                    run(
                        *compose,
                        "up",
                        "--no-build",
                        "-d",
                        "--scale",
                        "combat-worker=2",
                        "worker",
                        "combat-worker",
                        env=environment,
                    )
                    for _ in range(180):
                        state = game(f"proof({universe!r})")
                        rows = state["engagements"]
                        if all(e["state"] == "resolved" for e in rows) and all(
                            e["mission_status"] == "completed" for e in rows
                        ):
                            break
                        time.sleep(1)
                    else:
                        raise RuntimeError(f"Combat recipe: battles not resolved: {state}")
                    first, second = rows
                    # Rank order (battle_at, started_at, id): the better one fought first, on
                    # the full defence; the second one met the survivors only.
                    assert first["processed_at"] <= second["processed_at"], state
                    left = {
                        c: first["defender_force"][c] - first["defender_losses"][c]
                        for c in first["defender_force"]
                    }
                    assert second["defender_force"] == left, state
                    for row in rows:
                        assert row["reports"] == ["attacker", "defender"], row
                        assert row["replay_exact"] is True, row
                        assert row["fleet_status"] in {"STATIONED", "DESTROYED"}, row
                        if row["fleet_status"] == "STATIONED":
                            assert row["fleet_system_is_origin"], row  # returned, never stays
                    assert state["open_fences"] == 0, state
                    assert game(f"colony_snapshot({universe!r})") == frozen  # no Colony write
                    assert state["principals"] == 1, state
                    assert state["bound_empires"] == [human["empire_id"]], state
                    print(
                        "Combat recipe: two combat-worker processes, Portal down: "
                        + "; ".join(f"{r['outcome']}" for r in rows)
                        + " in rank order, no duplicate losses, exact replay, returns done",
                        flush=True,
                    )
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
                    Path("/tmp/echosphere-combat-failure.log").write_text(log)
                    print(log[-12000:], flush=True)
                    raise RuntimeError("Combat recipe real browser scenario failed")
                print(stdout)
        finally:
            if started:
                # This project and all its volumes were created by this recipe only (*_test).
                down = ("--profile", "ai", "down", "--volumes", "--remove-orphans")
                run(*compose, *down, env=environment)
    print("Combat smoke passed; owned project/volumes removed, retained stack preserved")


if __name__ == "__main__":
    main()
