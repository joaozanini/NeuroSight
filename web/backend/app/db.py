"""Engine + sessão do SQLAlchemy. Síncrono (FastAPI roda endpoints sync em threadpool).

Portável: SQLite no dev, PostgreSQL no servidor — só muda DB_URL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import Base

connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
engine = create_engine(settings.db_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Cria as tabelas (v1). Para o servidor, migrar para Alembic depois."""
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
