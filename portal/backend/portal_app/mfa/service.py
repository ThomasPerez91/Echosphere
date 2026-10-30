"""MFA ceremonies serialized by account, separate from normal and recovery sessions."""

import json
import secrets
from datetime import timedelta
from uuid import UUID

import pyotp
from sqlalchemy import delete, select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from portal_app.account_security.service import AccountSecurity, binding
from portal_app.accounts.models import PasswordCredential, User
from portal_app.accounts.security import PublicError, normalize_email, token_digest
from portal_app.mfa.crypto import challenge_valid, cipher, decrypt, policy, validate_rp, verify_totp
from portal_app.mfa.models import (
    BackupCode,
    MfaChallenge,
    MfaRecoverySession,
    TotpCredential,
    WebAuthnCredential,
)
from portal_app.mfa.throttle import attempt
from portal_app.sessions.models import LoginChallenge
from portal_app.sessions.service import Sessions, check_csrf, valid_secret

ALGORITHMS = [
    COSEAlgorithmIdentifier.ECDSA_SHA_256,
    COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
]


def enrollment_parameters(kind, name, replace_id=None):
    if (
        kind not in ("totp", "webauthn")
        or not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 80
    ):
        raise PublicError("invalid_request")
    if replace_id is not None:
        try:
            replace_id = str(UUID(str(replace_id)))
        except ValueError:
            raise PublicError("invalid_request") from None
    return {"kind": kind, "name": name.strip(), "replace_id": replace_id}


def removal_parameters(parameters):
    if (
        not isinstance(parameters, dict)
        or set(parameters) != {"kind", "id"}
        or parameters["kind"] not in ("totp", "webauthn")
        or (parameters["kind"] == "totp" and parameters["id"] is not None)
    ):
        raise PublicError("invalid_request")
    if parameters["kind"] == "webauthn":
        try:
            return {"kind": "webauthn", "id": str(UUID(parameters["id"]))}
        except (ValueError, TypeError, AttributeError):
            raise PublicError("invalid_request") from None
    return parameters


def backup_digest(code):
    if not isinstance(code, str):
        raise PublicError("invalid_recovery")
    return token_digest(code.replace("-", "").replace(" ", "").upper())


