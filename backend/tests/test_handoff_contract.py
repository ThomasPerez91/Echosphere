import json
from pathlib import Path

from app.access.tickets import Claims


def test_versioned_handoff_schema_matches_strict_game_claims():
    schema = Path(__file__).resolve().parents[2] / "contracts/handoff/v1.schema.json"
    assert json.loads(schema.read_text()) == Claims.model_json_schema()


def test_non_ascii_csrf_is_a_controlled_refusal():
    import pytest

    from app.access.service import AccessError, check_csrf

    with pytest.raises(AccessError) as error:
        check_csrf("a" * 43, "é" * 64)
    assert error.value.status == 403
