"""Version-one wire DTOs. No ORM, account credential or gameplay authority here."""

import hashlib
import json
from datetime import UTC
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator

PERMISSIONS = frozenset(
    (
        "colony.read",
        "colony.construct",
        "colony.cancel",
        "research.read",
        "research.start",
        "research.cancel",
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
        ]
    ] = Field(min_length=1, max_length=6)

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
    message: Annotated[Provision | Access | Revoke, Field(discriminator="kind")]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
