"""Contratos JSON do acesso (W01–W03) e do perfil do usuário logado (W05)."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def normalize_email(value: str) -> str:
    return value.strip().lower()


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)

    _email = field_validator("email")(normalize_email)


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)

    _email = field_validator("email")(normalize_email)


class LinkInfo(BaseModel):
    """O que a W03 mostra antes de pedir a senha: de quem é o link e para quê."""

    kind: Literal["invite", "reset"]
    name: str
    email: str


class SetPasswordIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=256)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class Me(BaseModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str
    permissions: list[str]
