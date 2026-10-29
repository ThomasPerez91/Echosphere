"""Initialize a local-only outbox key in a private Docker volume. Never print it."""

import os
from pathlib import Path

from cryptography.fernet import Fernet

from portal_app.core.config import Settings


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        Fernet(path.read_bytes().strip())
        return
    with os.fdopen(descriptor, "wb") as target:
        target.write(Fernet.generate_key())
        target.flush()
        os.fsync(target.fileno())


if __name__ == "__main__":
    initialize(Settings().mail_key_file)
