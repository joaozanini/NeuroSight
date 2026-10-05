"""Contratos JSON da matriz de perfis e permissões (W21)."""
from pydantic import BaseModel


class PermissionOut(BaseModel):
    id: str
    label: str
    description: str | None


class PermissionGroup(BaseModel):
    label: str
    permissions: list[PermissionOut]


class RoleOut(BaseModel):
    id: str
    label: str
    description: str


class PermissionMatrix(BaseModel):
    roles: list[RoleOut]
    groups: list[PermissionGroup]
    # Perfil -> permissões concedidas.
    grants: dict[str, list[str]]
    # Perfil -> permissões que ficam sempre marcadas (cadeado).
    locked: dict[str, list[str]]


class PermissionsUpdate(BaseModel):
    grants: dict[str, list[str]]
