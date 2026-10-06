"""Óculos que já se conectaram ao servidor (Fase 4, docs/protocolo-oculos.md).

O óculos se identifica pelo `deviceId` que ele mesmo gera e guarda; a chave é uma só para todos
(QUESTPRO_DEVICE_KEY). A linha é criada no primeiro `hello` e atualizada a cada conexão. Quem está
online agora, o código de pareamento e a sessão vinculada ficam só em memória (services/live_hub.py).
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UtcDateTime, utcnow

DEVICE_ID_PATTERN = r"^[A-Za-z0-9._-]{1,64}$"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    last_seen_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
