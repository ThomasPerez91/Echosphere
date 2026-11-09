"""UX-API-02 pure contract checks: what a browser may ask and what a Game receipt must prove."""

import pytest

from portal_app.accounts.security import PublicError
from portal_app.control.service import AI_PROFILES, creation_request, start_receipt

REQUEST = "11111111-1111-4111-8111-111111111111"
UNIVERSE = "22222222-2222-4222-8222-222222222222"
EMPIRE = "33333333-3333-4333-8333-333333333333"


def body(**changes):
    return {"request_id": REQUEST, "name": "Frontière d’Orion", "family": "solo",
            "profiles": ["economic_cautious", "expansionist"], **changes}


def test_solo_request_with_zero_to_three_known_profiles_is_accepted():
    assert AI_PROFILES == {"economic_cautious", "expansionist"}
    for profiles in ([], ["expansionist"], ["economic_cautious"] * 3):
        wanted = creation_request(body(profiles=profiles))
        assert wanted["profiles"] == profiles and wanted["family"] == "solo"
        assert str(wanted["request_id"]) == REQUEST


@pytest.mark.parametrize(
    "changes",
    [
        {"profiles": ["expansionist"] * 4},
        {"profiles": ["aggressive"]},
        {"profiles": "expansionist"},
        {"name": "ab"},
        {"name": " Orion"},
        {"name": "x" * 61},
        {"request_id": "not-a-uuid"},
        {"seed": "chosen-by-browser"},
    ],
)
def test_invalid_or_browser_chosen_fields_are_refused(changes):
    with pytest.raises(PublicError):
        creation_request(body(**changes))


def test_multiplayer_and_persistent_families_are_not_offered_yet():
    for family in ("private", "persistent"):
        with pytest.raises(PublicError) as refused:
            creation_request(body(family=family))
        assert refused.value.code == "family_unavailable"


def test_start_receipt_must_name_this_universe_and_a_human_empire():
    message = {"universe_id": UNIVERSE, "name": "Orion"}
    good = {"status": "applied", "universe_id": UNIVERSE, "name": "Orion",
            "human_empire_id": EMPIRE, "started_at": "2026-11-09T09:00:00+00:00"}
    assert start_receipt(message, good)
    for broken in (
        {**good, "status": "superseded"},
        {**good, "universe_id": EMPIRE},
        {**good, "name": "Autre"},
        {**good, "human_empire_id": "nope"},
        {key: value for key, value in good.items() if key != "started_at"},
    ):
        assert not start_receipt(message, broken)
