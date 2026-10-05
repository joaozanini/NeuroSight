"""Ambiente isolado dos testes: banco SQLite, mídia e site estático numa pasta temporária.

As variáveis de ambiente são definidas ANTES de importar a aplicação, porque `app.config.settings`,
o engine do banco e a rota do site estático são criados na importação.
"""
import os
import shutil
import tempfile
from pathlib import Path

TMP_ROOT = Path(tempfile.mkdtemp(prefix="neurosight-tests-"))
STATIC_DIR = TMP_ROOT / "static"
MEDIA_DIR = TMP_ROOT / "media"
# Arquivo fora do site estático: nenhuma URL pode devolvê-lo.
SECRET_FILE = TMP_ROOT / "segredo.txt"

os.environ["QUESTPRO_DB_URL"] = f"sqlite:///{TMP_ROOT / 'test.db'}"
os.environ["QUESTPRO_MEDIA_ROOT"] = str(MEDIA_DIR)
os.environ["QUESTPRO_STATIC_DIR"] = str(STATIC_DIR)
os.environ["QUESTPRO_API_KEY"] = ""
os.environ["QUESTPRO_SECRET_KEY"] = "chave-dos-testes-com-pelo-menos-32-bytes"
os.environ["QUESTPRO_SMTP_HOST"] = ""
os.environ["QUESTPRO_PUBLIC_BASE_URL"] = "http://site.teste"

(STATIC_DIR / "assets").mkdir(parents=True)
(STATIC_DIR / "index.html").write_text("<!doctype html><title>NeuroSight</title>", encoding="utf-8")
(STATIC_DIR / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
(STATIC_DIR / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
SECRET_FILE.write_text("conteudo secreto", encoding="utf-8")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:  # roda o lifespan: migra o banco temporário
        yield c


@pytest.fixture(autouse=True)
def clean_state(request):
    """Cada teste começa com o banco recém-migrado, sem mídia no disco e sem cookie de login.

    O banco é recriado (e não esvaziado) porque a auditoria não aceita DELETE.
    """
    yield
    if "client" not in request.fixturenames:
        return
    from sqlalchemy import text

    from app.db import engine, migrate
    from app.models import Base
    from app.services.ratelimit import login_limiter

    request.getfixturevalue("client").cookies.clear()
    login_limiter.clear()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    migrate()
    shutil.rmtree(MEDIA_DIR, ignore_errors=True)
    MEDIA_DIR.mkdir(exist_ok=True)


@pytest.fixture
def db():
    from app.db import SessionLocal

    with SessionLocal() as session:
        yield session


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
