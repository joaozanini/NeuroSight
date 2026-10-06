"""Pacientes (W06–W08): o cadastro a que as sessões ficam vinculadas. O paciente não usa o site.

O código (P-NNN) identifica o paciente nas análises e exportações, sem expor o nome; fica em
maiúsculas e é único. Pacientes não são excluídos, só inativados: o inativo sai das listas e não
recebe novas sessões, mas as sessões e os dados coletados continuam guardados.

O TCLE assinado fica em disco (`consent_file_key`, relativo à pasta de mídia) e só sai por uma
rota que exige login.
"""
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UtcDateTime, new_id, utcnow
from .user import User

SEXES = ("female", "male", "undisclosed")
VISION_CORRECTIONS = ("none", "glasses", "contacts")
PATIENT_STATUSES = ("active", "inactive")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_date = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)  # female | male | undisclosed
    # Óculos de grau ou lentes de contato (interfere no eye tracking): none | glasses | contacts.
    vision_correction: Mapped[str] = mapped_column(String(20), nullable=False)

    # Termo de consentimento (TCLE). Sem assinatura não há data nem PDF.
    consent_signed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_date = mapped_column(Date, nullable=True)
    consent_file_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)

    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    updated_at = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_by: Mapped[User | None] = relationship(lazy="joined")
