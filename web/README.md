# QuestPro Eye-Tracking — Ambiente Web

Plataforma web + API feita sob medida para o app
**[QuestPro-EyeTracking](https://github.com/joaozanini/QuestPro-EyeTracking)** (Unreal Engine 5.5,
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
[README do app](https://github.com/joaozanini/QuestPro-EyeTracking#dados-gravados-por-sessão).

## Rodar em desenvolvimento (sem instalar banco)

Requer Python 3.12 e Node 18+.

```bash
# API (SQLite + mídia local, sem chave)
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Site (noutro terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api -> :8000)
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

Porta fiel do algoritmo de referência (`tools/heatmap_overlay.py` do repo do app): para o
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
