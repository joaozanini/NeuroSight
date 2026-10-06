"""Início (W04) e o selo de sessões do menu. Só exige o login: cada um vê os números da própria visão
(services/dashboard.py), e as partes de usuários e auditoria dependem das permissões da área.

O selo tem rota própria, mais leve, porque o menu o consulta em todas as telas.
"""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..schemas.dashboard import Badge, Dashboard
from ..security import CurrentUser
from ..services import dashboard

router = APIRouter()


@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(user: CurrentUser, tz: str = Query("America/Sao_Paulo", max_length=64),
                  db: DbSession = Depends(get_db)):
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return dashboard.build(db, user, zone)


@router.get("/dashboard/badge", response_model=Badge)
def get_badge(user: CurrentUser, db: DbSession = Depends(get_db)):
    return Badge(sessions=dashboard.badge(db, user))
