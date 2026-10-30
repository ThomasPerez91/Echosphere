import json
import socketserver
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from email import message_from_bytes
from threading import Thread

import pytest
from sqlalchemy import select

from portal_app.accounts.models import AccountToken, EmailOutbox, User
from portal_app.delivery.worker import LocalSMTP, deliver_one, prune

pytestmark = pytest.mark.integration
PASSWORD = "C02 strong test phrase 2026 !"


class CaptureSMTP:
    def __init__(self, fail=False):
        self.fail, self.messages = fail, []

    def send(self, message):
        self.messages.append(message)
        if self.fail:
            raise OSError("private SMTP error must not be logged")


def row(accounts):
    with accounts.factory() as session:
        return session.scalar(select(EmailOutbox).where(EmailOutbox.state == "pending"))


def test_delivery_acceptance_and_payload_erasure(accounts):
    accounts.register("player@example.org", PASSWORD, "peer")
    original = row(accounts)
    transport = CaptureSMTP()
    assert deliver_one(accounts, transport)
    message = transport.messages[0]
    assert PASSWORD not in message.as_string()
    assert f"<{original.id}@portal.echosphere.invalid>" == message["Message-ID"]
    assert accounts.settings.public_origin + "/#verify-email=" in message.get_content()
    with accounts.factory() as session:
        stored = session.get(EmailOutbox, original.id)
        assert stored.state == "sent" and stored.payload_ciphertext is None
        assert stored.attempts == 1
    assert not deliver_one(accounts, transport)


def test_smtp_failure_retry_keeps_original_deadline_and_message_id(accounts, caplog):
    accounts.register("player@example.org", PASSWORD, "peer")
    original = row(accounts)
    transport = CaptureSMTP(fail=True)
    assert deliver_one(accounts, transport)
    stored = row(accounts)
    assert stored.attempts == 1 and stored.expires_at == original.expires_at
    assert stored.payload_ciphertext == original.payload_ciphertext
    assert not deliver_one(accounts, transport)
    accounts.test_clock[0] += timedelta(seconds=3)
    transport.fail = False
    assert deliver_one(accounts, transport)
    assert transport.messages[0]["Message-ID"] == transport.messages[1]["Message-ID"]
    assert PASSWORD not in caplog.text and "private SMTP" not in caplog.text


def test_two_workers_cannot_send_the_same_pending_row(accounts):
    accounts.register("player@example.org", PASSWORD, "peer")
    transport = CaptureSMTP()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: deliver_one(accounts, transport), range(2)))
    assert len(transport.messages) == 1


def test_expired_mail_is_cancelled_without_smtp_or_new_lifetime(accounts):
    accounts.register("player@example.org", PASSWORD, "peer")
    accounts.test_clock[0] += timedelta(hours=24)
    transport = CaptureSMTP()
    assert deliver_one(accounts, transport)
    assert transport.messages == []
    with accounts.factory() as session:
        stored = session.scalar(select(EmailOutbox))
        assert stored.state == "cancelled" and stored.payload_ciphertext is None
        assert session.scalar(select(User.email_verified_at)) is None


def test_swapped_or_tampered_payload_is_never_sent(accounts):
    accounts.register("player@example.org", PASSWORD, "peer")
    identifier = row(accounts).id
    with accounts.factory.begin() as session:
        stored = session.get(EmailOutbox, identifier)
        payload = json.loads(accounts.cipher().decrypt(stored.payload_ciphertext.encode()))
        payload["recipient"] = "other@example.org"
        stored.payload_ciphertext = accounts.cipher().encrypt(json.dumps(payload).encode()).decode()
    transport = CaptureSMTP()
    assert deliver_one(accounts, transport)
    assert transport.messages == []
    assert row(accounts).state == "pending"


def test_prune_expires_payload_but_keeps_token_proof(accounts):
    accounts.register("player@example.org", PASSWORD, "peer")
    accounts.test_clock[0] += timedelta(hours=24)
    prune(accounts)
    with accounts.factory() as session:
        assert session.scalar(select(EmailOutbox.payload_ciphertext)) is None
        assert session.scalar(select(AccountToken)) is not None


class SMTPReceiver(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 local test receiver\r\n")
        while line := self.rfile.readline():
            command = line.split(b" ", 1)[0].strip().upper()
            if command in (b"EHLO", b"HELO"):
                self.wfile.write(b"250 localhost\r\n")
            elif command in (b"MAIL", b"RCPT", b"RSET"):
                self.wfile.write(b"250 OK\r\n")
            elif command == b"DATA":
                self.wfile.write(b"354 Send message\r\n")
                data = bytearray()
                while (line := self.rfile.readline()) != b".\r\n":
                    if not line:
                        return
                    data.extend(line[1:] if line.startswith(b"..") else line)
                self.server.messages.append(message_from_bytes(bytes(data)))
                self.wfile.write(b"250 Accepted\r\n")
            elif command == b"QUIT":
                self.wfile.write(b"221 Bye\r\n")
                return
            else:
                self.wfile.write(b"500 Unsupported\r\n")


def test_real_smtp_transport_recovers_after_receiver_outage(accounts):
    accounts.register("player@example.org", PASSWORD, "peer")
    # Reserve a free port without listening: the first delivery must fail durably.
    with socketserver.TCPServer(("127.0.0.1", 0), SMTPReceiver, bind_and_activate=False) as probe:
        probe.server_bind()
        port = probe.server_address[1]
    settings = accounts.settings.model_copy(
        update={
            "mail_transport": "smtp_local",
            "mail_host": "127.0.0.1",
            "mail_port": port,
        }
    )
    assert deliver_one(accounts, LocalSMTP(settings))
    assert row(accounts).attempts == 1
    accounts.test_clock[0] += timedelta(seconds=3)
    with socketserver.TCPServer(("127.0.0.1", port), SMTPReceiver) as server:
        server.messages = []
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assert deliver_one(accounts, LocalSMTP(settings))
        finally:
            server.shutdown()
            thread.join(timeout=5)
        assert len(server.messages) == 1
        assert PASSWORD not in server.messages[0].as_string()
    with accounts.factory() as session:
        delivered = session.scalar(select(EmailOutbox))
        assert delivered.state == "sent" and delivered.attempts == 2
        assert delivered.payload_ciphertext is None
