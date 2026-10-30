"""Persistent progressive cooldown: early retries do not extend the cooldown."""

from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portal_app.accounts.models import SecurityEvent, User
from portal_app.accounts.security import PublicError, token_digest
from portal_app.mfa.models import AuthFailure, MfaRecoverySession
from portal_app.sessions.models import PortalSession


@contextmanager
def attempt(accounts, operation, peer, subject, *, email_key=None, session_digest=None):
    now = accounts.clock()
    keys = [f"{operation}:ip:{token_digest(peer)}", f"{operation}:account:{token_digest(subject)}"]
    with accounts.factory() as session:
        if session.scalar(
            select(AuthFailure.key).where(AuthFailure.key.in_(keys), AuthFailure.retry_after > now)
        ):
            raise PublicError("rate_limited", 429)
    try:
        yield
    except PublicError as error:
        if error.code not in (
            "invalid_credentials",
            "invalid_mfa",
            "reauthentication_required",
            "invalid_recovery",
        ):
            raise
        now = accounts.clock()
        with accounts.factory.begin() as session:
            user_id = None
            if email_key is not None:
                user_id = session.scalar(select(User.id).where(User.email_key == email_key))
            elif session_digest is not None:
                for model in (PortalSession, MfaRecoverySession):
                    user_id = session.scalar(
                        select(model.user_id).where(model.digest == session_digest)
                    )
                    if user_id:
                        break
            if user_id:
                session.add(
                    SecurityEvent(user_id=user_id, kind=f"{operation}_failed", created_at=now)
                )
            for key in keys:
                session.execute(
                    insert(AuthFailure)
                    .values(key=key, failures=0, updated_at=now, retry_after=now)
                    .on_conflict_do_nothing()
                )
                row = session.get(AuthFailure, key, with_for_update=True)
                row.failures = (
                    1 if row.updated_at < now - timedelta(minutes=15) else min(row.failures + 1, 20)
                )
                delay = min(
                    accounts.settings.auth_delay_max_ms,
                    accounts.settings.auth_delay_base_ms * 2 ** (row.failures - 1),
                )
                row.updated_at, row.retry_after = now, now + timedelta(milliseconds=delay)
        raise
