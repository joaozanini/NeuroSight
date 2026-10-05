"""Envio por SMTP: segurança da conexão, login e a mensagem; sem host, nada sai."""
import smtplib

import pytest

from app.config import settings
from app.services import mailer


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port
        self.calls: list[str] = []
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(f"login:{user}")

    def send_message(self, msg):
        self.messages.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.lab.br")
    monkeypatch.setattr(settings, "smtp_user", "robo")
    return FakeSMTP


def test_without_host_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    assert mailer.send("Ana", "ana@lab.br", "Assunto", "Corpo") is False


def test_starttls_login_and_message(smtp):
    assert mailer.send_reset("Ana Souza", "ana@lab.br", "http://site/redefinir-senha?token=abc") is True
    [conn] = smtp.instances
    assert (conn.host, conn.port, conn.calls) == ("smtp.lab.br", 587, ["starttls", "login:robo"])
    [msg] = conn.messages
    assert msg["To"] == "Ana Souza <ana@lab.br>"
    assert msg["Subject"] == "Nova senha do NeuroSight"
    body = msg.get_content()
    assert "http://site/redefinir-senha?token=abc" in body
    assert "vale por 2 horas" in body


def test_no_tls_for_mailpit(smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "none")
    monkeypatch.setattr(settings, "smtp_user", "")
    mailer.send("Ana", "ana@lab.br", "Assunto", "Corpo")
    assert smtp.instances[0].calls == []


def test_smtp_failure_returns_false(smtp, monkeypatch):
    def boom(self, msg):
        raise smtplib.SMTPRecipientsRefused({})

    monkeypatch.setattr(FakeSMTP, "send_message", boom)
    assert mailer.send("Ana", "ana@lab.br", "Assunto", "Corpo") is False
