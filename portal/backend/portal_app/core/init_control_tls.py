"""Development PKI only. Separate volumes; no workload receives a CA private key."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def write(path, data, *, private=False, owner=1000):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    if os.geteuid() == 0:
        os.chown(path, owner, owner)


def key_bytes(key):
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def ca(root, name):
    key_path, cert_path = root / (name + ".key"), root / (name + ".pem")
    if key_path.exists() or cert_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if key.public_key().public_numbers() != cert.public_key().public_numbers():
            raise RuntimeError("Development CA key mismatch")
        return key, cert
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Echosphere development " + name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    write(key_path, key_bytes(key), private=True, owner=0)
    write(cert_path, cert.public_bytes(serialization.Encoding.PEM), owner=0)
    return key, cert


def leaf(directory, basename, common_name, authority, *, client=False):
    key_path, cert_path = directory / (basename + ".key"), directory / (basename + ".pem")
    if key_path.exists() or cert_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if (
            key.public_key().public_numbers() != cert.public_key().public_numbers()
            or cert.not_valid_after_utc <= datetime.now(UTC)
        ):
            raise RuntimeError("Development certificate needs explicit operator renewal")
        return cert
    key = ec.generate_private_key(ec.SECP256R1())
    ca_key, ca_cert = authority
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH]
            ),
            critical=True,
        )
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    write(key_path, key_bytes(key), private=True)
    write(cert_path, cert.public_bytes(serialization.Encoding.PEM))
    return cert


def copy_public(path, cert):
    data = cert.public_bytes(serialization.Encoding.PEM)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError("Refusing implicit trust replacement")
    else:
        write(path, data)


def initialize(
    root=Path("/run/control-ca"), game=Path("/run/game-control"), portal=Path("/run/portal-control")
):
    server_ca = ca(root, "game-server-ca")
    client_ca = ca(root, "portal-client-ca")
    leaf(game, "server", "game-control", server_ca)
    client = leaf(portal, "client", "portal-control", client_ca, client=True)
    copy_public(portal / "game-ca.pem", server_ca[1])
    copy_public(game / "portal-ca.pem", client_ca[1])
    copy_public(game / "portal-client.pem", client)


if __name__ == "__main__":
    initialize()
