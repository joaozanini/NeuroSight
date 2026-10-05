"""Engine e sessão do SQLAlchemy, e as migrações do banco.

Síncrono: o FastAPI roda os endpoints `def` num threadpool. Portável: SQLite no dev e PostgreSQL
no servidor; só muda QUESTPRO_DB_URL.

O esquema é do Alembic (`app/migrations`): a API aplica as migrações pendentes ao subir.
"""
import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
# pre_ping: descarta do pool uma conexão que caiu (ex.: o PostgreSQL reiniciou).
engine = create_engine(settings.db_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Revisão que reproduz o esquema criado pelo create_all das versões anteriores.
BASELINE_REVISION = "0001_baseline"
# Chave arbitrária do advisory lock: com mais de um worker, só um migra por vez.
_MIGRATION_LOCK_KEY = 4_827_001


def alembic_config(connection=None):
    """Config do Alembic sem depender do alembic.ini (que fica só para a linha de comando)."""
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def migrate(bind: Engine | None = None) -> None:
    """Leva o banco até a última migração (equivale a `alembic upgrade head`).

    Um banco criado pelas versões anteriores (create_all, sem a tabela alembic_version) já tem o
    esquema da baseline: ele é carimbado com ela antes do upgrade, sem recriar nada.
    No PostgreSQL um advisory lock serializa os workers; o SQLite só é usado no desenvolvimento,
    com um processo.
    """
    from alembic import command

    bind = bind or engine
    with bind.begin() as conn:
        if conn.dialect.name == "postgresql":
            # Liberado no fim da transação; o DDL do Postgres é transacional.
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _MIGRATION_LOCK_KEY})
        cfg = alembic_config(conn)
        tables = set(inspect(conn).get_table_names())
        if "sessions" in tables and "alembic_version" not in tables:
            logger.warning("banco anterior ao Alembic: carimbando a baseline %s", BASELINE_REVISION)
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
