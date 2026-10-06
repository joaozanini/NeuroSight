"""Contratos JSON da administração de usuários (W19, W20)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["admin", "researcher"]
UserStatus = Literal["invited", "active", "inactive"]


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("informe o nome")
    return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: Role
    status: UserStatus
    last_login_at: datetime | None
    created_at: datetime


class UserDetail(UserOut):
    created_by_name: str | None
    # Sessões em que a pessoa é a responsável.
    sessions_as_owner: int


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UserCreate(BaseModel):
    name: str = Field(max_length=120)
    email: EmailStr = Field(max_length=254)
    role: Role

    _name = field_validator("name")(_clean_name)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=254)
    role: Role | None = None
    # O convite pendente não é escolhido: ativar quem nunca criou a senha volta para o convite.
    status: Literal["active", "inactive"] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().lower()


class LinkResult(BaseModel):
    """Resultado do envio de um convite ou de uma redefinição.

    `link` só vem quando o e-mail não saiu (SMTP desligado ou com falha): o admin copia e entrega.
    """

    email_sent: bool
    link: str | None
    expires_at: datetime


class UserCreated(BaseModel):
    user: UserDetail
    invite: LinkResult
