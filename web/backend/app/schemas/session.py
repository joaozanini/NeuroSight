"""Contratos JSON das sessões (W12, W13, W16 e W18)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .patient import Sex
from .stimulus import StimulusKind
from .user import Role

SessionStatus = Literal["configured", "running", "awaiting_data", "completed", "interrupted"]
Visibility = Literal["private", "shared", "all"]
# Os dados coletados: nenhum (antes de executar), esperando o óculos terminar de enviar, na fila de
# processamento, falha no processamento ou prontos para a W16 e a W17.
DataStatus = Literal["none", "waiting", "processing", "failed", "ready"]

MAX_STIMULI = 200
# Tempo de tela de uma imagem: de 0,1 s a 1 hora.
MAX_DURATION = 3600


def _required(message: str):
    def check(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(message)
        return value

    return check


def _optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _clean_title(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("informe o título da sessão")
    return value


class SequenceItemInput(BaseModel):
    stimulus_id: str = Field(max_length=32)
    # Só para imagens; em branco, a troca é manual. Nos vídeos é ignorado.
    duration_seconds: float | None = Field(default=None, ge=0.1, le=MAX_DURATION)


class SessionCreate(BaseModel):
    """O que o assistente (W13) manda ao salvar."""

    patient_id: str = Field(max_length=32)
    title: str = Field(max_length=120)
    objective: str = Field(max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    record: bool = True
    stimuli: list[SequenceItemInput] = Field(max_length=MAX_STIMULI)
    # "Duplicar para outro paciente": a sessão copiada.
    duplicated_from_id: str | None = Field(default=None, max_length=32)

    _title = field_validator("title")(_clean_title)
    _objective = field_validator("objective")(_required("descreva o objetivo da sessão"))
    _notes = field_validator("notes")(_optional)

    @field_validator("stimuli")
    @classmethod
    def _stimuli(cls, value: list[SequenceItemInput]) -> list[SequenceItemInput]:
        if not value:
            raise ValueError("adicione pelo menos um estímulo à sequência")
        ids = [item.stimulus_id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError("o mesmo estímulo aparece mais de uma vez na sequência")
        return value


class SessionUpdate(BaseModel):
    """"Editar informações" (W16). A gravação só muda antes de a sessão começar."""

    title: str | None = Field(default=None, max_length=120)
    objective: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    record: bool | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else _clean_title(value)

    @field_validator("objective")
    @classmethod
    def _objective(cls, value: str | None) -> str | None:
        return None if value is None else _required("descreva o objetivo da sessão")(value)

    _notes = field_validator("notes")(_optional)


class VisibilityChange(BaseModel):
    """W18: só o responsável, pesquisadores escolhidos (`user_ids`) ou todos."""

    visibility: Visibility
    user_ids: list[str] = Field(default_factory=list, max_length=500)


class Person(BaseModel):
    id: str
    name: str


class ShareCandidate(Person):
    role: Role
    role_label: str


class SessionRow(BaseModel):
    """Linha da W12."""

    id: str
    title: str
    patient_id: str
    patient_code: str
    owner_id: str
    owner_name: str
    # Início, depois de executada; antes disso, quando foi configurada.
    date: datetime
    status: SessionStatus
    visibility: Visibility


class SessionPage(BaseModel):
    items: list[SessionRow]
    total: int
    page: int
    page_size: int


class SequenceItem(BaseModel):
    position: int
    stimulus_id: str
    name: str
    kind: StimulusKind
    # Arquivado depois de entrar na sessão: continua na sequência, mas não entra em novas.
    archived: bool
    duration_seconds: float | None
    media_duration_seconds: float | None
    thumbnail_url: str


class ExposureRow(BaseModel):
    """Linha de "Estímulos exibidos" (W16), na ordem em que apareceram."""

    seq: int
    position: int
    stimulus_id: str
    name: str
    kind: StimulusKind
    archived: bool
    thumbnail_url: str
    # Segundos desde o início da sessão (relógio do óculos) e tempo na tela.
    on_t: float
    screen_seconds: float


class RecordingFile(BaseModel):
    # none: sessão sem gravação; failed: os frames chegaram, mas o MP4 não pôde ser montado.
    status: Literal["ready", "failed", "none"]
    size_bytes: int | None


class SessionFiles(BaseModel):
    """"Arquivos" da W16."""

    tracking_bytes: int
    recording: RecordingFile


class SessionPatient(BaseModel):
    id: str
    code: str
    # Nome, nascimento e sexo só para quem pode ver pacientes; as análises usam só o código.
    name: str | None
    birth_date: date | None
    sex: Sex | None


class SessionRef(BaseModel):
    id: str
    title: str


class SessionDetail(BaseModel):
    id: str
    type: str
    status: SessionStatus
    end_reason: str | None
    title: str
    objective: str
    notes: str | None
    record: bool
    visibility: Visibility
    shared_with: list[ShareCandidate]
    patient: SessionPatient
    owner: Person
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    date: datetime
    duration_seconds: float | None
    items: list[SequenceItem]
    duplicated_from: SessionRef | None
    data_status: DataStatus
    # O motivo, quando o processamento dos dados falhou.
    data_error: str | None
    exposures: list[ExposureRow]
    files: SessionFiles | None
    # O que a pessoa logada pode fazer com esta sessão.
    can_edit: bool
    can_run: bool
    can_change_visibility: bool
    can_export: bool
