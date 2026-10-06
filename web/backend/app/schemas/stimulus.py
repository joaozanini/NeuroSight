"""Contratos JSON dos estímulos (W09–W11)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..services.stimuli import MAX_TAG_LENGTH, clean_tags

StimulusKind = Literal["image", "video"]
StimulusFormat = Literal["jpg", "png", "mp4"]
StimulusStatus = Literal["draft", "active", "archived"]
DeviceStatus = Literal["pending", "processing", "ready", "failed"]

MAX_TAGS = 20


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("informe o nome do estímulo")
    return value


def _clean_description(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _clean_tags(value: list[str]) -> list[str]:
    tags = clean_tags(value)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"use no máximo {MAX_TAGS} etiquetas")
    if any(len(t) > MAX_TAG_LENGTH for t in tags):
        raise ValueError(f"cada etiqueta pode ter até {MAX_TAG_LENGTH} caracteres")
    return tags


class StimulusCard(BaseModel):
    """Cartão da W09 (e linha da biblioteca na W13)."""

    id: str
    name: str
    kind: StimulusKind
    status: StimulusStatus
    tags: list[str]
    duration_seconds: float | None
    thumbnail_url: str


class LibraryCounts(BaseModel):
    total: int
    images: int
    videos: int


class StimulusPage(BaseModel):
    items: list[StimulusCard]
    total: int
    page: int
    page_size: int
    # Biblioteca inteira (sem filtros nem arquivados): "42 estímulos na biblioteca: 30 imagens e 12 vídeos".
    counts: LibraryCounts


class StimulusDraft(BaseModel):
    """Arquivo recém-enviado na W10, ainda fora da biblioteca."""

    id: str
    original_filename: str
    suggested_name: str
    kind: StimulusKind
    format: StimulusFormat
    size_bytes: int
    width: int
    height: int
    duration_seconds: float | None
    thumbnail_url: str


class StimulusInfo(BaseModel):
    name: str = Field(max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list)

    _name = field_validator("name")(_clean_name)
    _description = field_validator("description")(_clean_description)
    _tags = field_validator("tags")(_clean_tags)


class StimulusSaveItem(StimulusInfo):
    id: str = Field(max_length=32)


class StimulusSave(BaseModel):
    """"Salvar na biblioteca": os rascunhos enviados, com nome, descrição e etiquetas."""

    items: list[StimulusSaveItem] = Field(min_length=1, max_length=200)


class StimulusUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    _description = field_validator("description")(_clean_description)

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_tags(value)


class StimulusStatusChange(BaseModel):
    """Arquivar ou desarquivar."""

    status: Literal["active", "archived"]


class StimulusSession(BaseModel):
    """Linha do "Usado em N sessões" (W11); as sessões novas chegam na Fase 3."""

    id: str
    title: str
    patient_code: str
    date: datetime


class StimulusDetail(BaseModel):
    id: str
    name: str
    description: str | None
    kind: StimulusKind
    format: StimulusFormat
    status: StimulusStatus
    original_filename: str
    size_bytes: int
    width: int
    height: int
    duration_seconds: float | None
    has_audio: bool | None
    tags: list[str]
    created_at: datetime
    created_by_name: str | None
    thumbnail_url: str
    file_url: str
    device_status: DeviceStatus
    device_error: str | None
    sessions_count: int
    sessions: list[StimulusSession]
    # Só o que nunca foi usado em sessões pode ser excluído; o resto, só arquivado.
    can_delete: bool
