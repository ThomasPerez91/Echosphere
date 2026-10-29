"""Atomic account/credential/token/outbox operations; no sessions or Game access."""

import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cryptography.fernet import Fernet
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from portal_app.accounts.models import (
    AbuseCounter,
    AccountToken,
    EmailOutbox,
    PasswordCredential,
    SecurityEvent,
    User,
)
from portal_app.accounts.security import Passwords, PublicError, normalize_email, token_digest
from portal_app.core.config import Settings


def utc_now():
    return datetime.now(UTC)


class Accounts:
    def __init__(
        self, factory, settings: Settings, passwords: Passwords | None = None, clock=utc_now
    ):
        self.factory = factory
        self.settings = settings
        self.passwords = passwords if passwords is not None else Passwords()
        self.clock = clock

    def cipher(self) -> Fernet:
        try:
            return Fernet(self.settings.mail_key_file.read_bytes().strip())
        except (OSError, ValueError):
            raise PublicError("temporarily_unavailable", 503) from None

    def limit(self, action: str, peer: str, subject: str) -> None:
        now = self.clock()
        window = now.replace(minute=0, second=0, microsecond=0)
        verification = action == "verify"
        limits = [
            (
                f"{action}:ip:{token_digest(peer)}",
                self.settings.verification_ip_limit
                if verification
                else self.settings.registration_ip_limit,
            ),
            (
                f"{action}:subject:{token_digest(subject)}",
                self.settings.verification_token_limit
                if verification
                else self.settings.email_request_limit,
            ),
        ]
        allowed = True
        with self.factory.begin() as session:
            for key, maximum in limits:
                query = insert(AbuseCounter).values(key=key, window_at=window, count=1)
                value = session.scalar(
                    query.on_conflict_do_update(
                        index_elements=[AbuseCounter.key, AbuseCounter.window_at],
                        set_={"count": AbuseCounter.count + 1},
                        where=AbuseCounter.count < maximum,
                    ).returning(AbuseCounter.count)
                )
                allowed &= value is not None
        if not allowed:
            raise PublicError("rate_limited", 429)

    def issue(self, session, user: User, now: datetime, cipher: Fernet) -> None:
        # Caller owns the User lock. Always User -> token -> outbox, as in delivery.
        session.execute(
            update(AccountToken)
            .where(
                AccountToken.user_id == user.id,
                AccountToken.active,
            )
            .values(active=False, revoked_at=now)
        )
        session.execute(
            update(EmailOutbox)
            .where(
                EmailOutbox.user_id == user.id,
                EmailOutbox.state == "pending",
            )
            .values(state="cancelled", payload_ciphertext=None)
        )
        raw = secrets.token_urlsafe(32)
        token_id, outbox_id = uuid4(), uuid4()
        expires = now + timedelta(hours=24)
        session.add(
            AccountToken(
                id=token_id,
                user_id=user.id,
                digest=token_digest(raw),
                created_at=now,
                expires_at=expires,
            )
        )
        session.flush()
        payload = {
            "outbox_id": str(outbox_id),
            "user_id": str(user.id),
            "token_id": str(token_id),
            "recipient": user.email,
            "token": raw,
        }
        encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()
        session.add(
            EmailOutbox(
                id=outbox_id,
                user_id=user.id,
                token_id=token_id,
                payload_ciphertext=encrypted,
                state="pending",
                attempts=0,
                created_at=now,
                expires_at=expires,
                next_attempt_at=now,
            )
        )

    def register(self, email: str, password: str, peer: str) -> None:
        address, key = normalize_email(email)
        self.limit("email", peer, key)
        cipher = self.cipher()
        # Existing and unknown addresses undergo the same password policy/hash work.
        saved = self.passwords.new_hash(password)
        now = self.clock()
        with self.factory.begin() as session:
            identifier = session.scalar(
                insert(User)
                .values(
                    id=uuid4(),
                    email=address,
                    email_key=key,
                    status="active",
                    created_at=now,
                )
                .on_conflict_do_nothing(index_elements=[User.email_key])
                .returning(User.id)
            )
            if identifier is None:
                return
            user = session.get(User, identifier)
            session.add(PasswordCredential(user_id=user.id, password_hash=saved, changed_at=now))
            self.issue(session, user, now, cipher)
            session.add(SecurityEvent(user_id=user.id, kind="account_registered", created_at=now))

    def resend(self, email: str, password: str, peer: str) -> None:
        _, key = normalize_email(email)
        self.limit("email", peer, key)
        cipher = self.cipher()
        with self.factory() as session:
            data = session.execute(
                select(User.id, PasswordCredential.password_hash)
                .join(
                    PasswordCredential,
                    PasswordCredential.user_id == User.id,
                )
                .where(User.email_key == key)
            ).first()
        if not self.passwords.verify(password, data.password_hash if data else None):
            return
        now = self.clock()
        with self.factory.begin() as session:
            user = session.get(User, data.id, with_for_update=True)
            current = session.get(PasswordCredential, user.id)
            if (
                user.status != "active"
                or user.email_verified_at is not None
                or current.password_hash != data.password_hash
            ):
                return
            self.issue(session, user, now, cipher)
            session.add(
                SecurityEvent(user_id=user.id, kind="verification_reissued", created_at=now)
            )

    def verify(self, raw: str, password: str, peer: str) -> None:
        digest = token_digest(raw)
        self.limit("verify", peer, digest)
        with self.factory() as session:
            data = session.execute(
                select(AccountToken.user_id, PasswordCredential.password_hash)
                .join(PasswordCredential, PasswordCredential.user_id == AccountToken.user_id)
                .where(AccountToken.digest == digest)
            ).first()
        if not self.passwords.verify(password, data.password_hash if data else None):
            raise PublicError("invalid_verification")
        with self.factory.begin() as session:
            user = session.get(User, data.user_id, with_for_update=True)
            token = session.scalar(select(AccountToken).where(AccountToken.digest == digest))
            current = session.get(PasswordCredential, user.id)
            now = self.clock()
            if (
                user.status != "active"
                or user.email_verified_at is not None
                or not token.active
                or now >= token.expires_at
                or token.purpose != "email_verification"
                or current.password_hash != data.password_hash
            ):
                raise PublicError("invalid_verification")
            token.active = False
            token.consumed_at = now
            user.email_verified_at = now
            session.execute(
                update(EmailOutbox)
                .where(
                    EmailOutbox.user_id == user.id,
                    EmailOutbox.state == "pending",
                )
                .values(state="cancelled", payload_ciphertext=None)
            )
            session.add(SecurityEvent(user_id=user.id, kind="email_verified", created_at=now))
