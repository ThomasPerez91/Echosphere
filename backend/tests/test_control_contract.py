import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.control.contracts import PERMISSIONS, Binding, Operation


def test_versioned_shared_schema_matches_the_game_admission_contract():
    source = Path(__file__).resolve().parents[2] / "contracts/portal-game/v1.schema.json"
    assert json.loads(source.read_text()) == Operation.model_json_schema()


def test_seventeen_rights_accepted_eighteenth_refused():
    empire = "00000000-0000-4000-8000-000000000001"
    assert len(PERMISSIONS) == 17
    assert {"fleet.command", "colony.expand", "combat.read", "combat.attack"} <= PERMISSIONS
    assert {"relations.read", "relations.negotiate"} <= PERMISSIONS
    binding = Binding(empire_id=empire, permissions=sorted(PERMISSIONS))
    assert len(binding.permissions) == 17
    for rights in [
        [*PERMISSIONS, "combat.loot"],
        [*PERMISSIONS, "combat.attack"],
        [*PERMISSIONS, "relations.ally"],
        [*PERMISSIONS, "relations.negotiate"],
    ]:
        with pytest.raises(ValidationError):
            Binding(empire_id=empire, permissions=rights)


def test_start_universe_is_solo_with_known_profiles_and_a_pinned_ruleset():
    def message(**changes):
        return {
            "version": 1,
            "operation_id": "00000000-0000-4000-8000-000000000009",
            "message": {
                "kind": "start_universe",
                "universe_id": "00000000-0000-4000-8000-000000000002",
                "name": "Orion",
                "seed": "server-random",
                "family": "solo",
                "ruleset": "v0.9",
                "profiles": ["economic_cautious", "expansionist"],
                **changes,
            },
        }

    assert Operation.model_validate(message()).message.profiles == [
        "economic_cautious",
        "expansionist",
    ]
    assert Operation.model_validate(message(profiles=[])).message.profiles == []
    for changes in (
        {"profiles": ["expansionist"] * 4},
        {"profiles": ["aggressive"]},
        {"family": "private"},
        {"ruleset": "v0.6"},
        {"name": "   "},
        {"human_slots": 2},
    ):
        with pytest.raises(ValidationError):
            Operation.model_validate(message(**changes))
