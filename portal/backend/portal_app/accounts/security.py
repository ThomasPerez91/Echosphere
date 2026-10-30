"""Password and verification primitives. No credentials or search suffixes are logged."""

import hashlib
import secrets
from contextlib import contextmanager
from threading import BoundedSemaphore

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from email_validator import EmailNotValidError, validate_email


class PublicError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def normalize_email(value: str) -> tuple[str, str]:
    try:
        valid = validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        raise PublicError("invalid_request") from None
    # Preserve SMTP local-part spelling for delivery; casefold only the account lookup key.
    address = f"{valid.local_part}@{valid.ascii_domain}"
    return address, address.casefold()


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class PwnedPasswords:
    """HIBP range API: only a five-character SHA-1 prefix leaves Portal over TLS."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def compromised(self, password: str) -> bool:
        fingerprint = (
            hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
        )
        try:
            with httpx.Client(timeout=3, trust_env=False, transport=self.transport) as client:
                with client.stream(
                    "GET",
                    f"https://api.pwnedpasswords.com/range/{fingerprint[:5]}",
                    headers={"Add-Padding": "true", "User-Agent": "Echosphere-Portal"},
                ) as response:
                    if response.status_code != 200:
                        raise PublicError("temporarily_unavailable", 503)
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 262144:
                            raise PublicError("temporarily_unavailable", 503)
            lines = body.decode("ascii").splitlines()
            if not lines:
                raise PublicError("temporarily_unavailable", 503)
            found = False
            for line in lines:
                suffix, count = line.split(":")
                if len(suffix) != 35 or any(c not in "0123456789ABCDEF" for c in suffix.upper()):
                    raise ValueError("Invalid range response")
                occurrences = int(count)
                if occurrences < 0:
                    raise ValueError("Invalid range response")
                found |= secrets.compare_digest(suffix.upper(), fingerprint[5:]) and occurrences > 0
            return found
        except (httpx.HTTPError, UnicodeError, ValueError):
            raise PublicError("temporarily_unavailable", 503) from None


class Passwords:
    def __init__(self, checker: PwnedPasswords | None = None):
        self.hasher = PasswordHasher(
            memory_cost=65536, time_cost=3, parallelism=1, hash_len=32, salt_len=16, type=Type.ID
        )
        self.checker = checker if checker is not None else PwnedPasswords()
        self.slots = BoundedSemaphore(2)
        self.dummy = self.hasher.hash(secrets.token_urlsafe(32))

    @contextmanager
    def bounded(self):
        if not self.slots.acquire(blocking=False):
            raise PublicError("temporarily_unavailable", 503)
        try:
            yield
        finally:
            self.slots.release()

    def new_hash(self, value: str) -> str:
        if not 15 <= len(value) <= 128:
            raise PublicError("password_rejected")
        with self.bounded():
            if self.checker.compromised(value):
                raise PublicError("password_rejected")
            return self.hasher.hash(value)

    def verify(self, value: str, saved: str | None) -> bool:
        with self.bounded():
            try:
                return self.hasher.verify(saved or self.dummy, value) and saved is not None
            except (VerificationError, InvalidHashError):
                return False
