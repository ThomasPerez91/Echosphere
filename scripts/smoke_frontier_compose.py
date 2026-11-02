"""Frontier recipe (13B, v0.9): one human and two AIs, the thirteen first-contact situations,
then a real worker interruption and resume. Owned Compose project, *_test databases only.

Requires the images of the current tree (`docker compose build`). Created then removed: this
project's containers and volumes only. The fixture (`frontier_game_fixture.py`) places test-only
Fleets/Knowledge/funds in the disposable Game DB, then every decision runs through the real code
on an injected clock (Fleet service, FrontierOrchestrator, CombatOrchestrator, AI Orchestrator);
the last entry is resolved by the real `worker` and `combat-worker` processes on the system
clock. The UI is covered by Vitest (Fleet.test.tsx) and Chromium (`npm run test:e2e`).

Status (02/11/2026): written in the cloud session, **never executed** (no Docker there).
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
GAME_DB = "echosphere_frontier_game_test"
ACCOUNTS_DB = "echosphere_frontier_accounts_test"


def check_scenarios(proof):
    sc = proof["scenarios"]
    assert proof["ruleset"] == "v0.9", proof
    # Passage in a watched system, anonymous mutual detection, no fight.
    assert sc["detection"]["detections"] == ["transit", "watch"], sc["detection"]
    assert sc["detection"]["identified"] == [False, False], sc["detection"]
    assert sc["detection"]["outcomes"] == [], sc["detection"]
    # Voluntary contact: both sides identified, durable 'frontier' contacts once read.
    assert sc["friendly"]["identified"] == [True, True], sc["friendly"]
    assert proof["frontier_contacts"] >= 2, proof
    # Ambush against a known enemy (real ATTACK by the human within 72 h, no pact).
    assert sc["ambush"]["outcomes"] == ["fought"], sc["ambush"]
    # Interception without power comparison: a weaker watcher still engages.
    assert sc["interception_weak"]["outcomes"] == ["fought"], sc["interception_weak"]
    # A pact (answered by the real AI policy) prevents the engagement; nothing lost.
    assert sc["pact"]["outcomes"] == ["pact"], sc["pact"]
    assert sc["pact"]["mover_units"] == {"interceptor": 1}, sc["pact"]
    # A purely civilian Fleet is never destroyed.
    assert sc["civilian"]["outcomes"] == ["no_military_target"], sc["civilian"]
    assert sc["civilian"]["mover_units"] == {"freighter": 1}, sc["civilian"]
    # A military Fleet destroyed in transit: mission ended, interception report.
    assert sc["destroyed"]["mover_status"] == "DESTROYED", sc["destroyed"]
    assert sc["destroyed"]["mission_status"] == "completed", sc["destroyed"]
    assert sc["destroyed"]["intercepted_report"], sc["destroyed"]
    # A mission continuing with its losses (survivors arrive).
    losses = sc["losses"]
    if losses["mover_status"] != "DESTROYED":
        assert losses["outcomes"] == ["fought"] and losses["mission_status"] == "completed", losses
        assert losses["mover_units"].get("frigate", 0) <= 3, losses
    # Friendly retreat: success towards the previous system; local 0-hop attack: impossible.
    assert proof["retreat"]["outcomes"] == ["retreated"], proof["retreat"]
    assert proof["retreat"]["destination_is_previous"], proof["retreat"]
    assert proof["local"]["passage"] == [["local", 0]], proof["local"]
    assert proof["local"]["at_launch"], proof["local"]
    assert proof["local"]["outcomes"] == ["retreat_impossible"], proof["local"]
    # B08: the AIs' own choices (never INTERCEPTION; cautious never AMBUSH).
    cautious, bold = proof["ai_postures"]["economic_cautious"], proof["ai_postures"]["expansionist"]
    assert "SURVEILLANCE" in cautious["protocols"], cautious
    assert set(cautious["protocols"]) <= {"SURVEILLANCE", "FRIENDLY_CONTACT"}, cautious
    assert "AMBUSH" in bold["protocols"], bold
    assert "INTERCEPTION" not in bold["protocols"], bold
    assert proof["open_entries"] == 0 and proof["open_fences"] == 0, proof


def main():
    project = f"echosphere-frontier-{uuid4().hex[:8]}"
    universe = str(uuid4())
    environment = {
        **os.environ,
        "POSTGRES_DB": GAME_DB,
        "POSTGRES_USER": "frontier_test",
        "POSTGRES_PASSWORD": "frontier_local_test_only",
        "PORTAL_POSTGRES_DB": ACCOUNTS_DB,
        "PORTAL_POSTGRES_USER": "frontier_accounts_test",
        "PORTAL_POSTGRES_PASSWORD": "frontier_accounts_local_test_only",
    }
    portal_fixture = (
        PORTAL_FIXTURE.replace("echosphere_galaxy_accounts_test", ACCOUNTS_DB)
        .replace("galaxy@example.org", "frontier@example.org")
        .replace("Univers de recette Galaxie", "Univers de recette Frontiere")
    )
    portal_access = PORTAL_ACCESS.replace("echosphere_galaxy_accounts_test", ACCOUNTS_DB).replace(
        "['colony.read','galaxy.read','exploration.read','exploration.start']", RIGHTS
    )
    assert RIGHTS in portal_access, "Frontier rights must reach the binding"
    fixture = (ROOT / "scripts/frontier_game_fixture.py").read_text()
    folder = tempfile.TemporaryDirectory(prefix="echosphere-frontier-")
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
            *compose, "exec", "-T", "portal-backend", "python", "-", env=environment, input=source
        )

    def module(name, *args):
        command = ("exec", "-T", "backend", "python", "-m", name, *args)
        return json.loads(run(*compose, *command, env=environment).splitlines()[-1])

    started = False
    try:
        print("Frontier recipe: starting isolated project", flush=True)
        started = True
        run(*compose, "up", "--no-build", "-d", "--wait", "--wait-timeout", "180", env=environment)
        user = portal(portal_fixture.replace("__UNIVERSE__", universe)).splitlines()[-1]
        provisioned = game(f"provisioned({universe!r})")
        # The injected recipe clock drives time first: no system-clock worker meanwhile.
        run(*compose, "stop", "--timeout", "5", "worker", "combat-worker", env=environment)
        at = (datetime.now(UTC) - timedelta(hours=96)).isoformat()
        created = module(
            "app.ai.worker",
            "--bootstrap",
            universe,
            "--name",
            provisioned["name"],
            "--seed",
            provisioned["seed"],
            "--profiles",
            "economic_cautious,expansionist",
            "--ruleset",
            "v0.9",
            "--at",
            at,
        )
        human, cautious, bold = created["actors"]
        assert human["controller_id"] is None
        assert (cautious["profile"], bold["profile"]) == ("economic_cautious", "expansionist")
        portal(
            portal_access.replace("__USER__", user)
            .replace("__UNIVERSE__", universe)
            .replace("__EMPIRE__", human["empire_id"])
        )
        print("Frontier recipe: v0.9 bootstrap, one human and two AIs", flush=True)
        staged = game(f"setup({universe!r})")
        assert {"detection", "friendly", "retreat", "local", "ai_postures"} <= set(
            staged["staged"]
        ), staged
        check_scenarios(game(f"proof({universe!r})"))
        print(
            "Frontier recipe: detection, introduction, ambush, interception, pact, civilian, "
            "destroyed, losses, retreat, local attack and AI postures verified",
            flush=True,
        )
        # Worker interruption and resume on the system clock.
        resume = game(f"resume_stage({universe!r})")
        while not resume["due_in_past"] and datetime.fromisoformat(
            resume["entered_at"]
        ) > datetime.now(UTC):
            time.sleep(5)
        run(*compose, "up", "--no-build", "-d", "worker", env=environment)  # combat-worker off
        time.sleep(15)
        frozen = game(f"resume_state({universe!r}, {resume['mission_id']!r})")
        assert frozen["entry_state"] == "pending" and not frozen["arrived"], frozen
        lag = module("app.combat.worker", "--lag")
        assert lag["alert"] and lag["oldest_entry_at"] is not None, lag
        print("Frontier recipe: combat-worker down -> entry pending, mover frozen, lag alert")
        run(*compose, "up", "--no-build", "-d", "combat-worker", env=environment)
        deadline = time.monotonic() + 240
        while True:
            state = game(f"resume_state({universe!r}, {resume['mission_id']!r})")
            if state["entry_state"] == "resolved" and state["arrived"]:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Frontier recipe: resume not reached: {state}")
            time.sleep(2)
        assert state["detections"] == 2, state  # the stationed SURVEILLANCE watcher, both sides
        assert module("app.combat.worker", "--blocked") == [], "nothing left blocked"
        print("Frontier recipe: combat-worker resumed -> entry resolved, then arrival processed")
    finally:
        if started:
            # This project and all its volumes were created by this recipe only (*_test).
            down = ("--profile", "ai", "down", "--volumes", "--remove-orphans")
            run(*compose, *down, env=environment)
        folder.cleanup()
    print("Frontier smoke passed; owned project/volumes removed, retained stack preserved")


if __name__ == "__main__":
    main()
