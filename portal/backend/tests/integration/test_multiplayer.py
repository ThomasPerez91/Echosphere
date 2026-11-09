"""UX-API-03 (Q59): multi seats, link and email invitations, through the real Accounts DB."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_control_outbox import PASSWORD, Remote, drain

from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError
from portal_app.control.invitations import Invitations
from portal_app.control.models import InvitationEmailOutbox, UniverseMembership
from portal_app.control.service import Lobby
from portal_app.delivery.worker import deliver_invitation_one
from portal_app.sessions.service import Sessions, csrf

pytestmark = pytest.mark.integration


def player(accounts, email):
    accounts.register(email, PASSWORD, email)
    sessions = Sessions(accounts)
    challenge = sessions.challenge(email)
    return sessions.login(email, PASSWORD, challenge, csrf(challenge), None, None, email)[0]


def multi(lobby, raw, humans, invite, profiles=()):
    body = {"request_id": str(uuid4()), "name": "Multi", "family": "private",
            "profiles": list(profiles), "humans": humans, "invite": invite}
    return lobby.create(raw, csrf(raw), body, "peer")["universe_id"]


class CaptureSMTP:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


@pytest.fixture
def world(accounts):
    remote, lobby, invitations = Remote(), Lobby(accounts), Invitations(accounts)
    creator = player(accounts, "creator@example.org")
    return accounts, remote, lobby, invitations, creator


def seats_of(accounts, universe):
    with accounts.factory() as session:
        return {
            row.user_id: row.bindings[0]["empire_id"]
            for row in session.scalars(
                select(UniverseMembership).where(UniverseMembership.universe_id == universe)
            )
            if row.bindings  # a player who left keeps no binding (Q60)
        }


def test_link_fills_seats_in_order_and_a_full_game_refuses(world):
    accounts, remote, lobby, invitations, creator = world
    universe = multi(lobby, creator, 3, "link", ["expansionist"])
    drain(accounts, remote)
    first = invitations.link(creator, csrf(creator), universe)
    second = invitations.link(creator, csrf(creator), universe)
    old, token = first["url"].split("#invite=")[1], second["url"].split("#invite=")[1]
    friend = player(accounts, "friend@example.org")
    with pytest.raises(PublicError) as replaced:
        invitations.accept(friend, csrf(friend), token=old)
    assert replaced.value.code == "invitation_not_found"
    assert invitations.accept(friend, csrf(friend), token=token)["status"] == "joined"
    assert invitations.accept(friend, csrf(friend), token=token)["status"] == "member"
    third = player(accounts, "third@example.org")
    invitations.accept(third, csrf(third), token=token)
    drain(accounts, remote)
    seats = seats_of(accounts, UUID(universe))
    assert len(seats) == 3 and len(set(seats.values())) == 3
    late = player(accounts, "late@example.org")
    with pytest.raises(PublicError) as full:
        invitations.accept(late, csrf(late), token=token)
    assert full.value.code == "game_full"
    view = next(m for m in lobby.read(creator)["memberships"] if m["universe_id"] == universe)
    assert (view["seats_total"], view["seats_taken"], view["invite_mode"]) == (3, 3, "link")
    member = next(m for m in lobby.read(third)["memberships"] if m["universe_id"] == universe)
    assert member["creator"] is False and "invite_mode" not in member


def test_email_invitation_is_bound_to_one_address_and_delivered_encrypted(world):
    accounts, remote, lobby, invitations, creator = world
    universe = multi(lobby, creator, 2, "email")
    with pytest.raises(PublicError) as wrong_mode:
        invitations.link(creator, csrf(creator), universe)
    assert wrong_mode.value.code == "invitation_mode_mismatch"
    with pytest.raises(PublicError) as self_invite:
        invitations.send(creator, csrf(creator), universe, "Creator@example.org")
    assert self_invite.value.code == "invitation_self"
    sent = invitations.send(creator, csrf(creator), universe, "Guest@Example.org")
    with pytest.raises(PublicError) as full:
        invitations.send(creator, csrf(creator), universe, "other@example.org")
    assert full.value.code == "game_full"  # one free seat, already promised
    smtp = CaptureSMTP()
    assert deliver_invitation_one(accounts, smtp)
    (message,) = smtp.messages
    assert message["To"] == "Guest@example.org" and "/rejoindre#invite=" in message.get_content()
    with accounts.factory() as session:
        assert session.scalar(select(InvitationEmailOutbox.payload_ciphertext)) is None
    stranger = player(accounts, "stranger@example.org")
    with pytest.raises(PublicError) as other:
        invitations.accept(stranger, csrf(stranger), invitation_id=sent["invitation_id"])
    assert other.value.code == "invitation_other_account"
    guest = player(accounts, "guest@example.org")
    (received,) = lobby.read(guest)["invitations"]
    assert received["universe_id"] == universe and received["name"] == "Multi"
    with pytest.raises(PublicError) as starting:
        invitations.accept(guest, csrf(guest), invitation_id=sent["invitation_id"])
    assert starting.value.code == "game_starting"
    drain(accounts, remote)
    assert invitations.accept(guest, csrf(guest), invitation_id=sent["invitation_id"])[
        "status"
    ] == "joined"
    assert lobby.read(guest)["invitations"] == []
    with pytest.raises(PublicError):
        invitations.accept(guest, csrf(guest), invitation_id=sent["invitation_id"])


def test_declined_and_revoked_invitations_cannot_be_used(world):
    accounts, remote, lobby, invitations, creator = world
    universe = multi(lobby, creator, 4, "email")
    drain(accounts, remote)
    one = invitations.send(creator, csrf(creator), universe, "one@example.org")
    two = invitations.send(creator, csrf(creator), universe, "two@example.org")
    first, second = player(accounts, "one@example.org"), player(accounts, "two@example.org")
    assert invitations.decline(first, csrf(first), one["invitation_id"])["state"] == "declined"
    assert invitations.revoke(creator, csrf(creator), two["invitation_id"])["state"] == "revoked"
    for raw, sent in ((first, one), (second, two)):
        with pytest.raises(PublicError):
            invitations.accept(raw, csrf(raw), invitation_id=sent["invitation_id"])
    with pytest.raises(PublicError):
        invitations.revoke(first, csrf(first), one["invitation_id"])  # not the creator
    with accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(UniverseMembership)) == 1
        assert session.scalar(select(func.count()).select_from(User)) == 3


def kinds(remote, kind):
    return [r[3]["message"] for r in remote.requests if r[3] and r[3]["message"]["kind"] == kind]


def test_chosen_empire_names_reach_game_and_mes_parties(world):
    accounts, remote, lobby, invitations, creator = world
    body = {"request_id": str(uuid4()), "name": "Multi", "family": "private", "profiles": [],
            "humans": 2, "invite": "link", "empire_name": "  Concorde   d’Aube "}
    universe = lobby.create(creator, csrf(creator), body, "peer")["universe_id"]
    drain(accounts, remote)
    token = invitations.link(creator, csrf(creator), universe)["url"].split("#invite=")[1]
    friend = player(accounts, "friend@example.org")
    with pytest.raises(PublicError) as invalid:
        invitations.accept(friend, csrf(friend), token=token, name="X")
    assert invalid.value.code == "invalid_empire_name"
    invitations.accept(friend, csrf(friend), token=token, name="Hégémonie")
    drain(accounts, remote)
    seats = seats_of(accounts, UUID(universe))
    named = {m["empire_id"]: m["name"] for m in kinds(remote, "name_empire")}
    with accounts.factory() as session:
        ids = {u.email: u.id for u in session.scalars(select(User))}
    assert named == {seats[ids["creator@example.org"]]: "Concorde d’Aube",
                     seats[ids["friend@example.org"]]: "Hégémonie"}
    view = next(m for m in lobby.read(friend)["memberships"] if m["universe_id"] == universe)
    assert view["empire_name"] == "Hégémonie" and not view["left"] and not view["archived"]
    from portal_app.control.life import GameLife

    assert GameLife(accounts).rename(friend, csrf(friend), universe, "Nouvelle Hégémonie") == {
        "empire_name": "Nouvelle Hégémonie"}
    drain(accounts, remote)
    assert kinds(remote, "name_empire")[-1]["name"] == "Nouvelle Hégémonie"


def test_leaving_a_multi_game_hands_the_seat_to_an_ai_and_never_reoffers_it(world):
    from portal_app.control.life import GameLife

    accounts, remote, lobby, invitations, creator = world
    universe = multi(lobby, creator, 3, "link")
    drain(accounts, remote)
    token = invitations.link(creator, csrf(creator), universe)["url"].split("#invite=")[1]
    friend = player(accounts, "friend@example.org")
    invitations.accept(friend, csrf(friend), token=token)
    drain(accounts, remote)
    seat_id = seats_of(accounts, UUID(universe))
    life = GameLife(accounts)
    assert life.leave(friend, csrf(friend), universe) == {"status": "left"}
    assert life.leave(friend, csrf(friend), universe) == {"status": "left"}  # replay: no effect
    drain(accounts, remote)
    (hand_over,) = kinds(remote, "hand_over_empire")
    with accounts.factory() as session:
        friend_id = session.scalar(select(User.id).where(User.email == "friend@example.org"))
    assert hand_over["empire_id"] == seat_id[friend_id] and hand_over["profile"] == (
        "economic_cautious")
    view = next(m for m in lobby.read(friend)["memberships"] if m["universe_id"] == universe)
    assert view["left"] and view["desired_status"] == "revoked" and not view["entry_available"]
    # One seat left of three: the left seat is not offered to a newcomer.
    third = player(accounts, "third@example.org")
    invitations.accept(third, csrf(third), token=token)
    late = player(accounts, "late@example.org")
    with pytest.raises(PublicError) as full:
        invitations.accept(late, csrf(late), token=token)
    assert full.value.code == "game_full"
    drain(accounts, remote)
    assert hand_over["empire_id"] not in seats_of(accounts, UUID(universe)).values()


def test_archiving_a_solo_game_keeps_it_readable_only(world):
    from portal_app.control.life import READ_ONLY, GameLife

    accounts, remote, lobby, _, creator = world
    body = {"request_id": str(uuid4()), "name": "Solo", "family": "solo", "profiles": []}
    universe = lobby.create(creator, csrf(creator), body, "peer")["universe_id"]
    drain(accounts, remote)
    life = GameLife(accounts)
    assert life.leave(creator, csrf(creator), universe) == {"status": "archived"}
    assert life.leave(creator, csrf(creator), universe) == {"status": "archived"}
    drain(accounts, remote)
    view = next(m for m in lobby.read(creator)["memberships"] if m["universe_id"] == universe)
    assert view["archived"] and view["desired_status"] == "active"
    with accounts.factory() as session:
        member = session.scalar(select(UniverseMembership).where(
            UniverseMembership.universe_id == UUID(universe)))
        assert member.bindings[0]["permissions"] == READ_ONLY
    assert kinds(remote, "hand_over_empire") == []
    with pytest.raises(PublicError) as renamed:
        life.rename(creator, csrf(creator), universe, "Trop tard")
    assert renamed.value.code == "rename_unavailable"


def test_deleting_a_solo_game_or_a_blocked_creation_removes_it_from_the_lists(world):
    """Recette 09/11/2026: the creator deletes a solo game (access revoked) or a creation that
    never started (no access is granted if Game starts it later); a multi game is never deleted."""
    from portal_app.control.life import GameLife

    accounts, remote, lobby, _, creator = world
    life = GameLife(accounts)
    body = {"request_id": str(uuid4()), "name": "Solo", "family": "solo", "profiles": []}
    played = lobby.create(creator, csrf(creator), body, "peer")["universe_id"]
    drain(accounts, remote)
    assert life.delete(creator, csrf(creator), played) == {"status": "deleted"}
    assert life.delete(creator, csrf(creator), played) == {"status": "deleted"}  # replay
    with accounts.factory() as session:
        member = session.scalar(select(UniverseMembership).where(
            UniverseMembership.universe_id == UUID(played)))
        assert member.desired_status == "revoked" and member.bindings == []
    # A creation deleted before Game answered: started later, it is never granted nor shown.
    body = dict(body, request_id=str(uuid4()), name="Bloquée")
    blocked = lobby.create(creator, csrf(creator), body, "peer")["universe_id"]
    assert any(c["universe_id"] == blocked for c in lobby.read(creator)["creations"])
    assert life.delete(creator, csrf(creator), blocked) == {"status": "deleted"}
    drain(accounts, remote)
    view = lobby.read(creator)
    shown = {m["universe_id"] for m in view["memberships"]} | {
        c["universe_id"] for c in view["creations"]}
    assert played not in shown and blocked not in shown
    with accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(UniverseMembership).where(
            UniverseMembership.universe_id == UUID(blocked))) == 0
    # Someone else's game, or a started multi game: refused.
    friend = player(accounts, "friend@example.org")
    with pytest.raises(PublicError) as other:
        life.delete(friend, csrf(friend), blocked)
    assert other.value.code == "universe_not_found"
    shared = multi(lobby, creator, 2, "link")
    drain(accounts, remote)
    with pytest.raises(PublicError) as refused:
        life.delete(creator, csrf(creator), shared)
    assert refused.value.code == "delete_unavailable"
