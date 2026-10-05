"""Contratos JSON compartilhados por vários domínios."""
from pydantic import BaseModel


class Health(BaseModel):
    ok: bool
