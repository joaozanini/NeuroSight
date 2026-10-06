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

    # Chave que libera a leitura das sessões do fluxo antigo (/legacy/sessions) pelo X-Api-Key, além
    # do login do site. Vazia = leitura aberta (ok no dev local; NUNCA exponha na internet sem chave).
    api_key: str = ""

    # Pasta com o build do frontend (dist) para servir como SPA na raiz. Se não existir,
    # a API roda sem site (modo dev, em que o Vite serve o front na 5173).
    static_dir: str = "./static"

    api_prefix: str = "/api/v1"

    # Nível do log da aplicação (DEBUG, INFO, WARNING...). O do uvicorn segue o --log-level.
    log_level: str = "INFO"

    # ---- Contas e acesso ----
    # Chave que assina o cookie de sessão (JWT). Vazia = gerada uma vez e guardada em
    # <media_root>/.secret_key, para valer entre reinícios e entre os workers.
    secret_key: str = ""
    # Duração da sessão do site; o cookie é renovado sozinho quando passa da metade.
    session_hours: int = 12
    # Cookie só por HTTPS. Ligue no servidor (atrás do proxy com TLS); no dev fica desligado.
    cookie_secure: bool = False
    # Validade dos links de convite e de redefinição de senha.
    invite_hours: int = 7 * 24
    reset_hours: int = 2

    # Endereço do site usado nos links dos e-mails (convite, redefinição de senha).
    public_base_url: str = "http://localhost:5173"

    # SMTP para os e-mails. Sem host, nada é enviado: o admin vê e copia o link na tela, e o link
    # de "esqueci minha senha" vai para o log do servidor.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "NeuroSight <nao-responda@neurosight.local>"
    # starttls (porta 587), ssl (porta 465) ou none (Mailpit no dev, porta 1025).
    smtp_security: str = "starttls"
    smtp_timeout: float = 10.0

    # ---- Pacientes e estímulos ----
    # Tamanho máximo de cada arquivo de estímulo enviado (JPG, PNG ou MP4) e do PDF do TCLE.
    max_stimulus_mb: int = 1024
    max_consent_mb: int = 20
    # Rascunhos de estímulos (enviados e nunca salvos na biblioteca) somem depois deste prazo.
    draft_hours: int = 24

    # ---- Execução ao vivo (docs/protocolo-oculos.md) ----
    # Chave que o óculos manda no X-Device-Key (WebSocket e rotas /device). Vazia = aberta (só no dev).
    device_key: str = ""
    # Captura da gravação pedida ao óculos: menor = menos banda para subir depois do B.
    capture_width: int = 1024
    capture_height: int = 1024
    capture_fps: int = 30
    capture_jpeg_quality: int = 80
    # Tamanho máximo do JSON da sessão enviado pelo óculos.
    max_tracking_mb: int = 512

    # ---- Análise (services/analysis.py) ----
    # Fixações por I-DT: dispersão máxima (graus de ângulo visual) e duração mínima da janela.
    fixation_dispersion_deg: float = 1.0
    fixation_min_ms: float = 100

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)


settings = Settings()
