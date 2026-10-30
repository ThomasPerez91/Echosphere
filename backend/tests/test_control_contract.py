import json
from pathlib import Path

from app.control.contracts import Operation


def test_versioned_shared_schema_matches_the_game_admission_contract():
    source = Path(__file__).resolve().parents[2] / "contracts/portal-game/v1.schema.json"
    assert json.loads(source.read_text()) == Operation.model_json_schema()
