"""E-mails do site (convite e redefinição de senha) por SMTP.

Sem QUESTPRO_SMTP_HOST nada é enviado: quem chamou recebe False e decide o que fazer (o admin vê
o link na tela para copiar; o "esqueci minha senha" deixa o link no log do servidor). No compose
de desenvolvimento o SMTP é o Mailpit.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from ..config import settings
from . import tokens

logger = logging.getLogger(__name__)


def send(to_name: str, to_email: str, subject: str, body: str) -> bool:
    """Envia em texto puro. True se o servidor SMTP aceitou a mensagem."""
    if not settings.smtp_enabled:
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = formataddr((to_name, to_email))
    msg["Subject"] = subject
    msg.set_content(body)

    security = settings.smtp_security.lower()
    try:
        if security == "ssl":
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout,
                                      context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout)
        with server:
            if security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except (OSError, smtplib.SMTPException):
        logger.exception("falha ao enviar e-mail para %s (%s)", to_email, subject)
        return False
    logger.info("e-mail enviado para %s: %s", to_email, subject)
    return True


def _validity(kind: str) -> str:
    hours = tokens.link_hours(kind)
    if hours % 24 == 0:
        days = hours // 24
        return f"{days} dia" if days == 1 else f"{days} dias"
    return f"{hours} hora" if hours == 1 else f"{hours} horas"


def send_invite(name: str, email: str, link: str, invited_by: str | None) -> bool:
    by = f"{invited_by} criou" if invited_by else "Foi criada"
    body = (
        f"Olá, {name}.\n\n"
        f"{by} uma conta para você no NeuroSight, a plataforma de rastreamento ocular e emocional "
        f"do laboratório.\n\n"
        f"Para começar, abra o link abaixo e crie a sua senha:\n{link}\n\n"
        f"O link vale por {_validity('invite')} e só pode ser usado uma vez. Se ele expirar, peça um "
        f"novo convite ao administrador do sistema.\n"
    )
    return send(name, email, "Seu acesso ao NeuroSight", body)


def send_reset(name: str, email: str, link: str) -> bool:
    body = (
        f"Olá, {name}.\n\n"
        f"Recebemos um pedido para criar uma nova senha para a sua conta no NeuroSight.\n\n"
        f"Abra o link abaixo para escolher a senha nova:\n{link}\n\n"
        f"O link vale por {_validity('reset')} e só pode ser usado uma vez. A senha atual continua "
        f"valendo até você usar o link. Se não foi você que pediu, ignore este e-mail.\n"
    )
    return send(name, email, "Nova senha do NeuroSight", body)
