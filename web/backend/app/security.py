"""Proteção simples por chave de API (header X-Api-Key).

Aplicada nos endpoints de ESCRITA (ingestão e delete). Se QUESTPRO_API_KEY não estiver
definida, nada é exigido (modo dev). Leituras (lista/detalhe/vídeo) ficam abertas.
"""
import secrets

from fastapi import Header, HTTPException

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-Api-Key")) -> None:
    if not settings.api_key:
        return  # sem chave configurada -> aberto (dev)
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="X-Api-Key ausente ou inválida")
