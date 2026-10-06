"""Regras das sessões usadas pelas rotas, pelos pacientes, pelos estímulos e pelo `app.seed`: quem vê
cada sessão, a data que aparece nas listas e os valores legíveis para a auditoria.

Quem vê uma sessão: o responsável; todos, se ela estiver aberta a todos; os pesquisadores
escolhidos, se estiver compartilhada; e quem tem "Ver sessões de outros pesquisadores".
"""
from sqlalchemy import and_, false, func, or_, select, true
from sqlalchemy.orm import Session as DbSession

from ..models import Session, SessionShare, User
from ..utils import format_decimal
from . import permissions

STATUS_LABELS = {
    "configured": "Configurada",
    "running": "Em andamento",
    "awaiting_data": "Aguardando dados",
    "completed": "Concluída",
    "interrupted": "Interrompida",
}
VISIBILITY_LABELS = {"private": "Privada", "shared": "Compartilhada", "all": "Aberta a todos"}
FIELD_LABELS = {
    "title": "Título",
    "patient": "Paciente",
    "objective": "Objetivo",
    "notes": "Observações",
    "record": "Gravação",
    "visibility": "Visibilidade",
    "stimuli": "Estímulos",
    "duplicated_from": "Duplicada de",
}
VISIBILITY_FIELD_LABELS = {"visibility": "Visibilidade", "shared_with": "Pesquisadores com acesso"}

# A data da sessão nas listas: o início, depois de executada; antes disso, quando foi configurada.
session_date = func.coalesce(Session.started_at, Session.created_at)


def sees_all(db: DbSession, user: User) -> bool:
    return permissions.has_permission(db, user.role, "sessions.view_all")


def visible_clause(user: User, all_sessions: bool):
    """Condição SQL das sessões que `user` pode ver (`all_sessions`: tem "Ver de outros")."""
    if all_sessions:
        return true()
    shared_with_me = select(SessionShare.session_id).where(SessionShare.user_id == user.id)
    return or_(
        Session.owner_id == user.id,
        Session.visibility == "all",
        and_(Session.visibility == "shared", Session.id.in_(shared_with_me)),
    )


def visible_to(db: DbSession, user: User | None):
    """A mesma condição, consultando a permissão; sem usuário, nenhuma sessão."""
    if user is None:
        return false()
    return visible_clause(user, sees_all(db, user))


def data_status(session: Session) -> tuple[str, str | None]:
    """Em que pé estão os dados coletados (W16) e, se o processamento falhou, o motivo."""
    if session.status in ("configured", "running"):
        return "none", None
    analysis = session.analysis or {}
    if session.status == "awaiting_data":
        if session.data_received_at is None:
            return "waiting", None
        if analysis.get("error"):
            return "failed", analysis["error"]
        return "processing", None
    return ("ready", None) if analysis and not analysis.get("error") else ("none", None)


def can_view(session: Session, user: User, all_sessions: bool) -> bool:
    if all_sessions or session.owner_id == user.id or session.visibility == "all":
        return True
    return session.visibility == "shared" and any(s.user_id == user.id for s in session.shares)


def audit_label(session: Session) -> str:
    """"Rostos neutros e expressivos, P-015" (item afetado da W22)."""
    return f"{session.title}, {session.patient.code}"


def item_label(position: int, name: str, kind: str, duration: float | None) -> str:
    if kind == "video":
        timing = "vídeo"
    elif duration is None:
        timing = "troca manual"
    else:
        timing = f"{format_decimal(duration)} s"
    return f"{position}. {name} ({timing})"


def sequence_label(session: Session) -> str:
    return "; ".join(
        item_label(item.position, item.stimulus.name, item.stimulus.kind, item.duration_seconds)
        for item in session.items
    )


def snapshot(session: Session) -> dict[str, object]:
    """Valores legíveis do que se configura no assistente, para o diff da auditoria."""
    return {
        "title": session.title,
        "patient": session.patient.code,
        "objective": session.objective,
        "notes": session.notes,
        "record": bool(session.record),
        "visibility": VISIBILITY_LABELS.get(session.visibility, session.visibility),
        "stimuli": sequence_label(session),
        "duplicated_from": audit_label(session.duplicated_from) if session.duplicated_from else None,
    }


def visibility_snapshot(session: Session) -> dict[str, str | None]:
    names = sorted((share.user.name for share in session.shares), key=str.casefold)
    return {
        "visibility": VISIBILITY_LABELS.get(session.visibility, session.visibility),
        "shared_with": ", ".join(names) or None,
    }


def owned_count(db: DbSession, user_id: str) -> int:
    """Sessões em que a pessoa é a responsável (W20)."""
    return db.scalar(select(func.count()).select_from(Session).where(Session.owner_id == user_id)) or 0
