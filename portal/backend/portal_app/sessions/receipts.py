"""Fifteen-minute, status-only capabilities. Never accepted as an authentication proof."""

import json
from datetime import UTC, datetime
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from portal_app.account_security.models import AccountRevocation
from portal_app.accounts.security import PublicError
from portal_app.sessions.models import LogoutRequest

COOKIE = "__Host-portal-revocation"


class RevocationReceipts:
    def __init__(self, accounts):
        self.accounts = accounts

    def cipher(self):
        try:
            return Fernet(self.accounts.settings.receipt_key_file.read_bytes().strip())
        except (OSError, ValueError):
            raise PublicError("receipt_unavailable", 503) from None

    def issue(self, kind, identifier):
        if kind not in ("device", "account"):
            raise ValueError("Invalid receipt scope")
        now = int(self.accounts.clock().timestamp())
        return (
            self.cipher()
            .encrypt_at_time(
                json.dumps(
                    {
                        "purpose": "revocation-status-v1",
                        "scope": kind,
                        "id": str(identifier),
                        "expires": now + 900,
                    }
                ).encode(),
                current_time=now,
            )
            .decode()
        )

    def read(self, raw):
        if not isinstance(raw, str) or len(raw) > 2048:
            raise PublicError("receipt_expired", 404)
        now = self.accounts.clock()
        try:
            value = json.loads(
                self.cipher().decrypt_at_time(
                    raw.encode(), ttl=900, current_time=int(now.timestamp())
                )
            )
            if (
                set(value) != {"purpose", "scope", "id", "expires"}
                or value["purpose"] != "revocation-status-v1"
                or value["scope"] not in ("device", "account")
                or type(value["expires"]) is not int
                or now.timestamp() >= value["expires"]
            ):
                raise ValueError()
            identifier = UUID(value["id"])
        except (InvalidToken, ValueError, TypeError, UnicodeError):
            raise PublicError("receipt_expired", 404) from None
        with self.accounts.factory() as session:
            model = LogoutRequest if value["scope"] == "device" else AccountRevocation
            source = session.get(model, identifier)
            if source is None:
                raise PublicError("receipt_expired", 404)
            return {
                "state": source.state,
                "scope": value["scope"],
                "expires_at": datetime.fromtimestamp(value["expires"], UTC).isoformat(),
            }


def attach(result, accounts, scope, identifier):
    if identifier:
        try:
            proof = RevocationReceipts(accounts).issue(scope, identifier)
        except PublicError:
            return result  # Revocation was committed; never claim it failed to happen.
        result.set_cookie(
            COOKIE, proof, max_age=900, secure=True, httponly=True, samesite="strict", path="/"
        )
    return result
