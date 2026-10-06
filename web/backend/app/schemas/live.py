"""Contratos JSON da execução ao vivo do lado do site (W14, W15). O lado do óculos, em camelCase,
está em docs/protocolo-oculos.md."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ControlAction = Literal["next", "previous", "goto", "neutral", "pause", "resume"]
TrackingState = Literal["active", "no_permission", "unavailable", "off"]


class PrepareRequest(BaseModel):
    """"Encontrado na rede" (o id do óculos) ou o código de pareamento digitado na W14."""

    device_id: str | None = Field(default=None, max_length=64)
    pairing_code: str | None = Field(default=None, max_length=10)

    @field_validator("pairing_code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not (len(value) == 4 and value.isdigit()):
            raise ValueError("o código tem 4 números, como aparece no app do óculos")
        return value

    @model_validator(mode="after")
    def _one(self):
        if not self.device_id and not self.pairing_code:
            raise ValueError("escolha o óculos ou digite o código")
        return self


class ControlRequest(BaseModel):
    action: ControlAction
    position: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _position(self):
        if self.action == "goto" and self.position is None:
            raise ValueError("diga qual estímulo exibir")
        return self


class ControlSent(BaseModel):
    command_id: int


class MarkerCreate(BaseModel):
    text: str = Field(max_length=200)

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("escreva o que aconteceu")
        return value


class Marker(BaseModel):
    id: int
    # Segundos desde o início da sessão.
    t: float
    text: str
    created_at: datetime
    created_by_name: str | None


class NearbyDevice(BaseModel):
    id: str
    name: str
    pairing_code: str | None


class LiveDevice(BaseModel):
    id: str
    name: str | None
    online: bool
    pairing_code: str | None
    same_network: bool
    paired_by: Literal["network", "code"] | None
    state: str
    tracking: dict[str, str]


class LiveLoad(BaseModel):
    loaded: int
    total: int
    error: dict[str, str] | None


class LivePlayback(BaseModel):
    position: int | None
    neutral: bool
    paused: bool
    shown: list[int]


class LiveSnapshot(BaseModel):
    """O retrato que o WebSocket /sessions/{id}/live manda a cada mudança."""

    type: Literal["live"] = "live"
    # Cresce a cada mudança: entre dois retratos, vale o de versão maior.
    version: int
    session_id: str
    status: str
    started_at: datetime | None
    device: LiveDevice | None
    nearby: list[NearbyDevice]
    load: LiveLoad
    playback: LivePlayback
