"""Estímulos (W09–W11): as imagens e os vídeos que o óculos mostra nas sessões.

Cada arquivo sobe num request próprio e fica como rascunho (`draft`) até "Salvar na biblioteca",
que o passa para `active`. O arquivado (`archived`) sai da biblioteca e não entra em novas sessões,
mas continua guardado para as sessões antigas. Só o que nunca foi usado pode ser excluído.

No disco ficam o original, a miniatura e a versão para o óculos (imagem com até 2048 px; vídeo
H.264 com faststart), gerada em segundo plano depois de salvar. O sha256 da versão para o óculos
é a chave do cache no aparelho.
"""
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UtcDateTime, new_id, utcnow
from .user import User

STIMULUS_KINDS = ("image", "video")
STIMULUS_FORMATS = ("jpg", "png", "mp4")
STIMULUS_STATUSES = ("draft", "active", "archived")
# Versão para o óculos: pending (ainda não começou), processing, ready ou failed.
DEVICE_STATUSES = ("pending", "processing", "ready", "failed")


class Stimulus(Base):
    __tablename__ = "stimuli"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # image | video
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Arquivo enviado, como chegou (o formato vem do conteúdo, não da extensão).
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # jpg | png | mp4
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Dimensões como o estímulo aparece (já com a rotação do EXIF ou do vídeo aplicada).
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_audio: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    device_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    device_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    device_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    device_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    updated_at = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_by: Mapped[User | None] = relationship(lazy="joined")
    tag_rows: Mapped[list["StimulusTag"]] = relationship(
        back_populates="stimulus", cascade="all, delete-orphan", order_by="StimulusTag.position",
        lazy="selectin",
    )

    @property
    def tags(self) -> list[str]:
        return [row.tag for row in self.tag_rows]

    def set_tags(self, tags: list[str]) -> None:
        """Troca as etiquetas mantendo a ordem em que foram digitadas."""
        current = {row.tag: row for row in self.tag_rows}
        rows = []
        for position, tag in enumerate(tags):
            row = current.get(tag) or StimulusTag(tag=tag)
            row.position = position
            rows.append(row)
        self.tag_rows = rows


class StimulusTag(Base):
    """Etiqueta de um estímulo ("paisagem", "rosto"), em minúsculas."""

    __tablename__ = "stimulus_tags"

    stimulus_id: Mapped[str] = mapped_column(ForeignKey("stimuli.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(40), primary_key=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stimulus: Mapped[Stimulus] = relationship(back_populates="tag_rows")
