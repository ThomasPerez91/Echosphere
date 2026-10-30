"""Security email delivery: original deadlines, bound payloads, no private logs."""

import json
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from cryptography.fernet import InvalidToken
from sqlalchemy import select, update

from portal_app.account_security.models import (
    EmailChangeRequest,
    PasswordResetRequest,
    SecurityEmail,
)
from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError, token_digest
from portal_app.sessions.models import PortalSession
from portal_app.sessions.service import alive


def build_security_message(row, payload, origin):
    message = EmailMessage()
    message["From"] = "Echosphere <accounts@echosphere.invalid>"
    message["To"] = payload["recipient"]
    message["Message-ID"] = f"<{row.id}@portal.echosphere.invalid>"
    if row.kind == "password_reset":
        message["Subject"] = "Réinitialisez votre mot de passe Echosphere"
        body = (
            "Lien à usage unique, valable 30 minutes depuis émission :\n"
            f"{origin}/#reset-password={payload['token']}\n"
            "Ignorez ce message si vous n’avez pas fait cette demande."
        )
    elif row.kind in ("email_old", "email_new"):
        side = "ancienne" if row.kind == "email_old" else "nouvelle"
        message["Subject"] = "Confirmez le changement d’adresse Echosphere"
        body = (
            f"Confirmez cette {side} adresse pour la même demande de changement :\n"
            f"{origin}/#confirm-email-change={payload['token']}\n"
            "Les deux confirmations expirent une heure après la création de la demande. "
            "Ignorez si vous n’avez pas demandé ce changement."
        )
    else:
        message["Subject"] = "Votre sécurité Echosphere a été modifiée"
        what = "mot de passe" if row.kind == "password_changed" else "adresse email"
        body = (
            f"Votre {what} a été modifié. Une nouvelle connexion normale est nécessaire.\n"
            f"Opération non reconnue ? Ouvrez le parcours de sécurité : {origin}/#security-alert\n"
            "Aucun rétablissement automatique d’une ancienne adresse n’est effectué."
        )
    message.set_content(body)
    return message


def deliver_security_one(accounts, transport):
    now = accounts.clock()
    with accounts.factory.begin() as session:
        candidate = session.execute(
            select(User, SecurityEmail.id)
            .join(SecurityEmail, SecurityEmail.user_id == User.id)
            .where(SecurityEmail.state == "pending", SecurityEmail.next_attempt_at <= now)
            .order_by(SecurityEmail.next_attempt_at, SecurityEmail.id)
            .with_for_update(of=User, skip_locked=True)
            .limit(1)
        ).first()
        if candidate is None:
            return False
        user, identifier = candidate
        row = session.get(SecurityEmail, identifier, with_for_update=True)
        if row.state != "pending" or row.next_attempt_at > now:
            return True
        valid = now < row.expires_at
        if row.kind == "password_reset":
            reset = session.get(PasswordResetRequest, row.reset_id)
            valid &= (
                reset is not None
                and reset.user_id == user.id
                and reset.active
                and now < reset.expires_at
                and user.status == "active"
                and not user.mfa_enabled
                and not user.platform_privileged
            )
        elif row.kind in ("email_old", "email_new"):
            change = session.get(EmailChangeRequest, row.email_change_id)
            valid &= (
                change is not None
                and change.user_id == user.id
                and change.active
                and now < change.expires_at
            )
            if valid:
                valid = (
                    alive(session.get(PortalSession, change.session_id), now)
                    and user.status == "active"
                    and user.email == change.old_email
                    and not user.mfa_enabled
                    and not user.platform_privileged
                )
        if not valid:
            row.state, row.payload_ciphertext = "cancelled", None
            return True
        row.attempts += 1
        try:
            payload = json.loads(accounts.cipher().decrypt(row.payload_ciphertext.encode()))
            if (
                payload["id"] != str(row.id)
                or payload["user_id"] != str(user.id)
                or payload["kind"] != row.kind
                or token_digest(payload["recipient"]) != row.recipient_digest
                or payload["reset_id"] != (str(row.reset_id) if row.reset_id else None)
                or payload["email_change_id"]
                != (str(row.email_change_id) if row.email_change_id else None)
                or (
                    payload["token"] is not None
                    and token_digest(payload["token"]) != row.token_digest
                )
                or (row.token_digest is None) != (payload["token"] is None)
            ):
                raise ValueError("Security email binding mismatch")
            if row.kind == "password_reset" and (
                token_digest(payload["token"]) != reset.digest or payload["recipient"] != user.email
            ):
                raise ValueError("Reset binding mismatch")
            if row.kind in ("email_old", "email_new"):
                expected = change.old_digest if row.kind == "email_old" else change.new_digest
                recipient = change.old_email if row.kind == "email_old" else change.new_email
                if token_digest(payload["token"]) != expected or recipient != payload["recipient"]:
                    raise ValueError("Email change binding mismatch")
            transport.send(build_security_message(row, payload, accounts.settings.public_origin))
        except (
            OSError,
            smtplib.SMTPException,
            InvalidToken,
            PublicError,
            ValueError,
            KeyError,
            TypeError,
        ):
            row.next_attempt_at = now + timedelta(seconds=min(300, 2 ** min(row.attempts, 8)))
            return True
        row.state, row.sent_at, row.payload_ciphertext = "sent", accounts.clock(), None
        return True


def prune_security(accounts):
    with accounts.factory.begin() as session:
        session.execute(
            update(SecurityEmail)
            .where(SecurityEmail.state == "pending", SecurityEmail.expires_at <= accounts.clock())
            .values(state="cancelled", payload_ciphertext=None)
        )
