from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.colony.rules import Ratio, Ruleset, load_ruleset
from app.simulation.production import MICRO_UNITS


@pytest.fixture
def rules():
    return load_ruleset()


@pytest.mark.parametrize(
    "kind,resource,expected",
    [
        ("extraction_complex", "alloys", [120, 210, 360, 600, 960]),
        ("flux_reactor", "flux", [100, 175, 300, 500, 800]),
        ("data_node", "data", [60, 105, 180, 300, 480]),
    ],
)
def test_reference_producer_levels_and_costs(rules, kind, resource, expected):
    for level, rate in enumerate(expected, 1):
        quote = rules.quote(kind, level)
        assert quote.production == {resource: rate * MICRO_UNITS}
        assert quote.cost["alloys"] == [250, 800, 2600, 8500, 28000][level - 1] * MICRO_UNITS
        assert quote.base_duration_us == [120, 900, 5400, 21600, 64800][level - 1] * MICRO_UNITS


def test_continuous_progression_and_deterministic_rounding(rules):
    six = rules.quote("extraction_complex", 6)
    assert six.cost == {
        "alloys": 38640 * MICRO_UNITS,
        "flux": 16560 * MICRO_UNITS,
        "data": 5520 * MICRO_UNITS,
    }
    assert six.production == {"alloys": 1_075_200_000}
    assert six.base_duration_us == 82_944_000_000
    assert rules.quote("industrial_complex", 10).construction_bonus_bps == 10500
    assert rules.quote("logistics_center", 6).capacity == 188800 * MICRO_UNITS
    assert rules.quote("extraction_complex", 20) == rules.quote("extraction_complex", 20)
    assert Ratio(numerator=138, denominator=100).apply(101, ceiling=True) == 140
    assert Ratio(numerator=112, denominator=100).apply(101) == 113
    with pytest.raises(ValueError, match="64-bit"):
        rules.quote("extraction_complex", 10**12)


@pytest.mark.parametrize(
    "kind,field,values",
    [
        ("industrial_complex", "construction_bonus_bps", [1000, 2000, 3500, 5500, 8000]),
        ("logistics_center", "capacity", [20000, 35000, 60000, 100000, 160000]),
    ],
)
def test_industry_and_storage_reference_levels(rules, kind, field, values):
    for level, value in enumerate(values, 1):
        assert getattr(rules.quote(kind, level), field) == value * (
            MICRO_UNITS if field == "capacity" else 1
        )


def test_reference_colony_and_per_instance_speed(rules):
    c = rules.colony
    assert (c.sectors, c.orbital_slots, c.queue_limit, c.base_capacity) == (12, 2, 3, 10000)
    assert c.initial_stocks == {"alloys": 2000, "flux": 1500, "data": 750}
    assert c.speeds["economy"].apply(120 * MICRO_UNITS) == 120 * MICRO_UNITS
    assert Ratio(numerator=3, denominator=2).apply(120 * MICRO_UNITS) == 180 * MICRO_UNITS
    assert c.refund_queued_bps == 10000 and c.refund_active_bps == 8000


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["colony"].update(queue_limit=0),
        lambda d: d["colony"].update(queue_limit=True),
        lambda d: d["colony"].update(unknown=1),
        lambda d: d["colony"]["speeds"]["economy"].update(denominator=0),
        lambda d: d["colony"].update(version="v0.2"),
        lambda d: d["catalogue"]["infrastructures"]["industrial_complex"].update(
            scaling_after_level=6
        ),
        lambda d: d["catalogue"]["infrastructures"]["data_node"]["explicit_levels"][0]["cost"].pop(
            "data"
        ),
        lambda d: d["colony"]["initial_stocks"].update(data=10001),
        lambda d: d["catalogue"]["infrastructures"]["data_node"]["requires"].update(missing=1),
    ],
)
def test_strict_validation_rejects_invalid_config(rules, mutate):
    data = deepcopy(rules.model_dump())
    mutate(data)
    with pytest.raises(ValidationError):
        Ruleset.model_validate(data)


def test_missing_mixed_or_duplicate_configuration_is_explicit(tmp_path: Path):
    with pytest.raises(ValueError, match="Invalid ruleset"):
        load_ruleset(root=tmp_path)
    path = tmp_path / "rulesets" / "v0.1"
    path.mkdir(parents=True)
    (path / "resources.json").write_text('{"version":"v0.1","version":"v0.2"}')
    with pytest.raises(ValueError, match="Duplicate"):
        load_ruleset(root=tmp_path)
    with pytest.raises(ValueError, match="Invalid ruleset version"):
        load_ruleset("../anything")


@pytest.mark.parametrize("level", [0, -1, 1.5, True])
def test_invalid_level_is_rejected(rules, level):
    with pytest.raises(ValueError):
        rules.quote("extraction_complex", level)
