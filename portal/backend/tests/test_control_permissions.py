import pytest

from portal_app.accounts.security import PublicError
from portal_app.control.service import normalized_bindings

EMPIRE = "00000000-0000-4000-8000-000000000001"


def test_galaxy_and_exploration_rights_are_explicit_never_implied():
    rights = ["galaxy.read", "exploration.read", "exploration.start", "colony.read"]
    (binding,) = normalized_bindings([{"empire_id": EMPIRE, "permissions": rights}])
    assert binding["permissions"] == sorted(rights)
    (colony_only,) = normalized_bindings([{"empire_id": EMPIRE, "permissions": ["colony.read"]}])
    assert colony_only["permissions"] == ["colony.read"]


@pytest.mark.parametrize("rights", [["galaxy.write"], ["exploration.cancel"], ["galaxy.read"] * 2])
def test_unknown_or_duplicated_rights_are_refused(rights):
    with pytest.raises(PublicError):
        normalized_bindings([{"empire_id": EMPIRE, "permissions": rights}])


def test_seventeen_rights_including_relations_accepted_eighteenth_refused():
    from portal_app.control.service import PERMISSIONS

    assert len(PERMISSIONS) == 17
    (binding,) = normalized_bindings([{"empire_id": EMPIRE, "permissions": sorted(PERMISSIONS)}])
    assert {"colony.expand", "combat.read", "combat.attack"} <= set(binding["permissions"])
    assert {"relations.read", "relations.negotiate"} <= set(binding["permissions"])
    for extra in ["combat.loot", "combat.attack", "relations.ally", "relations.read"]:
        with pytest.raises(PublicError):
            normalized_bindings(
                [{"empire_id": EMPIRE, "permissions": [*sorted(PERMISSIONS), extra]}]
            )
