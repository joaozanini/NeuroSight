"""Contratos JSON do Início (W04) e do selo de sessões do menu."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .session import SessionStatus

DataStatus = Literal["none", "waiting", "processing", "failed", "ready"]


class Trend(BaseModel):
    """Um número do mês, o do mesmo trecho do mês anterior e a linha das últimas 8 semanas."""

    # Contagens inteiras; o tempo de coleta, em segundos com uma casa.
    value: int | float
    previous: int | float
    series: list[int | float]


class AwaitingKpi(BaseModel):
    """"Aguardando dados": quantas agora e a mais recente, com o pé em que estão os dados."""

    value: int
    series: list[int]
    latest_id: str | None
    latest_title: str | None
    latest_data_status: DataStatus | None


class UsersKpi(BaseModel):
    """"Usuários ativos": ativos, convites pendentes e ativos cadastrados neste mês."""

    active: int
    invited: int
    added: int
    series: list[int]


class AuditKpi(BaseModel):
    """"Registros na auditoria hoje", ontem até a mesma hora, o último de hoje e os últimos 8 dias."""

    today: int
    yesterday: int
    last_at: datetime | None
    series: list[int]


class AttentionItem(BaseModel):
    """Sessão em andamento ou aguardando dados ("Precisam de atenção")."""

    id: str
    title: str
    status: SessionStatus
    patient_code: str
    owner_name: str
    started_at: datetime | None
    ended_at: datetime | None
    data_status: DataStatus
    # Responsável com "Criar e executar sessões": a sessão em andamento abre o controle.
    can_run: bool


class RecentSession(BaseModel):
    id: str
    title: str
    patient_code: str
    owner_name: str
    date: datetime
    status: SessionStatus
    stimuli_count: int


class AuditLine(BaseModel):
    id: int
    created_at: datetime
    user_name: str | None
    text: str


class Dashboard(BaseModel):
    # admin: o laboratório (as sessões que a pessoa vê, usuários e auditoria); researcher: as
    # sessões em que a pessoa é a responsável.
    view: Literal["admin", "researcher"]
    badge: int
    # Nome do mês corrente e do anterior ("outubro", "setembro"), no fuso pedido.
    month: str
    previous_month: str
    sessions: Trend
    awaiting: AwaitingKpi
    patients: Trend | None = None
    collection_seconds: Trend | None = None
    users: UsersKpi | None = None
    audit: AuditKpi | None = None
    attention: list[AttentionItem]
    recent: list[RecentSession]
    audit_entries: list[AuditLine] | None = None


class Badge(BaseModel):
    sessions: int
