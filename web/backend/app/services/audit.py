"""Auditoria: `record(...)` grava quem fez o quê, em qual item, de onde e o diff antes/depois.

O registro entra na mesma transação da mudança: se a mudança não for salva, o registro também
não é. Os valores do diff são guardados já como texto legível ("Pesquisador", "Inativo"), para o
registro continuar fiel mesmo que os rótulos mudem depois.
"""
from typing import Any, Mapping

from fastapi import Request
from sqlalchemy.orm import Session as DbSession

from ..models import AuditLog, User

# Rótulos das ações (filtro e coluna "Ação" da W22). As últimas quatro entram nas fases 3 a 5.
ACTION_LABELS = {
    "login": "Login",
    "create": "Criação",
    "update": "Edição",
    "invite": "Envio de convite",
    "password_reset": "Redefinição de senha",
    "visibility_change": "Mudança de visibilidade",
    "session_start": "Início de sessão",
    "session_end": "Fim de sessão",
    "export": "Exportação",
}

# Tipos de item afetado ("Todos os itens" da W22).
ENTITY_LABELS = {
    "session": "Sessão",
    "patient": "Paciente",
    "stimulus": "Estímulo",
    "user": "Usuário",
    "permissions": "Permissões",
    "system": "Sistema",
}

Change = dict[str, Any]


def client_ip(request: Request | None) -> str | None:
    # Atrás do proxy, o uvicorn com --proxy-headers já põe aqui o IP real (X-Forwarded-For).
    return request.client.host if request is not None and request.client else None


def user_agent(request: Request | None) -> str | None:
    ua = request.headers.get("user-agent") if request is not None else None
    return ua[:512] if ua else None


def record(
    db: DbSession,
    request: Request | None,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_label: str,
    entity_id: str | None = None,
    changes: list[Change] | None = None,
) -> AuditLog:
    """Acrescenta o registro na sessão do banco (o commit é de quem chamou)."""
    entry = AuditLog(
        user_id=actor.id if actor else None,
        user_name=actor.name if actor else None,
        user_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label[:255],
        ip=client_ip(request),
        user_agent=user_agent(request),
        changes=changes or [],
    )
    db.add(entry)
    return entry


def change(field: str, label: str, before: Any, after: Any) -> Change:
    return {"field": field, "label": label, "before": _text(before), "after": _text(after)}


def diff(before: Mapping[str, Any], after: Mapping[str, Any], labels: Mapping[str, str]) -> list[Change]:
    """Só os campos de `labels` que mudaram, na ordem de `labels`."""
    return [
        change(field, label, before.get(field), after.get(field))
        for field, label in labels.items()
        if _text(before.get(field)) != _text(after.get(field))
    ]


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    return str(value)
