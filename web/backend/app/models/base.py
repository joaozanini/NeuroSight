"""Base declarativa e tipos comuns a todos os modelos.

A convenção de nomes dá nomes estáveis a índices e constraints. O Alembic precisa deles para
alterar ou remover essas peças depois, inclusive no SQLite, onde as migrações em lote recriam a
tabela inteira. A chave primária fica de fora: ela mantém o nome padrão do banco (no PostgreSQL,
`<tabela>_pkey`), o mesmo que o create_all das versões anteriores deu à tabela `sessions`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, Integer, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}

# JSON portável: vira JSONB no PostgreSQL e JSON comum no SQLite.
JSONType = JSON().with_variant(JSONB(), "postgresql")

# Chave inteira crescente: BIGINT no PostgreSQL; no SQLite só INTEGER vira autoincremento.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class UtcDateTime(TypeDecorator):
    """Data e hora sempre com fuso UTC na volta do banco.

    O PostgreSQL guarda `timestamptz` e devolve com fuso; o SQLite guarda texto e devolve a data
    sem fuso, que a API mandaria sem o "Z" e o navegador leria como hora local.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
