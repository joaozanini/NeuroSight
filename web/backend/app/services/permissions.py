"""Catálogo das permissões (W21) e a consulta do que cada perfil pode fazer.

O catálogo é fixo no código: o servidor só sabe aplicar as permissões que conhece. O que é
editável é a matriz perfil × permissão, na tabela `role_permissions`. "Gerenciar usuários" e
"Alterar permissões" ficam sempre concedidas ao Admin, para ninguém perder o acesso à
administração; o servidor garante isso mesmo que a tabela diga outra coisa.
"""
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..models import RolePermission

ROLE_LABELS = {"admin": "Admin", "researcher": "Pesquisador"}
ROLE_DESCRIPTIONS = {
    "researcher": "Cadastra pacientes e estímulos, configura e executa sessões e analisa os dados.",
    "admin": "Tudo o que o pesquisador faz, mais usuários, permissões, visibilidade das sessões e auditoria.",
}


@dataclass(frozen=True)
class Permission:
    id: str
    group: str
    label: str
    description: str | None = None


PERMISSIONS: tuple[Permission, ...] = (
    Permission("patients.view", "Pacientes", "Ver pacientes"),
    Permission("patients.edit", "Pacientes", "Cadastrar e editar pacientes"),
    Permission("patients.deactivate", "Pacientes", "Inativar pacientes"),
    Permission("stimuli.edit", "Estímulos", "Enviar e editar estímulos"),
    Permission("stimuli.archive", "Estímulos", "Arquivar estímulos"),
    Permission("sessions.run", "Sessões", "Criar e executar sessões"),
    Permission(
        "sessions.view_all", "Sessões", "Ver sessões de outros pesquisadores",
        "Sem esta permissão, o pesquisador vê só as próprias sessões e as liberadas para ele.",
    ),
    Permission("sessions.visibility", "Sessões", "Alterar a visibilidade das sessões"),
    Permission("sessions.export", "Sessões", "Exportar os dados das sessões"),
    Permission("admin.users", "Administração", "Gerenciar usuários"),
    Permission("admin.permissions", "Administração", "Alterar permissões"),
    Permission("admin.audit", "Administração", "Consultar a auditoria"),
)
PERMISSION_IDS = frozenset(p.id for p in PERMISSIONS)
PERMISSION_LABELS = {p.id: p.label for p in PERMISSIONS}

# Sempre concedidas ao Admin (cadeado na W21).
LOCKED = {"admin": frozenset({"admin.users", "admin.permissions"})}

# Matriz padrão da W21; a migração 0002 semeia a tabela com estes valores.
DEFAULT_GRANTS: dict[str, frozenset[str]] = {
    "admin": PERMISSION_IDS,
    "researcher": frozenset({
        "patients.view", "patients.edit", "stimuli.edit", "sessions.run", "sessions.export",
    }),
}


def role_permissions(db: DbSession, role: str) -> set[str]:
    granted = set(db.scalars(select(RolePermission.permission).where(RolePermission.role == role)))
    return (granted & PERMISSION_IDS) | LOCKED.get(role, frozenset())


def all_grants(db: DbSession) -> dict[str, set[str]]:
    return {role: role_permissions(db, role) for role in ROLE_LABELS}


def has_permission(db: DbSession, role: str, permission: str) -> bool:
    return permission in role_permissions(db, role)


def replace_grants(db: DbSession, grants: dict[str, set[str]]) -> None:
    """Troca a matriz inteira (sem commit). As travadas são acrescentadas de qualquer jeito."""
    db.execute(delete(RolePermission))
    for role in ROLE_LABELS:
        for permission in sorted(grants.get(role, set()) | LOCKED.get(role, frozenset())):
            db.add(RolePermission(role=role, permission=permission))


def ensure_defaults(db: DbSession) -> bool:
    """Semeia a matriz padrão se a tabela estiver vazia (sem commit). True se semeou."""
    if db.scalar(select(RolePermission.role).limit(1)) is not None:
        return False
    replace_grants(db, {role: set(perms) for role, perms in DEFAULT_GRANTS.items()})
    return True
