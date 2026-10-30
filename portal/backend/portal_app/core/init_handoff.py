"""Local signing material: Portal private key, Game public-only volume; separate from mTLS."""

import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def initialize(private, public):
    private.parent.mkdir(parents=True, exist_ok=True)
    public.parent.mkdir(parents=True, exist_ok=True)
    if private.exists():
        if private.is_symlink() or stat.S_IMODE(private.stat().st_mode) != 0o600:
            raise RuntimeError("Handoff private key requires a regular private 0600 file")
        key = serialization.load_pem_private_key(private.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError("Invalid handoff signing key")
    else:
        key = Ed25519PrivateKey.generate()
        descriptor = os.open(private, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
        os.chown(private, 1000, 1000)
    wire = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if public.exists():
        if public.read_bytes() != wire:
            raise RuntimeError("Handoff public key mismatch; explicit rotation required")
    else:
        descriptor = os.open(public, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(descriptor, "wb") as target:
            target.write(wire)


if __name__ == "__main__":
    initialize(Path("/run/portal-handoff/signing.pem"), Path("/run/game-handoff/local-v1.pem"))
