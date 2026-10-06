"""Sessões (W12–W18): o que o óculos vai mostrar a um paciente, configurado no site.

Ciclo do status: Configurada → Em andamento → Aguardando dados → Concluída ou Interrompida. A
sessão nasce Configurada pelo assistente (W13); as outras transições chegam nas fases 4 e 5, com o
motivo do fim em `end_reason` (botão B, interrompida pelo pesquisador, queda).

A sequência (`session_stimuli`) guarda a ordem e, nas imagens, o tempo de tela; sem tempo, a troca
é manual. Vídeos avançam sozinhos ao terminar.

Visibilidade: o responsável sempre vê; `private` é só ele, `shared` inclui os pesquisadores de
`session_shares` e `all` abre para todos. Quem tem "Ver sessões de outros pesquisadores" vê todas.
"""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BigIntPK, UtcDateTime, new_id, utcnow
from .patient import Patient
from .stimulus import Stimulus
from .user import User

SESSION_TYPES = ("media_sequence",)
SESSION_STATUSES = ("configured", "running", "awaiting_data", "completed", "interrupted")
VISIBILITIES = ("private", "shared", "all")
END_REASONS = ("button_b", "interrupted", "disconnected")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # Único tipo por enquanto: "Fluxo de imagens e vídeos".
    type: Mapped[str] = mapped_column(String(30), default="media_sequence", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="configured", index=True, nullable=False)
    end_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Gravar a sessão": o óculos grava o que o paciente viu, junto com o rastreamento.
    record: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    # "Duplicar para outro paciente": a sessão de origem.
    duplicated_from_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)

    created_at = mapped_column(UtcDateTime, default=utcnow, index=True, nullable=False)
    updated_at = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    started_at = mapped_column(UtcDateTime, nullable=True)
    ended_at = mapped_column(UtcDateTime, nullable=True)

    patient: Mapped[Patient] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(lazy="joined")
    duplicated_from: Mapped["Session | None"] = relationship(remote_side=[id], lazy="select")
    items: Mapped[list["SessionStimulus"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="SessionStimulus.position",
        lazy="selectin",
    )
    shares: Mapped[list["SessionShare"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin",
    )


class SessionStimulus(Base):
    """Um estímulo da sequência, na posição em que aparece (a partir de 1)."""

    __tablename__ = "session_stimuli"
    __table_args__ = (UniqueConstraint("session_id", "stimulus_id"),)

    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    stimulus_id: Mapped[str] = mapped_column(ForeignKey("stimuli.id"), index=True, nullable=False)
    # Tempo de tela das imagens, em segundos; vazio = troca manual. Vídeos não têm.
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    session: Mapped[Session] = relationship(back_populates="items")
    stimulus: Mapped[Stimulus] = relationship(lazy="joined")


class SessionShare(Base):
    """Pesquisador escolhido para ver uma sessão compartilhada (W18)."""

    __tablename__ = "session_shares"

    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)

    session: Mapped[Session] = relationship(back_populates="shares")
    user: Mapped[User] = relationship(lazy="joined")


class SessionMarker(Base):
    """Marcação feita pelo pesquisador durante a sessão (W15), com `t` em segundos desde o início.

    Fica só no servidor; a tela ao vivo chega na Fase 4.
    """

    __tablename__ = "session_markers"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    t: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
