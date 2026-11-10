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
                "ruleset": "v0.10",
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
        {"profiles": ["expansionist"] * 40},  # 41 Empires: above any galaxy-v2 cap
        {"profiles": ["aggressive"]},
        {"size": 150},
        {"size": "100"},
        {"ruleset": "v0.9"},  # A5 (09/11/2026): every new game is v0.10
        {"family": "private"},
        {"ruleset": "v0.6"},
        {"name": "   "},
        {"human_slots": 2},
    ):
        with pytest.raises(ValidationError):
            Operation.model_validate(message(**changes))


def test_private_multi_start_has_two_to_ten_humans_and_a_map_size():
    def message(**changes):
        return {
            "version": 1,
            "operation_id": "00000000-0000-4000-8000-000000000010",
            "message": {
                "kind": "start_universe",
                "universe_id": "00000000-0000-4000-8000-000000000003",
                "name": "Orion",
                "seed": "server-random",
                "family": "private",
                "humans": 2,
                "ruleset": "v0.10",
                "profiles": ["expansionist", "economic_cautious"],
                **changes,
            },
        }

    assert Operation.model_validate(message()).message.humans == 2
    assert Operation.model_validate(message(humans=10, profiles=[])).message.humans == 10
    big = Operation.model_validate(message(humans=10, size=2000, profiles=["expansionist"] * 30))
    assert (big.message.size, len(big.message.profiles)) == (2000, 30)
    assert Operation.model_validate(message()).message.size == 100  # default map
    for changes in (
        {"humans": 1},  # one human is a SOLO game
        {"humans": 11, "profiles": []},
        {"family": "solo"},
        {"humans": "2"},
    ):
        with pytest.raises(ValidationError):
            Operation.model_validate(message(**changes))


def test_empire_names_are_visible_text_and_a_hand_over_names_a_known_profile():
    universe = "00000000-0000-4000-8000-000000000002"
    empire = "00000000-0000-4000-8000-000000000003"

    def operation(message):
        return Operation.model_validate(
            {"version": 1, "operation_id": "00000000-0000-4000-8000-000000000009",
             "message": {"universe_id": universe, "empire_id": empire, **message}}
        )

    named = operation({"kind": "name_empire", "name": "Concorde d’Aube"})
    assert named.message.name == "Concorde d’Aube"
    for name in ["A", " Concorde", "Concorde ", "Con\ncorde", "x" * 41, "\u0085Nova"]:
        with pytest.raises(ValidationError):
            operation({"kind": "name_empire", "name": name})
    assert operation({"kind": "hand_over_empire", "profile": "expansionist"}).message.profile == (
        "expansionist"
    )
    for extra in [{"profile": "aggressive"}, {"profile": "expansionist", "resources": {}}]:
        with pytest.raises(ValidationError):
            operation({"kind": "hand_over_empire", **extra})


def test_a_test_game_is_a_solo_start_and_leaves_earlier_digests_unchanged():
    message = {
        "kind": "start_universe",
        "universe_id": "00000000-0000-4000-8000-000000000002",
        "name": "Banc d'essai",
        "seed": "seed",
        "family": "solo",
        "ruleset": "v0.11",
        "profiles": [],
    }
    envelope = {"version": 1, "operation_id": "00000000-0000-4000-8000-000000000003"}
    plain = Operation.model_validate({**envelope, "message": message})
    assert "sandbox" not in plain.model_dump(mode="json", exclude_unset=True)["message"]
    test = Operation.model_validate({**envelope, "message": {**message, "sandbox": True}})
    assert test.message.sandbox is True
    for broken in (
        {**message, "sandbox": "yes"},
        {**message, "sandbox": True, "family": "private", "humans": 2},
    ):
        with pytest.raises(ValidationError):
            Operation.model_validate({**envelope, "message": broken})
