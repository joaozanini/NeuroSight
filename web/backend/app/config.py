"""Configuração via variáveis de ambiente (.env opcional).

Roda sem nenhuma configuração: o padrão é SQLite + pasta ./media, relativo a onde
você inicia o uvicorn. Para o servidor, basta setar DB_URL para o Postgres.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_prefix evita colisão com variáveis genéricas do sistema (ex.: um DB_URL de outro projeto).
    # As variáveis ficam QUESTPRO_DB_URL, QUESTPRO_MEDIA_ROOT, etc.
    model_config = SettingsConfigDict(env_prefix="QUESTPRO_", env_file=".env", extra="ignore")

    # SQLite no dev (zero instalação). No servidor:
    #   DB_URL=postgresql+psycopg://questpro:questpro@localhost:5432/questpro
    db_url: str = "sqlite:///./questpro.db"

    # Onde a mídia (frames + video.mp4) é gravada. Troque por um bucket via Storage depois.
    media_root: str = "./media"

    # Origem do dev server do React (CORS).
    frontend_origin: str = "http://localhost:5173"

    # Limite defensivo de frames por requisição multipart (o device manda em lotes).
    max_batch_frames: int = 50

    # Chave exigida no header X-Api-Key dos endpoints de ESCRITA (ingestão e delete) quando
    # definida. Vazia = tudo aberto (ok no dev local; NUNCA exponha na internet sem chave).
    api_key: str = ""

    # Pasta com o build do frontend (dist) para servir como SPA na raiz. Se não existir,
    # a API roda sem site (modo dev, em que o Vite serve o front na 5173).
    static_dir: str = "./static"

    api_prefix: str = "/api/v1"

    # Nível do log da aplicação (DEBUG, INFO, WARNING...). O do uvicorn segue o --log-level.
    log_level: str = "INFO"


settings = Settings()
