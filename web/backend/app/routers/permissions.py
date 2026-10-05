"""Matriz de perfis e permissões (W21): ler e salvar. Exige a permissão "Alterar permissões".

A matriz é salva inteira. As permissões travadas do Admin ficam marcadas de qualquer jeito, e a
auditoria guarda uma linha por caixa que mudou ("Pesquisador · Inativar pacientes: Não → Sim").
"""
from itertools import groupby

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..models import User
from ..schemas.permission import PermissionGroup, PermissionMatrix, PermissionOut, PermissionsUpdate, RoleOut
from ..security import require_permission
from ..services import audit
from ..services import permissions as perms

router = APIRouter()

ManagePermissions = require_permission("admin.permissions")


def _matrix(db: DbSession) -> PermissionMatrix:
    grants = perms.all_grants(db)
    return PermissionMatrix(
        roles=[RoleOut(id=r, label=label, description=perms.ROLE_DESCRIPTIONS[r]) for r, label in perms.ROLE_LABELS.items()],
        groups=[
            PermissionGroup(label=group, permissions=[PermissionOut(id=p.id, label=p.label, description=p.description) for p in items])
            for group, items in groupby(perms.PERMISSIONS, key=lambda p: p.group)
        ],
        grants={role: [p.id for p in perms.PERMISSIONS if p.id in granted] for role, granted in grants.items()},
        locked={role: sorted(ids) for role, ids in perms.LOCKED.items()},
    )


@router.get("/permissions", response_model=PermissionMatrix)
def get_permissions(_: User = Depends(ManagePermissions), db: DbSession = Depends(get_db)):
    return _matrix(db)


@router.put("/permissions", response_model=PermissionMatrix)
def save_permissions(body: PermissionsUpdate, request: Request, me: User = Depends(ManagePermissions),
                     db: DbSession = Depends(get_db)):
    unknown_roles = set(body.grants) - set(perms.ROLE_LABELS)
    unknown_perms = {p for ids in body.grants.values() for p in ids} - perms.PERMISSION_IDS
    if unknown_roles or unknown_perms:
        raise HTTPException(status_code=422, detail="a matriz tem perfis ou permissões desconhecidos")

    before = perms.all_grants(db)
    after = {
        role: set(body.grants.get(role, [])) | perms.LOCKED.get(role, frozenset())
        for role in perms.ROLE_LABELS
    }
    changes = [
        audit.change(f"{role}:{p.id}", f"{perms.ROLE_LABELS[role]} · {p.label}", p.id in before[role], p.id in after[role])
        for role in perms.ROLE_LABELS
        for p in perms.PERMISSIONS
        if (p.id in before[role]) != (p.id in after[role])
    ]
    if changes:
        perms.replace_grants(db, after)
        audit.record(db, request, me, "update", "permissions", "Perfis e permissões", None, changes)
        db.commit()
    return _matrix(db)
