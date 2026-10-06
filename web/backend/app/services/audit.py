"""Auditoria: `record(...)` grava quem fez o quê, em qual item, de onde e o diff antes/depois.

O registro entra na mesma transação da mudança: se a mudança não for salva, o registro também
não é. Os valores do diff são guardados já como texto legível ("Pesquisador", "Inativo"), para o
registro continuar fiel mesmo que os rótulos mudem depois.
"""
from datetime import datetime
from typing import Any, Mapping

from starlette.requests import HTTPConnection
from sqlalchemy.orm import Session as DbSession

from ..models import AuditLog, User

# Rótulos das ações (filtro e coluna "Ação" da W22). As últimas quatro entram nas fases 3 a 5.
ACTION_LABELS = {
    "login": "Login",
    "create": "Criação",
    "update": "Edição",
    "delete": "Exclusão",
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


def client_ip(request: HTTPConnection | None) -> str | None:
    # Atrás do proxy, o uvicorn com --proxy-headers já põe aqui o IP real (X-Forwarded-For).
    return request.client.host if request is not None and request.client else None


def user_agent(request: HTTPConnection | None) -> str | None:
    ua = request.headers.get("user-agent") if request is not None else None
    return ua[:512] if ua else None


def record(
    db: DbSession,
    request: HTTPConnection | None,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_label: str,
    entity_id: str | None = None,
    changes: list[Change] | None = None,
    agent: str | None = None,
    at: datetime | None = None,
) -> AuditLog:
    """Acrescenta o registro na sessão do banco (o commit é de quem chamou).

    `agent` substitui o user-agent da requisição (o fim de sessão pelo B vem do óculos); `at`, o
    instante do registro, só para os dados de exemplo do `app.seed`, datados como se fossem reais.
    """
    entry = AuditLog(
        user_id=actor.id if actor else None,
        user_name=actor.name if actor else None,
        user_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label[:255],
        ip=client_ip(request),
        user_agent=agent[:512] if agent else user_agent(request),
        changes=changes or [],
    )
    if at is not None:
        entry.created_at = at
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


# Frases do Início (W04, "Últimas ações da auditoria"): o verbo e o artigo de cada tipo de item.
ENTITY_NOUNS = {
    "session": "a sessão",
    "patient": "o paciente",
    "stimulus": "o estímulo",
    "user": "o usuário",
}
CREATE_VERBS = {"session": "Criou", "patient": "Cadastrou", "stimulus": "Enviou", "user": "Criou"}
# Mudança de situação: (o que deixa de fora das listas, o que traz de volta).
STATUS_VERBS = {
    "patient": ("Inativou", "Reativou"),
    "stimulus": ("Arquivou", "Desarquivou"),
    "user": ("Desativou", "Reativou"),
}
STATUS_OFF = {"Inativo", "Arquivado"}


def summary(entry: AuditLog) -> str:
    """A ação como frase: "Iniciou a sessão Rostos neutros e expressivos", "Enviou 6 estímulos".

    A sessão aparece só pelo título (o registro guarda "título, código do paciente").
    """
    kind, action, label = entry.entity_type, entry.action, entry.entity_label
    if kind == "session":
        label = label.rsplit(", ", 1)[0]
    item = f"{ENTITY_NOUNS[kind]} {label}" if kind in ENTITY_NOUNS else label
    changes = entry.changes or []
    fields = {c.get("field"): c.get("after") for c in changes}
    own = entry.user_id is not None and entry.user_id == entry.entity_id

    if action == "login":
        return "Entrou no sistema"
    if action == "create" and kind == "stimulus" and entry.entity_id is None:
        return f"Enviou {len(changes)} estímulos"
    if action == "create" and kind in CREATE_VERBS:
        return f"{CREATE_VERBS[kind]} {item}"
    if action == "update" and kind == "user" and own:
        return "Aceitou o convite" if "status" in fields else "Alterou a senha"
    if action == "update" and kind in STATUS_VERBS and "status" in fields:
        off, on = STATUS_VERBS[kind]
        return f"{off if fields['status'] in STATUS_OFF else on} {item}"
    if action == "update" and kind == "permissions":
        return "Alterou os perfis e permissões"
    if action == "update" and kind in ENTITY_NOUNS:
        return f"Editou {item}"
    if action == "delete" and kind in ENTITY_NOUNS:
        return f"Excluiu {item}"
    if action == "invite":
        return f"Reenviou o convite para {label}"
    if action == "password_reset":
        return "Pediu a redefinição de senha" if own else f"Enviou a redefinição de senha para {label}"
    if action == "visibility_change":
        return f"Alterou a visibilidade da sessão {label}"
    if action == "session_start":
        return f"Iniciou a sessão {label}"
    if action == "session_end":
        return f"Encerrou a sessão {label}"
    if action == "export" and kind == "session":
        return f"Exportou os dados da sessão {label}"
    if action == "export":
        return "Exportou os registros da auditoria"
    return f"{ACTION_LABELS.get(action, action)}: {entry.entity_label}"
