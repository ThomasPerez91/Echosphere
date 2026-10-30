"""Accounts email outbox. SMTP acceptance is not an exactly-once delivery guarantee."""

import argparse
import json
import smtplib
import time
from datetime import timedelta
from email.message import EmailMessage
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from portal_app.account_security.delivery import deliver_security_one, prune_security
from portal_app.accounts.models import AbuseCounter, AccountToken, EmailOutbox, SecurityEvent, User
from portal_app.accounts.security import PublicError, token_digest
from portal_app.accounts.service import Accounts
from portal_app.core.config import Settings
from portal_app.mfa.models import AuthFailure, MfaChallenge, MfaRecoverySession
from portal_app.persistence.database import create_database_engine, create_session_factory
from portal_app.sessions.models import LoginChallenge


class LocalSMTP:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: EmailMessage) -> None:
        if self.settings.mail_transport != "smtp_local" or self.settings.mail_host not in (
            "portal-mailpit",
            "localhost",
            "127.0.0.1",
        ):
            raise OSError("Email transport is not configured")
        # Development receiver only; no public SMTP provider or relay is selected by C02.
        with smtplib.SMTP(self.settings.mail_host, self.settings.mail_port, timeout=3) as client:
            refused = client.send_message(message)
            if refused:
                raise OSError("Email recipient was not accepted")


def build_message(outbox: EmailOutbox, payload: dict, origin: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = "Echosphere <accounts@echosphere.invalid>"
    message["To"] = payload["recipient"]
    message["Subject"] = "Confirmez votre adresse Echosphere"
    message["Message-ID"] = f"<{outbox.id}@portal.echosphere.invalid>"
    message.set_content(
        "Vous avez demandé la création d’un compte Echosphere.\n"
        "Confirmez votre adresse avec le mot de passe saisi à l’inscription :\n"
        f"{origin}/#verify-email={payload['token']}\n\n"
        "Ce lien expire 24 heures après son émission et ne sert qu’une fois.\n"
        "Si vous n’avez pas demandé ce compte, ignorez ce message."
    )
    return message


def deliver_one(accounts: Accounts, transport: LocalSMTP) -> bool:
    now = accounts.clock()
    with accounts.factory.begin() as session:
        # Same lock order as resend/verification. SKIP LOCKED lets other workers take other users.
        candidate = session.execute(
            select(User, EmailOutbox.id)
            .join(
                EmailOutbox,
                EmailOutbox.user_id == User.id,
            )
            .where(EmailOutbox.state == "pending", EmailOutbox.next_attempt_at <= now)
            .order_by(EmailOutbox.next_attempt_at, EmailOutbox.id)
            .with_for_update(of=User, skip_locked=True)
            .limit(1)
        ).first()
        if candidate is None:
            return False
        user, identifier = candidate
        row = session.get(EmailOutbox, identifier, with_for_update=True)
        if row.state != "pending" or row.next_attempt_at > now:
            return True
        token = session.get(AccountToken, row.token_id)
        if (
            now >= row.expires_at
            or now >= token.expires_at
            or not token.active
            or user.status != "active"
            or user.email_verified_at is not None
        ):
            row.state, row.payload_ciphertext = "cancelled", None
            return True
        row.attempts += 1
        try:
            payload = json.loads(accounts.cipher().decrypt(row.payload_ciphertext.encode()))
            if (
                UUID(payload["outbox_id"]) != row.id
                or UUID(payload["user_id"]) != user.id
                or UUID(payload["token_id"]) != token.id
                or payload["recipient"] != user.email
                or token_digest(payload["token"]) != token.digest
            ):
                raise ValueError("Outbox binding mismatch")
            transport.send(build_message(row, payload, accounts.settings.public_origin))
        except (OSError, smtplib.SMTPException, InvalidToken, PublicError, ValueError, KeyError):
            row.next_attempt_at = now + timedelta(seconds=min(300, 2 ** min(row.attempts, 8)))
            # Do not persist exception strings: they may include SMTP recipients or payloads.
            return True
        row.state = "sent"
        row.sent_at = accounts.clock()
        row.payload_ciphertext = None
        return True


def prune(accounts: Accounts) -> None:
    now = accounts.clock()
    with accounts.factory.begin() as session:
        session.execute(
            update(MfaChallenge).where(MfaChallenge.expires_at <= now).values(encrypted_secret=None)
        )
        session.execute(
            delete(MfaChallenge).where(MfaChallenge.expires_at < now - timedelta(days=1))
        )
        session.execute(
            delete(MfaRecoverySession).where(
                MfaRecoverySession.expires_at < now - timedelta(days=1)
            )
        )
        session.execute(delete(AuthFailure).where(AuthFailure.updated_at < now - timedelta(days=1)))
        session.execute(
            delete(LoginChallenge).where(LoginChallenge.expires_at < now - timedelta(days=1))
        )
        session.execute(
            delete(SecurityEvent).where(SecurityEvent.created_at < now - timedelta(days=90))
        )
        session.execute(
            delete(AbuseCounter).where(AbuseCounter.window_at < now - timedelta(days=1))
        )
        session.execute(
            update(EmailOutbox)
            .where(
                EmailOutbox.state == "pending",
                EmailOutbox.expires_at <= now,
            )
            .values(state="cancelled", payload_ciphertext=None)
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be between 1 and 1000")
    settings = Settings()
    engine = create_database_engine(settings)
    accounts = Accounts(create_session_factory(engine), settings)
    transport = LocalSMTP(settings)
    try:
        while True:
            try:
                prune(accounts)
                prune_security(accounts)
                processed = 0
                while processed < args.limit:
                    progressed = False
                    for deliver in (deliver_security_one, deliver_one):
                        if processed >= args.limit:
                            break
                        if deliver(accounts, transport):
                            processed += 1
                            progressed = True
                    if not progressed:
                        break
                print(json.dumps({"processed": processed}), flush=True)
            except SQLAlchemyError:
                print(json.dumps({"status": "accounts_unavailable"}), flush=True)
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                break
            time.sleep(settings.mail_poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