class Mfa:
    def __init__(self, accounts):
        self.accounts = accounts
        self.sessions, self.security = Sessions(accounts), AccountSecurity(accounts)

    def recovery_locked(self, session, raw):
        if not valid_secret(raw):
            raise PublicError("invalid_recovery", 401)
        identifier = session.scalar(
            select(MfaRecoverySession.user_id).where(MfaRecoverySession.digest == token_digest(raw))
        )
        if identifier is None:
            raise PublicError("invalid_recovery", 401)
        user = session.get(User, identifier, with_for_update=True)
        recovery = session.scalar(
            select(MfaRecoverySession).where(MfaRecoverySession.digest == token_digest(raw))
        )
        if (
            user.status != "active"
            or recovery.completed_at
            or self.accounts.clock() >= recovery.expires_at
            or recovery.epoch != user.security_epoch
        ):
            raise PublicError("invalid_recovery", 401)
        return recovery, user

    def status(self, raw):
        with self.accounts.factory.begin() as session:
            _, user = self.sessions.locked(session, raw)
            keys = list(
                session.scalars(
                    select(WebAuthnCredential)
                    .where(WebAuthnCredential.user_id == user.id)
                    .order_by(WebAuthnCredential.created_at)
                )
            )
            return {
                "enabled": user.mfa_enabled,
                "totp": session.get(TotpCredential, user.id) is not None,
                "credentials": [{"id": str(item.id), "name": item.name} for item in keys],
                "privileged": user.platform_privileged,
            }

    def assertion_options(self, raw, csrf, password, action, parameters, email, peer):
        key = normalize_email(email)[1] if action == "login" else None
        with attempt(
            self.accounts,
            "assert_options",
            peer,
            key or token_digest(raw or ""),
            email_key=key,
            session_digest=None if key else token_digest(raw or ""),
        ):
            return self._assertion_options(raw, csrf, password, action, parameters, email, peer)

    def _assertion_options(self, raw, csrf, password, action, parameters, email, peer):
        check_csrf(raw, csrf)
        self.accounts.limit("security_mfa", peer, email.casefold() if email else token_digest(raw))
        with self.accounts.factory.begin() as session:
            if action == "login":
                _, key = normalize_email(email)
                user = session.scalar(select(User).where(User.email_key == key).with_for_update())
                credential = session.get(PasswordCredential, user.id) if user else None
                if (
                    not self.accounts.passwords.verify(
                        password, credential.password_hash if credential else None
                    )
                    or user.status != "active"
                ):
                    raise PublicError("invalid_credentials", 401)
                pending = session.scalar(
                    select(LoginChallenge).where(LoginChallenge.digest == token_digest(raw))
                )
                if (
                    pending is None
                    or pending.consumed_at
                    or self.accounts.clock() >= pending.expires_at
                ):
                    raise PublicError("login_challenge_expired", 401)
            else:
                _, user = self.sessions.locked(session, raw)
                if not self.accounts.passwords.verify(
                    password, session.get(PasswordCredential, user.id).password_hash
                ):
                    raise PublicError("reauthentication_required", 403)
            policy(session, user, self.accounts)
            keys = list(
                session.scalars(
                    select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
                )
            )
            if not keys:
                raise PublicError("invalid_mfa", 403)
            if action == "email_change":
                parameters = normalize_email(parameters)[0]
            elif action == "mfa_remove":
                parameters = removal_parameters(parameters)
            elif action == "mfa_enroll":
                if not isinstance(parameters, dict):
                    raise PublicError("invalid_request")
                parameters = enrollment_parameters(
                    parameters.get("kind"), parameters.get("name"), parameters.get("replace_id")
                )
            validate_rp(self.accounts)
            options = generate_authentication_options(
                rp_id=self.accounts.settings.webauthn_rp_id,
                allow_credentials=[
                    PublicKeyCredentialDescriptor(id=item.credential_id) for item in keys
                ],
                user_verification=UserVerificationRequirement.REQUIRED,
                timeout=120000,
            )
            now = self.accounts.clock()
            row = MfaChallenge(
                user_id=user.id,
                purpose="assert",
                context_digest=binding(raw, action, parameters),
                epoch=user.security_epoch,
                challenge=options.challenge,
                created_at=now,
                expires_at=now + timedelta(minutes=5),
            )
            session.add(row)
            session.flush()
            return {"challenge_id": str(row.id), "options": json.loads(options_to_json(options))}

    def begin(self, raw, csrf, proof, kind, name, replace_id=None, recovery=False):
        check_csrf(raw, csrf)
        parameters = enrollment_parameters(kind, name, replace_id)
        with self.accounts.factory.begin() as session:
            if recovery:
                owner, user = self.recovery_locked(session, raw)
                if user.platform_privileged and kind != "webauthn":
                    raise PublicError("additional_proof_required", 403)
            else:
                owner, user = self.sessions.locked(session, raw)
                self.security.consume(
                    session,
                    user,
                    owner,
                    raw,
                    proof,
                    "mfa_enroll",
                    parameters,
                    self.accounts.clock(),
                )
            replacing = (
                session.get(WebAuthnCredential, UUID(parameters["replace_id"]))
                if replace_id
                else None
            )
            if replace_id and (
                replacing is None or replacing.user_id != user.id or kind != "webauthn"
            ):
                raise PublicError("factor_not_found", 404)
            keys = list(
                session.scalars(
                    select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
                )
            )
            if kind == "webauthn" and not recovery and len(keys) - int(replacing is not None) >= 5:
                raise PublicError("factor_limit_reached", 409)
            now = self.accounts.clock()
            seed = pyotp.random_base32() if kind == "totp" else None
            options = None
            challenge = secrets.token_bytes(32)
            if kind == "webauthn":
                validate_rp(self.accounts)
                options = generate_registration_options(
                    rp_id=self.accounts.settings.webauthn_rp_id,
                    rp_name="Echosphere",
                    user_id=user.id.bytes,
                    user_name=user.email,
                    challenge=challenge,
                    supported_pub_key_algs=ALGORITHMS,
                    exclude_credentials=[
                        PublicKeyCredentialDescriptor(id=item.credential_id) for item in keys
                    ],
                    authenticator_selection=AuthenticatorSelectionCriteria(
                        user_verification=UserVerificationRequirement.REQUIRED
                    ),
                )
            row = MfaChallenge(
                user_id=user.id,
                purpose="enroll_" + kind,
                context_digest=binding(
                    raw, "recover_enroll" if recovery else "mfa_enroll", parameters
                ),
                epoch=user.security_epoch,
                challenge=challenge,
                name=parameters["name"],
                replace_id=replacing.id if replacing else None,
                encrypted_secret=cipher(self.accounts).encrypt(seed.encode()).decode()
                if seed
                else None,
                created_at=now,
                expires_at=min(now + timedelta(minutes=5), owner.expires_at),
            )
            session.add(row)
            session.flush()
            if not recovery:
                owner.last_activity_at = now
            self.security.audit(session, user, "mfa_enrollment_started", now)
            return {
                "challenge_id": str(row.id),
                "secret": seed,
                "uri": pyotp.TOTP(seed).provisioning_uri(user.email, issuer_name="Echosphere")
                if seed
                else None,
                "options": json.loads(options_to_json(options)) if options else None,
            }

    def fresh_codes(self, session, user, now):
        session.execute(delete(BackupCode).where(BackupCode.user_id == user.id))
        codes = []
        for _ in range(10):
            value = secrets.token_hex(20).upper()
            codes.append("-".join(value[index : index + 8] for index in range(0, 40, 8)))
            session.add(BackupCode(user_id=user.id, digest=backup_digest(value), created_at=now))
        return codes

    def notice(self, session, user, now):
        self.security.mail(session, user, "mfa_changed", user.email, now)
        self.security.audit(session, user, "mfa_changed", now)

    def finish(self, raw, csrf, identifier, supplied, peer, recovery=False):
        check_csrf(raw, csrf)
        self.accounts.limit("security_mfa", peer, token_digest(raw))
        with attempt(
            self.accounts, "mfa", peer, token_digest(raw), session_digest=token_digest(raw)
        ):
            return self._finish(raw, identifier, supplied, recovery)

    def _finish(self, raw, identifier, supplied, recovery):
        with self.accounts.factory.begin() as session:
            owner, user = (
                self.recovery_locked(session, raw)
                if recovery
                else self.sessions.locked(session, raw)
            )
            try:
                row = session.get(MfaChallenge, UUID(identifier))
            except (ValueError, TypeError):
                raise PublicError("invalid_mfa", 403) from None
            if row is None:
                raise PublicError("invalid_mfa", 403)
            kind = row.purpose.removeprefix("enroll_")
            parameters = enrollment_parameters(kind, row.name, row.replace_id)
            now = self.accounts.clock()
            challenge_valid(
                row,
                user,
                binding(raw, "recover_enroll" if recovery else "mfa_enroll", parameters),
                now,
                "enroll_" + kind,
            )
            if recovery and user.platform_privileged and kind != "webauthn":
                raise PublicError("additional_proof_required", 403)
            had_mfa = user.mfa_enabled
            old_totp = session.get(TotpCredential, user.id)
            replacing = session.get(WebAuthnCredential, row.replace_id) if row.replace_id else None
            if row.replace_id and (replacing is None or replacing.user_id != user.id):
                raise PublicError("invalid_mfa", 403)
            verified = None
            if kind == "totp":
                seed = decrypt(self.accounts, row.encrypted_secret)
                step = verify_totp(seed, supplied.get("totp"), now)
            else:
                try:
                    validate_rp(self.accounts)
                    verified = verify_registration_response(
                        credential=supplied.get("credential"),
                        expected_challenge=row.challenge,
                        expected_rp_id=self.accounts.settings.webauthn_rp_id,
                        expected_origin=self.accounts.settings.public_origin,
                        require_user_verification=True,
                        supported_pub_key_algs=ALGORITHMS,
                    )
                except (WebAuthnException, ValueError, KeyError, TypeError, AttributeError):
                    raise PublicError("invalid_mfa", 403) from None
                if session.scalar(
                    select(WebAuthnCredential.id).where(
                        WebAuthnCredential.credential_id == verified.credential_id
                    )
                ):
                    raise PublicError("factor_already_registered", 409)
                keys = list(
                    session.scalars(
                        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
                    )
                )
                if not recovery and len(keys) - int(replacing is not None) >= 5:
                    raise PublicError("factor_limit_reached", 409)
            if recovery:
                session.execute(delete(TotpCredential).where(TotpCredential.user_id == user.id))
                session.execute(
                    delete(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
                )
                session.flush()
                old_totp = None
            elif replacing:
                session.delete(replacing)
                session.flush()
            if kind == "totp":
                if old_totp:
                    old_totp.encrypted_secret, old_totp.last_step, old_totp.created_at = (
                        row.encrypted_secret,
                        step,
                        now,
                    )
                else:
                    session.add(
                        TotpCredential(
                            user_id=user.id,
                            encrypted_secret=row.encrypted_secret,
                            last_step=step,
                            created_at=now,
                        )
                    )
            else:
                session.add(
                    WebAuthnCredential(
                        user_id=user.id,
                        credential_id=verified.credential_id,
                        public_key=verified.credential_public_key,
                        sign_count=verified.sign_count,
                        name=row.name,
                        created_at=now,
                    )
                )
            row.used_at, row.encrypted_secret = now, None
            user.mfa_enabled = True
            codes = self.fresh_codes(session, user, now) if recovery or not had_mfa else []
            global_revoke = (
                recovery
                or not had_mfa
                or bool(replacing)
                or (kind == "totp" and old_totp is not None)
            )
            if global_revoke:
                self.security.cancel_changes(session, user, now)
                self.security.cancel_resets(session, user, now)
                self.security.revoke_all(
                    session,
                    user,
                    "mfa_recovery" if recovery else "mfa_activate" if not had_mfa else "mfa_change",
                    now,
                )
            if recovery:
                owner.completed_at = now
            elif not global_revoke:
                owner.last_activity_at = now
            self.notice(session, user, now)
            return {
                "status": "factor_registered",
                "global_logout": global_revoke,
                "backup_codes": codes,
                "game_revocation": "pending" if global_revoke else "unchanged",
                "privileged_recovery_blocked": user.privilege_recovery_required,
            }

    def manage(self, raw, csrf, proof, action, parameters):
        check_csrf(raw, csrf)
        if action == "mfa_remove":
            parameters = removal_parameters(parameters)
        elif action not in ("mfa_disable", "mfa_backup_codes") or parameters is not None:
            raise PublicError("invalid_request")
        with self.accounts.factory.begin() as session:
            current, user = self.sessions.locked(session, raw)
            now = self.accounts.clock()
            self.security.consume(session, user, current, raw, proof, action, parameters, now)
            if action == "mfa_backup_codes":
                if not user.mfa_enabled:
                    raise PublicError("invalid_request")
                codes = self.fresh_codes(session, user, now)
                current.last_activity_at = now
                self.notice(session, user, now)
                return {
                    "status": "backup_codes_regenerated",
                    "backup_codes": codes,
                    "global_logout": False,
                }
            if action == "mfa_disable":
                if user.platform_privileged:
                    raise PublicError("additional_proof_required", 403)
                session.execute(delete(TotpCredential).where(TotpCredential.user_id == user.id))
                session.execute(
                    delete(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
                )
                user.mfa_enabled = False
            elif action == "mfa_remove":
                kind, identifier = parameters["kind"], parameters.get("id")
                stored = (
                    session.get(TotpCredential, user.id)
                    if kind == "totp"
                    else session.get(WebAuthnCredential, UUID(identifier))
                )
                if stored is None or stored.user_id != user.id:
                    raise PublicError("factor_not_found", 404)
                if user.platform_privileged and kind == "webauthn":
                    from portal_app.mfa.crypto import web_count

                    if web_count(session, user) <= (2 if self.accounts.settings.production else 1):
                        raise PublicError("additional_proof_required", 403)
                session.delete(stored)
                session.flush()
                user.mfa_enabled = (
                    session.get(TotpCredential, user.id) is not None
                    or session.scalar(
                        select(WebAuthnCredential.id)
                        .where(WebAuthnCredential.user_id == user.id)
                        .limit(1)
                    )
                    is not None
                )
            else:
                raise PublicError("invalid_request")
            if not user.mfa_enabled:
                session.execute(delete(BackupCode).where(BackupCode.user_id == user.id))
            self.security.cancel_changes(session, user, now)
            self.security.cancel_resets(session, user, now)
            self.security.revoke_all(
                session, user, "mfa_disable" if not user.mfa_enabled else "mfa_change", now
            )
            self.notice(session, user, now)
            return {"status": "mfa_changed", "global_logout": True, "game_revocation": "pending"}

    def recover(self, email, password, code, challenge_raw, csrf, peer):
        check_csrf(challenge_raw, csrf)
        _, key = normalize_email(email)
        self.accounts.limit("security_mfa_recover", peer, key)
        with attempt(self.accounts, "recovery", peer, key, email_key=key):
            with self.accounts.factory.begin() as session:
                user = session.scalar(select(User).where(User.email_key == key).with_for_update())
                saved = session.get(PasswordCredential, user.id) if user else None
                if (
                    not self.accounts.passwords.verify(
                        password, saved.password_hash if saved else None
                    )
                    or user.status != "active"
                    or not user.mfa_enabled
                ):
                    raise PublicError("invalid_recovery")
                challenge = session.scalar(
                    select(LoginChallenge).where(
                        LoginChallenge.digest == token_digest(challenge_raw)
                    )
                )
                now = self.accounts.clock()
                if challenge is None or challenge.consumed_at or now >= challenge.expires_at:
                    raise PublicError("invalid_recovery")
                backup = session.scalar(
                    select(BackupCode).where(
                        BackupCode.user_id == user.id, BackupCode.digest == backup_digest(code)
                    )
                )
                if backup is None or backup.used_at:
                    raise PublicError("invalid_recovery")
                backup.used_at, challenge.consumed_at = now, now
                # Recovery immediately invalidates the lost factors; no password-only fallback.
                session.execute(delete(TotpCredential).where(TotpCredential.user_id == user.id))
                session.execute(
                    delete(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
                )
                if user.platform_privileged:
                    user.privilege_recovery_required = True
                self.security.cancel_changes(session, user, now)
                self.security.cancel_resets(session, user, now)
                self.security.revoke_all(session, user, "mfa_recovery", now)
                self.notice(session, user, now)
                raw = secrets.token_urlsafe(32)
                session.add(
                    MfaRecoverySession(
                        user_id=user.id,
                        digest=token_digest(raw),
                        epoch=user.security_epoch,
                        created_at=now,
                        expires_at=now + timedelta(minutes=15),
                    )
                )
                return raw
