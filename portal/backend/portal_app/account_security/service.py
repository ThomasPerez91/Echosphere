"""Single-use account proofs, atomic credential changes and durable notifications."""

import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from portal_app.account_security.models import (
    AccountRevocation,
    EmailChangeRequest,
    PasswordResetRequest,
    SecurityEmail,
    StepUpGrant,
)
from portal_app.accounts.models import (
    AccountToken,
    EmailOutbox,
    PasswordCredential,
    SecurityEvent,
    User,
)
from portal_app.accounts.security import PublicError, normalize_email, token_digest
from portal_app.sessions.models import PortalSession
from portal_app.sessions.service import Sessions, alive, check_csrf, valid_secret


def password_only(user):
    # C05 must replace this guard with real MFA/WebAuthn verification, never a bypass.
    if user.mfa_enabled or user.platform_privileged:
        raise PublicError("additional_proof_required", 403)


def binding(raw, action, parameters):
    value = json.dumps(
        ["account-action-v1", action, parameters], sort_keys=True, separators=(",", ":")
    )
    return hmac.new(raw.encode(), value.encode(), hashlib.sha256).hexdigest()


class AccountSecurity:
    def __init__(self, accounts):
        self.accounts = accounts
        self.sessions = Sessions(accounts)

    def audit(self, session, user, kind, now):
        session.add(SecurityEvent(user_id=user.id, kind=kind, created_at=now))

    def mail(
        self, session, user, kind, recipient, now, expires=None, token=None, reset=None, change=None
    ):
        row = SecurityEmail(
            id=uuid4(),
            user_id=user.id,
            kind=kind,
            reset_id=reset.id if reset else None,
            email_change_id=change.id if change else None,
            recipient_digest=token_digest(recipient),
            token_digest=token_digest(token) if token else None,
            state="pending",
            attempts=0,
            created_at=now,
            next_attempt_at=now,
            expires_at=expires
            or now + timedelta(hours=self.accounts.settings.security_notice_hours),
        )
        payload = {
            "id": str(row.id),
            "user_id": str(user.id),
            "kind": kind,
            "recipient": recipient,
            "token": token,
            "reset_id": str(row.reset_id) if row.reset_id else None,
            "email_change_id": str(row.email_change_id) if row.email_change_id else None,
        }
        row.payload_ciphertext = (
            self.accounts.cipher().encrypt(json.dumps(payload).encode()).decode()
        )
        session.add(row)

    def cancel_resets(self, session, user, now):
        session.execute(
            update(PasswordResetRequest)
            .where(PasswordResetRequest.user_id == user.id, PasswordResetRequest.active)
            .values(active=False, revoked_at=now)
        )
        session.execute(
            update(SecurityEmail)
            .where(
                SecurityEmail.user_id == user.id,
                SecurityEmail.kind == "password_reset",
                SecurityEmail.state == "pending",
            )
            .values(state="cancelled", payload_ciphertext=None)
        )

    def cancel_changes(self, session, user, now):
        session.execute(
            update(EmailChangeRequest)
            .where(EmailChangeRequest.user_id == user.id, EmailChangeRequest.active)
            .values(active=False, revoked_at=now)
        )
        session.execute(
            update(SecurityEmail)
            .where(
                SecurityEmail.user_id == user.id,
                SecurityEmail.kind.in_(["email_old", "email_new"]),
                SecurityEmail.state == "pending",
            )
            .values(state="cancelled", payload_ciphertext=None)
        )

    def revoke_all(self, session, user, reason, now):
        user.security_epoch += 1
        session.execute(
            update(PortalSession)
            .where(PortalSession.user_id == user.id, PortalSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        session.execute(
            update(StepUpGrant)
            .where(
                StepUpGrant.user_id == user.id,
                StepUpGrant.consumed_at.is_(None),
                StepUpGrant.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        session.add(
            AccountRevocation(
                user_id=user.id,
                account_epoch=user.security_epoch,
                reason=reason,
                state="pending",
                created_at=now,
            )
        )
        self.audit(session, user, reason, now)

    def step_up(self, raw, csrf, password, action, parameters, peer):
        check_csrf(raw, csrf)
        info = self.sessions.read(raw)
        self.accounts.limit("security_stepup", peer, info["user"]["id"])
        if action == "email_change":
            address, _ = normalize_email(parameters)
            parameters = address
        elif action == "password_change":
            if not isinstance(parameters, str) or not 15 <= len(parameters) <= 128:
                raise PublicError("password_rejected")
        elif action != "logout_all" or parameters is not None:
            raise PublicError("invalid_request")
        with self.accounts.factory() as session:
            saved = session.scalar(
                select(PasswordCredential.password_hash).where(
                    PasswordCredential.user_id == info["user"]["id"]
                )
            )
        if not self.accounts.passwords.verify(password, saved):
            raise PublicError("reauthentication_required", 403)
        with self.accounts.factory.begin() as session:
            current, user = self.sessions.locked(session, raw)
            password_only(user)
            if session.get(PasswordCredential, user.id).password_hash != saved:
                raise PublicError("reauthentication_required", 403)
            now = self.accounts.clock()
            secret = secrets.token_urlsafe(32)
            session.add(
                StepUpGrant(
                    user_id=user.id,
                    session_id=current.id,
                    device_id=current.device_id,
                    digest=token_digest(secret),
                    action=action,
                    parameters_digest=binding(raw, action, parameters),
                    created_at=now,
                    expires_at=now + timedelta(minutes=5),
                )
            )
            current.last_activity_at = now
            self.audit(session, user, "step_up_issued", now)
            return {"proof": secret, "expires_at": (now + timedelta(minutes=5)).isoformat()}

    def consume(self, session, user, current, raw, proof, action, parameters, now):
        password_only(user)
        if not valid_secret(proof):
            raise PublicError("invalid_step_up", 403)
        grant = session.scalar(select(StepUpGrant).where(StepUpGrant.digest == token_digest(proof)))
        if (
            grant is None
            or grant.user_id != user.id
            or grant.session_id != current.id
            or grant.action != action
            or grant.consumed_at
            or grant.revoked_at
            or now >= grant.expires_at
            or not hmac.compare_digest(grant.parameters_digest, binding(raw, action, parameters))
        ):
            raise PublicError("invalid_step_up", 403)
        grant.consumed_at = now

    def password_change(self, raw, csrf, proof, password, peer):
        check_csrf(raw, csrf)
        self.accounts.limit("security_password_change", peer, token_digest(raw or ""))
        # Prove the authorized parameters before querying a third-party password corpus/KDF.
        with self.accounts.factory() as session:
            current, user = self.sessions.locked(session, raw)
            self.consume(
                session,
                user,
                current,
                raw,
                proof,
                "password_change",
                password,
                self.accounts.clock(),
            )
        saved = self.accounts.passwords.new_hash(password)
        with self.accounts.factory.begin() as session:
            current, user = self.sessions.locked(session, raw)
            now = self.accounts.clock()
            self.consume(session, user, current, raw, proof, "password_change", password, now)
            session.get(PasswordCredential, user.id).password_hash = saved
            session.get(PasswordCredential, user.id).changed_at = now
            self.cancel_resets(session, user, now)
            self.cancel_changes(session, user, now)
            self.revoke_all(session, user, "password_change", now)
            self.mail(session, user, "password_changed", user.email, now)
        return {
            "status": "password_changed",
            "game_revocation": "pending",
            "reauthentication_required": True,
        }

    def logout_all(self, raw, csrf, proof):
        check_csrf(raw, csrf)
        with self.accounts.factory.begin() as session:
            current, user = self.sessions.locked(session, raw)
            now = self.accounts.clock()
            self.consume(session, user, current, raw, proof, "logout_all", None, now)
            self.revoke_all(session, user, "logout_all", now)
        return {
            "status": "portal_logged_out",
            "game_revocation": "pending",
            "reauthentication_required": True,
        }

    def reset_request(self, email, peer):
        _, key = normalize_email(email)
        self.accounts.limit("security_reset_request", peer, key)
        start = time.monotonic()
        try:
            self.accounts.cipher()  # Same configuration failure for unknown/known accounts.
            with self.accounts.factory.begin() as session:
                user = session.scalar(select(User).where(User.email_key == key).with_for_update())
                if (
                    user is None
                    or user.status != "active"
                    or user.mfa_enabled
                    or user.platform_privileged
                ):
                    return
                now = self.accounts.clock()
                self.cancel_resets(session, user, now)
                raw = secrets.token_urlsafe(32)
                reset = PasswordResetRequest(
                    user_id=user.id,
                    digest=token_digest(raw),
                    active=True,
                    created_at=now,
                    expires_at=now + timedelta(minutes=30),
                )
                session.add(reset)
                session.flush()
                self.mail(
                    session,
                    user,
                    "password_reset",
                    user.email,
                    now,
                    reset.expires_at,
                    raw,
                    reset=reset,
                )
                self.audit(session, user, "password_reset_requested", now)
        finally:
            time.sleep(
                max(
                    0,
                    self.accounts.settings.reset_response_floor_ms / 1000
                    - (time.monotonic() - start),
                )
            )

    def reset_confirm(self, token, password, peer):
        self.accounts.limit("security_reset_confirm", peer, token_digest(token))
        with self.accounts.factory() as session:
            request = session.scalar(
                select(PasswordResetRequest).where(
                    PasswordResetRequest.digest == token_digest(token)
                )
            )
            if request is None or not request.active or self.accounts.clock() >= request.expires_at:
                raise PublicError("invalid_recovery")
            identifier = request.user_id
        saved = self.accounts.passwords.new_hash(password)
        with self.accounts.factory.begin() as session:
            user = session.get(User, identifier, with_for_update=True)
            password_only(user)
            request = session.scalar(
                select(PasswordResetRequest).where(
                    PasswordResetRequest.digest == token_digest(token)
                )
            )
            now = self.accounts.clock()
            if user.status != "active" or not request.active or now >= request.expires_at:
                raise PublicError("invalid_recovery")
            request.active, request.consumed_at = False, now
            session.flush()
            self.cancel_resets(session, user, now)
            self.cancel_changes(session, user, now)
            credential = session.get(PasswordCredential, user.id)
            credential.password_hash, credential.changed_at = saved, now
            self.revoke_all(session, user, "password_reset", now)
            self.mail(session, user, "password_changed", user.email, now)
        return {
            "status": "password_reset",
            "game_revocation": "pending",
            "reauthentication_required": True,
        }

    def email_request(self, raw, csrf, proof, email, peer):
        check_csrf(raw, csrf)
        address, key = normalize_email(email)
        self.accounts.limit("security_email_request", peer, token_digest(raw or ""))
        with self.accounts.factory.begin() as session:
            current, user = self.sessions.locked(session, raw)
            now = self.accounts.clock()
            self.consume(session, user, current, raw, proof, "email_change", address, now)
            if key == user.email_key:
                raise PublicError("invalid_request")
            self.cancel_changes(session, user, now)
            old, new = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            change = EmailChangeRequest(
                user_id=user.id,
                session_id=current.id,
                device_id=current.device_id,
                old_email=user.email,
                new_email=address,
                new_email_key=key,
                old_digest=token_digest(old),
                new_digest=token_digest(new),
                active=True,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
            session.add(change)
            session.flush()
            self.mail(
                session, user, "email_old", user.email, now, change.expires_at, old, change=change
            )
            self.mail(
                session, user, "email_new", address, now, change.expires_at, new, change=change
            )
            current.last_activity_at = now
            self.audit(session, user, "email_change_requested", now)
        return {"status": "confirmation_required"}

    def email_confirm(self, token, peer):
        digest = token_digest(token)
        self.accounts.limit("security_email_confirm", peer, digest)
        with self.accounts.factory() as session:
            identifier = session.scalar(
                select(EmailChangeRequest.user_id).where(
                    or_(
                        EmailChangeRequest.old_digest == digest,
                        EmailChangeRequest.new_digest == digest,
                    )
                )
            )
        if identifier is None:
            raise PublicError("invalid_email_confirmation")
        with self.accounts.factory.begin() as session:
            user = session.get(User, identifier, with_for_update=True)
            password_only(user)
            change = session.scalar(
                select(EmailChangeRequest).where(
                    or_(
                        EmailChangeRequest.old_digest == digest,
                        EmailChangeRequest.new_digest == digest,
                    )
                )
            )
            now = self.accounts.clock()
            original = session.get(PortalSession, change.session_id)
            if (
                user.status != "active"
                or not change.active
                or now >= change.expires_at
                or user.email != change.old_email
                or not alive(original, now)
            ):
                raise PublicError("invalid_email_confirmation")
            if digest == change.old_digest:
                if change.old_confirmed_at:
                    raise PublicError("invalid_email_confirmation")
                change.old_confirmed_at = now
            else:
                if change.new_confirmed_at:
                    raise PublicError("invalid_email_confirmation")
                change.new_confirmed_at = now
            if change.old_confirmed_at is None or change.new_confirmed_at is None:
                return {"status": "additional_confirmation_required"}
            # A uniqueness conflict rolls back this proof too, without exposing another account.
            try:
                with session.begin_nested():
                    user.email, user.email_key, user.email_verified_at = (
                        change.new_email,
                        change.new_email_key,
                        now,
                    )
                    session.flush()
            except IntegrityError:
                raise PublicError("email_change_unavailable") from None
            change.active, change.completed_at = False, now
            session.flush()
            self.cancel_changes(session, user, now)
            self.cancel_resets(session, user, now)
            session.execute(
                update(AccountToken)
                .where(AccountToken.user_id == user.id, AccountToken.active)
                .values(active=False, revoked_at=now)
            )
            session.execute(
                update(EmailOutbox)
                .where(EmailOutbox.user_id == user.id, EmailOutbox.state == "pending")
                .values(state="cancelled", payload_ciphertext=None)
            )
            self.revoke_all(session, user, "email_change", now)
            self.mail(session, user, "email_changed_old", change.old_email, now)
            self.mail(session, user, "email_changed_new", change.new_email, now)
        return {
            "status": "email_changed",
            "game_revocation": "pending",
            "reauthentication_required": True,
        }
