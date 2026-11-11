"""Version-one wire DTOs. No ORM, account credential or gameplay authority here."""

import hashlib
import json
from datetime import UTC
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

PERMISSIONS = frozenset(
    (
        "colony.read",
        "colony.construct",
        "colony.cancel",
        "research.read",
        "research.start",
        "research.cancel",
        "galaxy.read",
        "exploration.read",
        "exploration.start",
        "fleet.read",
        "fleet.build",
        "fleet.command",
        "colony.expand",
        "combat.read",
        "combat.attack",
        "relations.read",
        "relations.negotiate",
    )
)


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Binding(Wire):
    empire_id: UUID
    permissions: list[
        Literal[
            "colony.read",
            "colony.construct",
            "colony.cancel",
            "research.read",
            "research.start",
            "research.cancel",
            "galaxy.read",
            "exploration.read",
            "exploration.start",
            "fleet.read",
            "fleet.build",
            "fleet.command",
            "colony.expand",
            "combat.read",
            "combat.attack",
            "relations.read",
            "relations.negotiate",
        ]
    ] = Field(min_length=1, max_length=17)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.permissions)) != len(self.permissions):
            raise ValueError("Repeated permission")
        self.permissions.sort()
        return self


class Provision(Wire):
    kind: Literal["provision_universe"]
    universe_id: UUID
    name: str = Field(min_length=1, max_length=120)
    seed: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def not_blank(self):
        if not self.name.strip():
            raise ValueError("Blank name")
        return self


class Start(Wire):
    """UX-API-02/03: create and start a universe in one idempotent operation: SOLO (one human
    Empire) or PRIVATE multi (2 to 10 human Empires, Q59/Q61) with AI opponents of known
    profiles, ruleset v0.10 (galaxy-v2, A5 of 09/11/2026: every game is v0.10). The map `size`
    caps the Empires (100 -> 4, 300 -> 12, 500 -> 20, 1000 and 2000 -> 40; exact cap checked
    against the pinned ruleset by Game). The result lists the human Empires (seats) so that
    Portal can grant them; no AI actor identity leaves Game."""

    kind: Literal["start_universe"]
    universe_id: UUID
    name: str = Field(min_length=1, max_length=120)
    seed: str = Field(min_length=1, max_length=200)
    family: Literal["solo", "private"]
    humans: StrictInt = Field(default=1, ge=1, le=10)
    ruleset: Literal["v0.10", "v0.11", "v0.12"]
    size: Literal[100, 300, 500, 1000, 2000] = 100
    profiles: list[Literal["economic_cautious", "expansionist"]] = Field(max_length=30)
    # Test game (recette 10/11/2026): solo only, almost finished world plus sandbox tools.
    # Omitted when false so every earlier envelope keeps its digest (exclude_unset).
    sandbox: StrictBool = False
    # Galaxy shape (v0.12, recette 11/11/2026): `random` draws one from the seed. Omitted when
    # unset (lattice blob) so every earlier envelope keeps its digest.
    shape: Literal["random", "elliptical", "spiral2", "spiral4", "irregular", "clusters"] | None = (
        None
    )

    @model_validator(mode="after")
    def not_blank(self):
        if not self.name.strip():
            raise ValueError("Blank name")
        if (self.family == "solo") != (self.humans == 1):
            raise ValueError("Solo means exactly one human Empire")
        if self.sandbox and self.family != "solo":
            raise ValueError("A test game is a solo game")
        if self.humans + len(self.profiles) > 40:
            raise ValueError("galaxy-v2 offers at most forty starting sites")
        return self


def empire_name(value):
    """Q60: a player's own Empire name, 2 to 40 visible characters, no control character."""
    hidden = any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value)
    if value != value.strip() or len(value) < 2 or hidden:
        raise ValueError("Invalid Empire name")
    return value


class NameEmpire(Wire):
    """Q60: the player names the human Empire of their seat (at creation, on joining, later)."""

    kind: Literal["name_empire"]
    universe_id: UUID
    empire_id: UUID
    name: str = Field(min_length=2, max_length=40)

    @model_validator(mode="after")
    def visible(self):
        empire_name(self.name)
        return self


class HandOver(Wire):
    """Q60: a player leaving a multi game hands their Empire to a server AI of a known profile;
    refused while any human binding remains on that Empire (Portal revokes the seat first)."""

    kind: Literal["hand_over_empire"]
    universe_id: UUID
    empire_id: UUID
    profile: Literal["economic_cautious", "expansionist"]


class Access(Wire):
    kind: Literal["set_universe_access"]
    membership_id: UUID
    global_user_id: UUID
    universe_id: UUID
    revision: StrictInt = Field(ge=1)
    access_epoch: StrictInt = Field(ge=1)
    account_epoch: StrictInt = Field(ge=0)
    status: Literal["active", "suspended", "revoked"]
    portal_confirmed_at: AwareDatetime
    valid_until: AwareDatetime
    bindings: list[Binding] = Field(max_length=100)

    @model_validator(mode="after")
    def absolute_dates(self):
        from datetime import timedelta

        self.portal_confirmed_at = self.portal_confirmed_at.astimezone(UTC)
        self.valid_until = self.valid_until.astimezone(UTC)
        if (
            not self.portal_confirmed_at
            < self.valid_until
            <= (self.portal_confirmed_at + timedelta(hours=8))
        ):
            raise ValueError("Invalid absolute access lifetime")
        if len({b.empire_id for b in self.bindings}) != len(self.bindings):
            raise ValueError("Repeated empire")
        self.bindings.sort(key=lambda b: str(b.empire_id))
        return self


class Revoke(Wire):
    kind: Literal["revoke_sessions"]
    global_user_id: UUID
    scope: Literal["account", "device"]
    epoch: StrictInt = Field(ge=1)
    device_id: UUID | None = None

    @model_validator(mode="after")
    def target(self):
        if (self.scope == "device") != (self.device_id is not None):
            raise ValueError("Invalid revocation target")
        return self


class Operation(Wire):
    version: StrictInt = Field(ge=1, le=1)
    operation_id: UUID
    message: Annotated[
        Provision | Start | NameEmpire | HandOver | Access | Revoke, Field(discriminator="kind")
    ]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
