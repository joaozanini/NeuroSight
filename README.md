# QuestPro Eye-Tracking — Web + API

Recebe as sessões de eye tracking gravadas pelo app do Meta Quest Pro
([VR-EyeTracking-QuestPro](../VR-EyeTracking-QuestPro)), armazena num banco, lista todos os
registros e permite visualizar cada um **com e sem heatmap** (overlay no navegador).

```
óculos / adb pull ──► API (FastAPI)  ──►  banco (SQLite no dev / Postgres no servidor)
                         │                 mídia (frames + video.mp4) em disco
                         ▼
                   web (React)  ──►  vídeo + heatmap por cima (canvas, liga/desliga)
```

## O que cada sessão contém
- `gaze.json`: `meta` (fov, w, h, fps, uvOrigin) + `frames[]` (idx, t, arquivo) + `samples[]` (t, valid, world, **uv**, confidence). `uv` ∈ [0,1], origem no canto superior-esquerdo → pixel `(u·W, v·H)`.
- `frames/000001.jpg ...`: os quadros gravados. A API monta o `video.mp4` a partir deles.

## Status
- **Fase 1 — Backend (FastAPI):** ✅ implementado (ingestão + leitura + montagem do MP4).
- **Fase 2 — Frontend (React + heatmap no canvas):** ⏳ a fazer.
- **Fase 3 — App UE envia os frames** (hoje só manda o JSON): ⏳ a fazer (recompila o APK).

---

## Rodar o backend (dev, sem instalar banco)

Requer Python 3.12 e, para os scripts, as mesmas libs.

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

- Sobe em http://localhost:8000 — docs interativas em http://localhost:8000/docs.
- Sem `.env`, usa **SQLite** (`backend/questpro.db`) e grava a mídia em `backend/media/`.
- Os caminhos são relativos à pasta onde o `uvicorn` é iniciado.

### Testar a ingestão com uma sessão real (sem óculos)
Em outro terminal (com o venv ativo ou usando `.venv\Scripts\python`):

```bash
py -3.12 scripts/replay_session.py "C:/GitHub/VR-EyeTracking-QuestPro/Saved/GazeSessions/2026-06-17_22-10-54"
```

Confira `GET http://localhost:8000/api/v1/sessions` (lista) e o `video_url` do detalhe.
> As sessões reais têm **0 amostras válidas** (eye tracker descalibrado): o vídeo monta e toca,
> mas o heatmap fica vazio — é esperado.

### Testar o HEATMAP (sessão sintética)
```bash
py -3.12 scripts/make_synthetic_session.py ./synthetic
py -3.12 scripts/replay_session.py ./synthetic
```
Essa sessão tem `uv` válido varrendo a tela — é a que valida o heatmap quando o front estiver pronto.

---

## Usar PostgreSQL (servidor)
```bash
docker compose up -d        # sobe só o Postgres
# instale o driver e aponte o QUESTPRO_DB_URL:
backend\.venv\Scripts\pip install "psycopg[binary]"
$env:QUESTPRO_DB_URL="postgresql+psycopg://questpro:questpro@localhost:5432/questpro"   # PowerShell
.venv\Scripts\uvicorn app.main:app --port 8000
```

## Endpoints
| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/sessions` | cria/atualiza a sessão a partir do `gaze.json` (header `X-Session-Id`) |
| POST | `/api/v1/sessions/{id}/frames` | envia um lote de JPEGs (multipart, campo `frames`) |
| POST | `/api/v1/sessions/{id}/complete` | monta o MP4 e finaliza |
| GET | `/api/v1/sessions?limit=&offset=` | lista paginada (resumos) |
| GET | `/api/v1/sessions/{id}` | detalhe (meta + frames + todas as samples + `video_url`) |
| GET | `/api/v1/sessions/{id}/video` | serve o MP4 (suporta Range/seek) |
| DELETE | `/api/v1/sessions/{id}` | apaga a sessão e a mídia |
| GET | `/healthz` | health check |
