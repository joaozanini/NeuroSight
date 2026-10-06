"""Início (W04) e selo de sessões do menu: números calculados a cada pedido, direto das tabelas.

Duas visões, pelo perfil: o admin vê o laboratório (as sessões que pode ver, os usuários e a
auditoria); o pesquisador, as sessões em que é o responsável ("Suas sessões recentes", "precisam da
sua atenção"). O selo do menu conta as mesmas sessões de "Precisam de atenção": em andamento ou
aguardando dados.

Os períodos seguem o fuso de quem olha. O mês vai do dia 1 até agora e a variação compara com o
mesmo trecho do mês anterior (de 1 a 6 de outubro contra 1 a 6 de setembro); a auditoria de hoje,
com ontem até a mesma hora. As linhas de tendência mostram as últimas 8 semanas (7 dias corridos
terminando agora) e, na auditoria, os últimos 8 dias.

Uma sessão conta no período em que começou. A linha de "Aguardando dados" é um retrato no fim de cada
semana: as que estavam esperando os dados naquele instante, do fim da execução até o óculos terminar
de enviar (`data_received_at`; o processamento leva segundos). O último ponto é o valor do cartão.

"Últimas ações da auditoria" deixa os logins de fora (são a maioria dos registros e não mudam nada);
o número de registros de hoje conta todos.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..models import AuditLog, Session, User, utcnow
from ..schemas.dashboard import (
    AttentionItem, AuditKpi, AuditLine, AwaitingKpi, Dashboard, RecentSession, Trend, UsersKpi,
)
from . import audit, permissions
from . import sessions as rules

MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
          "outubro", "novembro", "dezembro")
ACTIVE_STATUSES = ("running", "awaiting_data")
EXECUTED_STATUSES = ("running", "awaiting_data", "completed", "interrupted")
TREND_POINTS = 8
RECENT_LIMIT = 5
AUDIT_LIMIT = 5


@dataclass
class Periods:
    now: datetime
    month: tuple[datetime, datetime]
    previous_month: tuple[datetime, datetime]
    today: tuple[datetime, datetime]
    yesterday: tuple[datetime, datetime]
    weeks: list[tuple[datetime, datetime]]
    days: list[tuple[datetime, datetime]]
    month_name: str
    previous_month_name: str


def periods(now: datetime, zone: ZoneInfo) -> Periods:
    """Os intervalos [início, fim) em UTC; os "até agora" terminam logo depois de `now`."""
    local = now.astimezone(zone)
    end = now + timedelta(microseconds=1)
    month_start = datetime.combine(local.date().replace(day=1), time(), zone)
    previous_start = datetime.combine((month_start.date() - timedelta(days=1)).replace(day=1), time(), zone)
    # O mesmo trecho do mês anterior; num mês mais curto, ele acaba no fim do mês.
    previous_end = min(previous_start + (local - month_start), month_start)
    today = datetime.combine(local.date(), time(), zone)
    yesterday = datetime.combine(local.date() - timedelta(days=1), time(), zone)
    days = [datetime.combine(local.date() - timedelta(days=n), time(), zone) for n in range(TREND_POINTS - 1, -1, -1)]

    def utc(start: datetime, stop: datetime) -> tuple[datetime, datetime]:
        return start.astimezone(timezone.utc), stop.astimezone(timezone.utc)

    return Periods(
        now=now,
        month=utc(month_start, end),
        previous_month=utc(previous_start, previous_end),
        today=utc(today, end),
        yesterday=utc(yesterday, yesterday + (local - today)),
        weeks=[(now - timedelta(weeks=n + 1), now - timedelta(weeks=n)) for n in range(TREND_POINTS - 1, -1, -1)],
        days=[utc(start, start + timedelta(days=1)) for start in days],
        month_name=MONTHS[local.month - 1],
        previous_month_name=MONTHS[previous_start.month - 1],
    )


def is_admin_view(user: User) -> bool:
    return user.role == "admin"


def scope(db: DbSession, user: User):
    """As sessões que entram nos números: as visíveis para o admin, as próprias para o pesquisador."""
    return rules.visible_to(db, user) if is_admin_view(user) else Session.owner_id == user.id


def attention_sessions(db: DbSession, user: User) -> list[Session]:
    """Em andamento primeiro, depois aguardando dados; as mais recentes antes."""
    first = case((Session.status == "running", 0), else_=1)
    return list(db.scalars(
        select(Session).where(scope(db, user), Session.status.in_(ACTIVE_STATUSES))
        .order_by(first, func.coalesce(Session.ended_at, Session.started_at).desc(), Session.created_at.desc())
    ))


def badge(db: DbSession, user: User) -> int:
    return db.scalar(
        select(func.count()).select_from(Session).where(scope(db, user), Session.status.in_(ACTIVE_STATUSES))
    ) or 0


@dataclass
class Executed:
    """O que os números precisam de uma sessão executada."""

    status: str
    patient_id: str
    started_at: datetime
    ended_at: datetime | None
    data_received_at: datetime | None

    def started_in(self, period: tuple[datetime, datetime]) -> bool:
        return period[0] <= self.started_at < period[1]

    def awaiting_at(self, instant: datetime) -> bool:
        if self.ended_at is None or self.status == "running":
            return False
        if self.status == "awaiting_data":
            return self.ended_at <= instant
        return self.ended_at <= instant < (self.data_received_at or self.ended_at)


def _executed(db: DbSession, user: User, since: datetime) -> list[Executed]:
    rows = db.execute(
        select(Session.status, Session.patient_id, Session.started_at, Session.ended_at, Session.data_received_at)
        .where(
            scope(db, user), Session.started_at.is_not(None), Session.status.in_(EXECUTED_STATUSES),
            or_(Session.started_at >= since, Session.status == "awaiting_data", Session.data_received_at >= since),
        )
    ).all()
    return [Executed(*row) for row in rows]


def _count(rows: list[Executed], period) -> int:
    return sum(1 for r in rows if r.started_in(period))


def _patients(rows: list[Executed], period) -> int:
    return len({r.patient_id for r in rows if r.started_in(period)})


def _seconds(rows: list[Executed], period) -> float:
    return round(sum((r.ended_at - r.started_at).total_seconds()
                     for r in rows if r.started_in(period) and r.ended_at is not None), 1)


def _trend(rows: list[Executed], p: Periods, measure) -> Trend:
    return Trend(value=measure(rows, p.month), previous=measure(rows, p.previous_month),
                 series=[measure(rows, week) for week in p.weeks])


def _awaiting(rows: list[Executed], attention: list[Session], p: Periods) -> AwaitingKpi:
    waiting = [s for s in attention if s.status == "awaiting_data"]
    latest = waiting[0] if waiting else None
    return AwaitingKpi(
        value=len(waiting),
        series=[sum(1 for r in rows if r.awaiting_at(week[1] - timedelta(microseconds=1))) for week in p.weeks],
        latest_id=latest.id if latest else None,
        latest_title=latest.title if latest else None,
        latest_data_status=rules.data_status(latest)[0] if latest else None,
    )


def _users(db: DbSession, p: Periods) -> UsersKpi:
    counts = dict(db.execute(select(User.status, func.count()).group_by(User.status)).all())
    # Sem o histórico de quando cada um passou a ativo, a linha usa a data do cadastro.
    active = list(db.scalars(select(User.created_at).where(User.status == "active")))
    return UsersKpi(
        active=counts.get("active", 0),
        invited=counts.get("invited", 0),
        added=sum(1 for at in active if at >= p.month[0]),
        series=[sum(1 for at in active if at < week[1]) for week in p.weeks],
    )


def _audit_kpi(db: DbSession, p: Periods) -> AuditKpi:
    times = list(db.scalars(select(AuditLog.created_at).where(AuditLog.created_at >= p.days[0][0])))

    def count(period) -> int:
        return sum(1 for at in times if period[0] <= at < period[1])

    today = [at for at in times if at >= p.today[0]]
    return AuditKpi(
        today=len(today), yesterday=count(p.yesterday), last_at=max(today, default=None),
        series=[count(day) for day in p.days],
    )


def _audit_lines(db: DbSession) -> list[AuditLine]:
    entries = db.scalars(
        select(AuditLog).where(AuditLog.action != "login")
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(AUDIT_LIMIT)
    )
    return [AuditLine(id=e.id, created_at=e.created_at, user_name=e.user_name, text=audit.summary(e)) for e in entries]


def _recent(db: DbSession, user: User) -> list[RecentSession]:
    """As últimas pela data da lista (W12). As em andamento ficam só em "Precisam de atenção"."""
    sessions = db.scalars(
        select(Session).where(scope(db, user), Session.status != "running")
        .order_by(rules.session_date.desc(), Session.created_at.desc()).limit(RECENT_LIMIT)
    )
    return [
        RecentSession(id=s.id, title=s.title, patient_code=s.patient.code, owner_name=s.owner.name,
                      date=s.started_at or s.created_at, status=s.status, stimuli_count=len(s.items))
        for s in sessions
    ]


def build(db: DbSession, user: User, zone: ZoneInfo) -> Dashboard:
    p = periods(utcnow(), zone)
    granted = permissions.role_permissions(db, user.role)
    admin = is_admin_view(user)
    attention = attention_sessions(db, user)
    rows = _executed(db, user, min(p.previous_month[0], p.weeks[0][0]))
    can_run = "sessions.run" in granted
    see_audit = admin and "admin.audit" in granted
    return Dashboard(
        view="admin" if admin else "researcher",
        badge=len(attention),
        month=p.month_name,
        previous_month=p.previous_month_name,
        sessions=_trend(rows, p, _count),
        awaiting=_awaiting(rows, attention, p),
        patients=None if admin else _trend(rows, p, _patients),
        collection_seconds=None if admin else _trend(rows, p, _seconds),
        users=_users(db, p) if admin and "admin.users" in granted else None,
        audit=_audit_kpi(db, p) if see_audit else None,
        attention=[
            AttentionItem(
                id=s.id, title=s.title, status=s.status, patient_code=s.patient.code, owner_name=s.owner.name,
                started_at=s.started_at, ended_at=s.ended_at, data_status=rules.data_status(s)[0],
                can_run=can_run and s.owner_id == user.id,
            )
            for s in attention
        ],
        recent=_recent(db, user),
        audit_entries=_audit_lines(db) if see_audit else None,
    )
