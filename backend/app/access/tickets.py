"""Strict local verification: a ticket cannot supply an algorithm or discovery endpoint."""

import re
from uuid import UUID

import jwt
from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError

TYPE = "echosphere-handoff+jwt"


class TicketDenied(Exception):
    pass


class Claims(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    iss: str
    aud: str
    sub: UUID
    jti: UUID
    universe_id: UUID
    membership_id: UUID
    device_id: UUID
    pre_auth_id: UUID
    iat: StrictInt
    exp: StrictInt
    revision: StrictInt
    access_epoch: StrictInt
    account_epoch: StrictInt
    device_epoch: StrictInt


def verify(raw, settings, now):
    try:
        if not isinstance(raw, str) or len(raw) > 4096:
            raise TicketDenied()
        header = jwt.get_unverified_header(raw)
        if (
            set(header) != {"alg", "kid", "typ"}
            or header["alg"] != "EdDSA"
            or header["typ"] != TYPE
            or not isinstance(header["kid"], str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", header["kid"])
        ):
            raise TicketDenied()
        key = settings.handoff_public_keys.get(header["kid"])
        if key is None:
            raise TicketDenied()
        wire = jwt.decode(
            raw,
            key.read_bytes(),
            algorithms=["EdDSA"],
            audience=settings.game_public_origin,
            issuer=settings.portal_public_origin,
            options={
                "verify_exp": False,
                "verify_iat": False,
                "require": list(Claims.model_fields),
                "strict_aud": True,
            },
        )
        value = Claims.model_validate(wire)
        timestamp = now.timestamp()
        if (
            not value.iat <= timestamp < value.exp
            or not 0 < value.exp - value.iat <= 60
            or value.revision < 1
            or value.access_epoch < 1
            or value.account_epoch < 0
            or value.device_epoch < 0
        ):
            raise TicketDenied()
        return value, header["kid"]
    except (jwt.PyJWTError, ValidationError, ValueError, TypeError, OSError, KeyError):
        raise TicketDenied() from None
