# NeuroSight — Ambiente Web

> **Em reconstrução** seguindo o [plano de implementação](../docs/PLANO-IMPLEMENTACAO.md): a
> interface antiga (lista de sessões e viewer) saiu na Fase 0 e as telas novas entram fase a fase.
> A ingestão do óculos descrita abaixo continua funcionando igual.

Plataforma web + API feita sob medida para o app
**[do headset](../headset/)** (Unreal Engine 5.5,
Meta Quest Pro): recebe as sessões de rastreamento ocular gravadas no headset, armazena em
banco, monta o vídeo e permite **assistir cada sessão com ou sem heatmap do olhar**.

## 🎬 Demonstração

![Demo do ambiente web](docs/demo-ambiente-web.gif)

🎥 [Vídeo completo da demonstração (1 min, MP4)](docs/demo-ambiente-web.mp4)

## O que faz

- **Ingestão resiliente** direto do headset (botão B no app): `gaze.json` + frames JPEG em
  lotes multipart, com **retomada** se a rede cair e idempotência por sessão;
- **Monta o MP4 (H.264)** em background no servidor (status `uploading → processing → complete`);
- **Viewer** com três modos: vídeo puro, **heatmap em tempo real** (janela temporal, σ e
  opacidade ajustáveis ao vivo, renderizado no navegador) e **validação** (crosshair do olhar
  sobre o vídeo — deve coincidir com o marcador gravado pelo app);
- Corrige a linha do tempo para frames com Δt não uniforme (`currentTime → t real do frame`);
- Tema claro/escuro, chave de API nos endpoints de escrita, deploy via Docker Compose.

## Arquitetura

```
[Quest Pro — app UE 5.5]                [Este repositório]                      [Navegador]
 botão B → upload em lotes  ──HTTP──►    backend/  FastAPI + SQLAlchemy          frontend/  React+Vite+TS
                                         ├─ SQLite (dev) / PostgreSQL (prod)     ├─ lista de sessões
 (ou adb pull + replay_session.py)       ├─ mídia em disco (frames + video.mp4)  ├─ <video> + <canvas>
                                         └─ montagem H.264 em background         └─ heatmap client-side
```

O formato dos dados (`gaze.json`: `meta` + `frames[]` + `samples[]` com `uv` normalizado,
origem top-left) é definido pelo app — veja o
[README do app](../headset/README.md#dados-gravados-por-sessão).

## Rodar em desenvolvimento (sem instalar banco)

Requer Python 3.12+ e Node 20+.

```bash
# API (SQLite + mídia local, sem chave). Ao subir, aplica as migrações do banco.
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Site (noutro terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api -> :8000, inclusive WebSocket)
```

No Linux e no macOS os executáveis do venv ficam em `.venv/bin/`.

### Primeiro acesso

O site exige login. O primeiro admin é criado pela linha de comando, em `backend/`, e recebe um
convite para criar a senha (o link aparece no terminal e vai por e-mail quando há SMTP):

```bash
.venv\Scripts\python -m app.seed --admin-email voce@lab.br --admin-name "Seu Nome"
.venv\Scripts\python -m app.seed --demo   # usuários de exemplo dos protótipos (senha NeuroSight#2026)
```

Sem SMTP, os convites e redefinições que o admin envia pelo site mostram o link para copiar, e o
"Esqueci minha senha" deixa o link no log da API. Para ver os e-mails no dev, rode o
[Mailpit](https://mailpit.axllent.org/) e use `QUESTPRO_SMTP_HOST=localhost`,
`QUESTPRO_SMTP_PORT=1025` e `QUESTPRO_SMTP_SECURITY=none` (veja o `.env.example`).

### Testes e verificação

```bash
cd backend && .venv\Scripts\pytest                          # API, com SQLite temporário
cd frontend && npm run typecheck && npm test && npm run build
```

Os testes de migração (inclusive a trigger que impede alterar ou apagar a auditoria) também
rodam num PostgreSQL descartável quando `NEUROSIGHT_TEST_PG_URL` aponta para ele. Com o `npm run dev` no ar,
`http://localhost:5173/dev/componentes` mostra a vitrine dos componentes de base (só no modo dev).

### Banco e migrações

O esquema é do Alembic (`backend/app/migrations`), e a API aplica as migrações pendentes ao
subir. Um banco criado antes do Alembic é reconhecido e carimbado na baseline (`0001_baseline`),
sem recriar nada. Pela linha de comando, em `backend/`:

```bash
alembic upgrade head                            # aplica as migrações
alembic stamp 0001_baseline                     # marca um banco antigo como já estando na baseline
alembic revision --autogenerate -m "descrição"  # nova migração a partir dos modelos
```

### Testar sem o óculos

```bash
# reenviar uma sessão real (puxada do headset com adb pull)
py -3.12 scripts/replay_session.py "caminho/da/sessao" [--api http://SERVIDOR:8000/api/v1 --api-key CHAVE]

# ou gerar uma sessão sintética com olhar conhecido (valida o heatmap de ponta a ponta)
py -3.12 scripts/make_synthetic_session.py ./synthetic
py -3.12 scripts/replay_session.py ./synthetic
```

## API

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/sessions` | cria/atualiza a sessão a partir do `gaze.json` (header `X-Session-Id`) 🔑 |
| POST | `/api/v1/sessions/{id}/frames` | lote de JPEGs (multipart, campo `frames`) 🔑 |
| POST | `/api/v1/sessions/{id}/complete` | finaliza e agenda a montagem do MP4 🔑 |
| GET | `/api/v1/sessions?limit=&offset=` | lista paginada (resumos) |
| GET | `/api/v1/sessions/{id}` | detalhe: meta + frames + todas as amostras + `video_url` |
| GET | `/api/v1/sessions/{id}/video` | MP4 com suporte a Range/seek |
| DELETE | `/api/v1/sessions/{id}` | apaga sessão e mídia 🔑 |

🔑 = exige header `X-Api-Key` quando `QUESTPRO_API_KEY` está definida (produção).
Docs interativas em `http://localhost:8000/docs`.

## Heatmap (como é calculado)

Porta fiel do algoritmo de referência ([`headset/tools/heatmap_overlay.py`](../headset/tools/heatmap_overlay.py)): para o
instante `t`, as amostras válidas na janela `[t−W, t]` depositam gaussianas (σ configurável)
com decaimento linear, normalizadas pelo pico e coloridas com colormap JET — tudo no
navegador, em ¼ de resolução, com os parâmetros ajustáveis sem reprocessar nada.

## Produção (servidor)

Stack completo (site + API + PostgreSQL) com Docker Compose — **passo a passo em
[`DEPLOY.md`](DEPLOY.md)**, incluindo checklist de firewall, testes em camadas, backup e a
configuração do app do headset (`Upload Url` + `Api Key`).

```bash
cp .env.example .env    # defina QUESTPRO_API_KEY e QUESTPRO_DB_PASSWORD
docker compose up -d --build
```

## Estado do projeto

Pipeline completo validado em campo (13/07/2026): sessão gravada no Quest Pro → upload →
banco → MP4 → heatmap e validação no navegador. ✅
