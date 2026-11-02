"""Relations recipe (step 13, v0.8): human + AI, real battles by the combat-worker, contacts
and dated hostility, a human pact proposal answered by the real ai-worker. Owned Compose project.

Requires the images of the current tree (`docker compose build` or the CI `up --build` step).
Only *_test databases and this project's own volumes are created, then removed. After the
operator bootstrap nothing is credited, placed or revealed: the Combat fixture's injected clock
plays the human through the Fleet service; battles, contacts and the AI answer then come from
real worker processes with Portal stopped. The UI is covered by Vitest (Relations.test.tsx).
"""

import json
import os
import tempfile
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from smoke_galaxy_compose import PORTAL_ACCESS, PORTAL_FIXTURE
from smoke_handoff_compose import ROOT, run

OVERRIDE = """services:
  backend:
    ports: !reset []
  frontend:
    image: echosphere-frontend:latest
    ports: !reset []
  portal-frontend:
    image: echosphere-portal-frontend:latest
  local-edge:
    ports: !reset []
"""

RIGHTS = (
    "['colony.read','galaxy.read','fleet.read','fleet.build','fleet.command',"
    "'combat.read','combat.attack','relations.read','relations.negotiate']"
)
GAME_DB = "echosphere_relations_game_test"
ACCOUNTS_DB = "echosphere_relations_accounts_test"


def main():
    project = f"echosphere-relations-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": GAME_DB,
        "POSTGRES_USER": "relations_test",
        "POSTGRES_PASSWORD": "relations_local_test_only",
        "PORTAL_POSTGRES_DB": ACCOUNTS_DB,
        "PORTAL_POSTGRES_USER": "relations_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "relations_accounts_local_test_only",
    }
    portal_fixture = (
        PORTAL_FIXTURE.replace("echosphere_galaxy_accounts_test", ACCOUNTS_DB)
        .replace("galaxy@example.org", "relations@example.org")
        .replace("Univers de recette Galaxie", "Univers de recette Relations")
    )
    portal_access = PORTAL_ACCESS.replace("echosphere_galaxy_accounts_test", ACCOUNTS_DB).replace(
        "['colony.read','galaxy.read','exploration.read','exploration.start']", RIGHTS
    )
    assert RIGHTS in portal_access, "Relations rights must reach the binding"
    combat_fixture = (ROOT / "scripts/combat_game_fixture.py").read_text()
    assert 'DATABASE = "echosphere_combat_game_test"' in combat_fixture
    fixture = (
        combat_fixture.replace(
            'DATABASE = "echosphere_combat_game_test"', f'DATABASE = "{GAME_DB}"'
        )
        + "\n"
        + (ROOT / "scripts/relations_game_fixture.py").read_text()
    )
    folder = tempfile.TemporaryDirectory(prefix="echosphere-relations-")
    override = os.path.join(folder.name, "compose.yml")
    with open(override, "w") as handle:
        handle.write(OVERRIDE)
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

    def wait(call, done, label, timeout=240):
        deadline = time.monotonic() + timeout
        while True:
            state = game(call)
            if done(state):
                return state
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Relations recipe: {label} not reached: {state}")
            time.sleep(2)

    started = False
    try:
        print("Relations recipe: starting isolated project", flush=True)
        started = True
        run(*compose, "up", "--no-build", "-d", "--wait", "--wait-timeout", "180", env=environment)
        user = portal(portal_fixture.replace("__UNIVERSE__", universe)).splitlines()[-1]
        provisioned = game(f"provisioned({universe!r})")
        # The injected recipe clock drives time first: no system-clock worker meanwhile.
        stop = ("stop", "--timeout", "5", "worker", "combat-worker")
        run(*compose, *stop, env=environment)
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
            "v0.8",
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
        driven = game(f"drive({universe!r}, 96)")
        assert driven["launched"], driven
        print("Relations recipe: v0.8 bootstrap, human ATTACKs launched on the AI", flush=True)
        # Portal down: Relations, like Combat, never depend on it.
        portal_down = ("stop", "--timeout", "3", "portal-backend", "portal-control-worker")
        run(*compose, *portal_down, env=environment)
        up = ("up", "--no-build", "-d", "worker", "combat-worker")
        run(*compose, *up, env=environment)
        proof = wait(
            f"contacts_proof({universe!r})",
            lambda p: p["contacts"] == 2 and p["human_hostile_is_last_battle"],
            "combat contacts",
        )
        assert proof["ruleset"] == "v0.8" and proof["mutual"], proof
        assert set(proof["sources"]) <= {"combat", "presence"}, proof
        assert not proof["ai_hostile"], proof
        assert proof["state_pacts"] == 0 and proof["ai_attacks"] == 0, proof
        print(
            "Relations recipe: real battles -> both oriented contacts, attacker's dated "
            "hostile fact, no state change",
            flush=True,
        )
        receipt = game(f"propose({universe!r})")
        assert receipt["kind"] == "proposed", receipt
        run(*compose, "--profile", "ai", "up", "--no-build", "-d", "ai-worker", env=environment)
        # One AI turn per 10 min; a survival (bootstrap) or defence priority may come first.
        answer = wait(f"answer({universe!r})", lambda a: a["answered"], "AI answer", timeout=1500)
        assert answer["kind"] == answer["expected"], answer  # 72 h grievance rule, exactly
        assert answer["trace_action"] == {"accepted": "accept", "refused": "refuse"}[answer["kind"]]
        assert answer["proposal_cleared"], answer
        assert answer["pacts"] == (1 if answer["kind"] == "accepted" else 0), answer
        assert answer["human_cooldown"] == (answer["kind"] == "refused"), answer
        assert answer["principals"] == 1, answer  # no account, session or identity for the AI
        print(
            f"Relations recipe: real ai-worker answered {answer['kind']} per its grievance "
            "rule; no AI attack, no AI identity",
            flush=True,
        )
    finally:
        if started:
            # This project and all its volumes were created by this recipe only (*_test).
            down = ("--profile", "ai", "down", "--volumes", "--remove-orphans")
            run(*compose, *down, env=environment)
        folder.cleanup()
    print("Relations smoke passed; owned project/volumes removed, retained stack preserved")


if __name__ == "__main__":
    main()
