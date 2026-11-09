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


def test_solo_request_with_known_profiles_within_the_map_cap_is_accepted():
    assert AI_PROFILES == {"economic_cautious", "expansionist"}
    for profiles in ([], ["expansionist"], ["economic_cautious"] * 3):
        wanted = creation_request(body(profiles=profiles))
        assert wanted["profiles"] == profiles and wanted["family"] == "solo"
        assert str(wanted["request_id"]) == REQUEST


@pytest.mark.parametrize(
    "changes",
    [
        {"profiles": ["expansionist"] * 31},
        {"profiles": ["aggressive"]},
        {"size": 150},
        {"size": "100"},
        {"size": True},
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


def test_persistent_family_is_not_offered_yet():
    with pytest.raises(PublicError) as refused:
        creation_request(body(family="persistent"))
    assert refused.value.code == "family_unavailable"


def private(**changes):
    return body(**{"family": "private", "humans": 2, "invite": "link", **changes})


def test_private_multi_needs_two_to_ten_humans_an_invite_mode_and_the_map_cap():
    wanted = creation_request(private())
    assert (wanted["humans"], wanted["invite"], wanted["family"]) == (2, "link", "private")
    assert wanted["size"] == 100  # default map (Q61)
    assert creation_request(private(humans=4, profiles=[], invite="email"))["humans"] == 4
    big = creation_request(private(humans=10, size=2000, profiles=["expansionist"] * 30))
    assert (big["humans"], big["size"], len(big["profiles"])) == (10, 2000, 30)
    for broken in (
        private(humans=1),
        private(humans=11, profiles=[], size=2000),
        private(humans=True),
        private(humans="2"),
        private(invite="both"),
        body(family="private"),  # humans and invite are required
        body(humans=2),  # solo takes neither
    ):
        with pytest.raises(PublicError):
            creation_request(broken)
    with pytest.raises(PublicError) as crowded:
        creation_request(private(humans=3, profiles=["expansionist", "expansionist"]))
    assert crowded.value.code == "too_many_empires"  # 5 Empires on a 100-system map
    assert creation_request(private(humans=3, profiles=["expansionist"] * 2, size=300))
    with pytest.raises(PublicError) as crowded:
        creation_request(private(humans=10, profiles=["expansionist"] * 11, size=500))
    assert crowded.value.code == "too_many_empires"  # 21 Empires above the 500 cap


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


def test_private_receipt_lists_one_distinct_seat_per_human_creator_first():
    message = {"universe_id": UNIVERSE, "name": "Orion", "humans": 2}
    other = "44444444-4444-4444-8444-444444444444"
    good = {"status": "applied", "universe_id": UNIVERSE, "name": "Orion",
            "human_empire_id": EMPIRE, "human_empire_ids": [EMPIRE, other],
            "started_at": "2026-11-09T09:00:00+00:00"}
    assert start_receipt(message, good) == [EMPIRE, other]
    for seats in ([EMPIRE], [other, EMPIRE], [EMPIRE, EMPIRE], [EMPIRE, "x"]):
        assert start_receipt(message, {**good, "human_empire_ids": seats}) is None
    solo = {"universe_id": UNIVERSE, "name": "Orion"}
    assert start_receipt(solo, {**good, "human_empire_ids": [EMPIRE]}) is None


def test_link_tokens_have_a_fixed_shape_before_any_lookup():
    from portal_app.control.invitations import invite_token

    assert invite_token("a" * 43) and invite_token("A-b_c" * 9)
    for value in ("short", "a" * 65, "a" * 42 + "!", None, 43):
        assert not invite_token(value)


def test_creation_state_tells_a_slow_game_from_a_refused_start():
    from types import SimpleNamespace

    from portal_app.control.service import creation_state

    def row(error, attempts):
        return SimpleNamespace(last_error=error, attempts=attempts)

    assert creation_state(None) == "starting"
    assert creation_state(row(None, 1)) == "starting"
    # A first network miss is ordinary; a Game still unreachable after a few attempts is shown.
    assert creation_state(row("control_unavailable", 1)) == "starting"
    assert creation_state(row("control_unavailable", 3)) == "delayed"
    assert creation_state(row("unknown_target", 5)) == "delayed"
    # The Game answered and refused: said at once, even if retries go on.
    for code in ("remote_conflict", "remote_refused", "invalid_receipt"):
        assert creation_state(row(code, 1)) == "refused"


def test_empire_names_are_trimmed_visible_text_and_optional_at_creation():
    from portal_app.control.life import empire_name

    assert empire_name("  Concorde   d’Aube ") == "Concorde d’Aube"
    for bad in [None, 3, "A", "x" * 41, "No\u0007va", "  "]:
        with pytest.raises(PublicError) as refused:
            empire_name(bad)
        assert refused.value.code == "invalid_empire_name"
    assert "empire_name" not in creation_request(body())
    assert creation_request(body(empire_name=" Nova "))["empire_name"] == "Nova"
    with pytest.raises(PublicError):
        creation_request(body(empire_name="N"))
