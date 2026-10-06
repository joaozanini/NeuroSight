"""Contratos JSON dos pacientes (W06–W08).

Criar e editar chegam em multipart (os campos em JSON no campo `data` e o PDF do TCLE em
`consent_file`), para o cadastro e o termo entrarem juntos, num registro só da auditoria.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Sex = Literal["female", "male", "undisclosed"]
VisionCorrection = Literal["none", "glasses", "contacts"]
PatientStatus = Literal["active", "inactive"]

CODE_RULE = "use até 20 letras, números, ponto, hífen ou sublinhado (ex.: P-016)"


def _today() -> date:
    # Um dia de folga: o servidor fica em UTC e, no Brasil à noite, "hoje" ainda é ontem lá.
    return datetime.now(timezone.utc).date() + timedelta(days=1)


class PatientInput(BaseModel):
    code: str = Field(max_length=20)
    name: str = Field(max_length=120)
    birth_date: date
    sex: Sex
    vision_correction: VisionCorrection
    consent_signed: bool = False
    consent_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("informe o código do participante")
        if not all(c.isascii() and (c.isalnum() or c in "._-") for c in value) or not value[0].isalnum():
            raise ValueError(CODE_RULE)
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("informe o nome completo")
        return value

    @field_validator("birth_date")
    @classmethod
    def _birth(cls, value: date) -> date:
        if value > _today() or value.year < 1900:
            raise ValueError("informe uma data de nascimento válida")
        return value

    @field_validator("consent_date")
    @classmethod
    def _consent(cls, value: date | None) -> date | None:
        if value is not None and (value > _today() or value.year < 1900):
            raise ValueError("informe uma data de assinatura válida")
        return value

    @field_validator("notes")
    @classmethod
    def _notes(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None

    @model_validator(mode="after")
    def _signature(self) -> "PatientInput":
        if self.consent_signed and self.consent_date is None:
            raise ValueError("informe a data da assinatura do termo")
        if not self.consent_signed:
            self.consent_date = None
        return self


class StatusChange(BaseModel):
    status: PatientStatus


class NextCode(BaseModel):
    code: str


class PatientRow(BaseModel):
    """Linha da W06."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    birth_date: date
    status: PatientStatus
    sessions_count: int = 0
    last_session_at: datetime | None = None


class PatientCounts(BaseModel):
    active: int
    inactive: int


class PatientPage(BaseModel):
    items: list[PatientRow]
    total: int
    page: int
    page_size: int
    # Cadastro inteiro, sem a busca: o subtítulo "15 pacientes cadastrados".
    counts: PatientCounts


class ConsentFile(BaseModel):
    name: str
    size: int


class PatientSession(BaseModel):
    """Linha do "Histórico de sessões" (W08): só as sessões que a pessoa logada pode ver."""

    id: str
    title: str
    date: datetime
    owner_name: str
    stimuli_count: int
    status: str


class PatientDetail(BaseModel):
    id: str
    code: str
    name: str
    birth_date: date
    sex: Sex
    vision_correction: VisionCorrection
    consent_signed: bool
    consent_date: date | None
    consent_file: ConsentFile | None
    notes: str | None
    status: PatientStatus
    created_at: datetime
    created_by_name: str | None
    sessions_count: int
    sessions: list[PatientSession]
