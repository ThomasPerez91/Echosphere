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
