import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.control.contracts import PERMISSIONS, Binding, Operation


def test_versioned_shared_schema_matches_the_game_admission_contract():
    source = Path(__file__).resolve().parents[2] / "contracts/portal-game/v1.schema.json"
    assert json.loads(source.read_text()) == Operation.model_json_schema()


def test_twelve_rights_accepted_thirteenth_refused():
    empire = "00000000-0000-4000-8000-000000000001"
    assert len(PERMISSIONS) == 12 and {"fleet.read", "fleet.build", "fleet.command"} <= PERMISSIONS
    binding = Binding(empire_id=empire, permissions=sorted(PERMISSIONS))
    assert len(binding.permissions) == 12
    for rights in [[*PERMISSIONS, "fleet.attack"], [*PERMISSIONS, "fleet.read"]]:
        with pytest.raises(ValidationError):
            Binding(empire_id=empire, permissions=rights)
