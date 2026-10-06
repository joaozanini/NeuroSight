# NeuroSight — Ambiente Web

> **Em reconstrução** seguindo o [plano de implementação](../docs/PLANO-IMPLEMENTACAO.md): a
> interface antiga (lista de sessões e viewer) saiu na Fase 0 e as telas novas entram fase a fase.
> Na Fase 3 a ingestão do fluxo antigo (cena 3D) e o `replay_session.py` saíram: as sessões passam
> a ser configuradas no site, e o óculos volta a enviar dados com o protocolo novo (fases 4 e 7). As
> sessões antigas ficam no banco, só para leitura em `/api/v1/legacy/sessions`. O resto deste
> README descreve o sistema antigo e é refeito na Fase 8.

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
.venv\Scripts\python -m app.seed --demo   # usuários, pacientes, estímulos e sessões de exemplo (senha NeuroSight#2026)
```

Os estímulos de exemplo são desenhados na hora (nada de mídia no repositório) e passam pelo mesmo
processamento de um envio pelo site: miniatura e versão para o óculos, com o ffmpeg que vem no
`imageio-ffmpeg`. As sessões de exemplo Concluídas e Interrompidas ganham olhar, expressões e uma
gravação sintéticos (o mesmo gerador do simulador, `backend/app/synthetic.py`), que passam pela
ingestão de verdade: o `--demo` leva cerca de um minuto a mais por isso. Rodar o `--demo` de novo
completa os dados que faltarem, inclusive num banco semeado antes de existir a análise.

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

`python -m app.seed --demo` cria usuários, pacientes, estímulos e sessões de exemplo, e o
`scripts/device_simulator.py` faz o papel do óculos, com o protocolo de
[`docs/protocolo-oculos.md`](../docs/protocolo-oculos.md): mostra o nome e o código de pareamento,
baixa os estímulos quando o site prepara a sessão (W14), obedece aos comandos da W15 e gera olhar e
expressões sintéticos. O B é o Enter; depois dele o simulador envia o JSON e a gravação, e o servidor
monta o MP4, analisa e deixa a sessão Concluída (ou Interrompida), com a análise na W17. O
`--truth arquivo.json` grava as fixações que o simulador gerou, para conferir as métricas.

```bash
cd backend
.venv/bin/python ../scripts/device_simulator.py                       # API em http://localhost:8000
.venv/bin/python ../scripts/device_simulator.py --auto-end 60 --once  # aperta o B sozinho e sai
.venv/bin/python ../scripts/device_simulator.py --help                # nome, chave, sem facial, --truth...
```

Com `QUESTPRO_DEVICE_KEY` definida no servidor, passe a mesma chave em `--key`. O hub da execução ao
vivo fica em memória: a API precisa rodar com **um** worker.

## API

Sessões configuradas no site (Fase 3; todas exigem o login, e cada um vê só o que a
visibilidade da sessão deixa):

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/sessions?q=&status=&owner_id=&since=&page=` | lista da W12 |
| GET | `/api/v1/sessions/owners` | responsáveis para o filtro da W12 |
| POST | `/api/v1/sessions` | cria a sessão do assistente (W13), com a sequência |
| GET | `/api/v1/sessions/{id}` | detalhe (W16) |
| PATCH | `/api/v1/sessions/{id}` | edita título, objetivo, observações e gravação |
| GET | `/api/v1/sessions/{id}/share-candidates` | pesquisadores para a W18 |
| PUT | `/api/v1/sessions/{id}/visibility` | muda a visibilidade (W18) |

Execução ao vivo (Fase 4; preparar, iniciar, controlar, interromper e marcar exigem "Criar e
executar sessões" e ser o responsável):

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/devices/nearby` | óculos conectados com o mesmo IP do navegador (W14) |
| POST | `/api/v1/sessions/{id}/prepare` | vincula o óculos (`device_id` ou `pairing_code`) e manda a sessão |
| POST | `/api/v1/sessions/{id}/release` | "Cancelar" da W14 |
| POST | `/api/v1/sessions/{id}/start` | Configurada → Em andamento (auditado) |
| POST | `/api/v1/sessions/{id}/control` | próximo, anterior, ir para N, tela neutra, pausar, retomar |
| POST | `/api/v1/sessions/{id}/interrupt` | Em andamento → Aguardando dados (auditado) |
| GET/POST | `/api/v1/sessions/{id}/markers` | marcações da W15 |
| GET/WS | `/api/v1/sessions/{id}/live` | retrato da sessão ao vivo (o WebSocket manda a cada mudança) |

O óculos usa o WebSocket `/api/v1/device/ws` e as rotas `/api/v1/device/...`, descritos em
[`docs/protocolo-oculos.md`](../docs/protocolo-oculos.md).

Dados coletados (Fase 5; quem vê a sessão vê a análise e a gravação, e baixar exige "Exportar os
dados das sessões" e fica na auditoria como Exportação):

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/sessions/{id}/analysis` | W17: exibições com as métricas, marcações, gravação e expressões |
| GET | `/api/v1/sessions/{id}/recording` | o MP4 para assistir (Range) |
| GET | `/api/v1/sessions/{id}/downloads/tracking` | o JSON como o óculos enviou |
| GET | `/api/v1/sessions/{id}/downloads/recording` | o MP4 |
| GET | `/api/v1/sessions/{id}/downloads/csv` | uma linha por exibição de estímulo, com as métricas e a média de cada expressão |

Sessões do fluxo antigo, só leitura (🔒 = com `QUESTPRO_API_KEY` definida, exige o login do site
ou o header `X-Api-Key`):

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/legacy/sessions?limit=&offset=` | lista paginada (resumos) 🔒 |
| GET | `/api/v1/legacy/sessions/{id}` | detalhe: meta + frames + todas as amostras + `video_url` 🔒 |
| GET | `/api/v1/legacy/sessions/{id}/video` | MP4 com suporte a Range/seek 🔒 |

Docs interativas em `http://localhost:8000/docs`.

## Análise (como é calculada)

Depois do envio do óculos, o servidor (`backend/app/services/analysis.py`) separa as exibições de
estímulo pelos eventos e calcula, em cada uma, as fixações por I-DT (até 1° de dispersão em pelo
menos 100 ms, em graus de ângulo visual pela geometria do painel; `QUESTPRO_FIXATION_*`), a duração
média, o tempo até a 1ª fixação e a porcentagem de amostras válidas, além das expressões faciais
reamostradas a 10 Hz. Os detalhes estão em [`docs/protocolo-oculos.md`](../docs/protocolo-oculos.md),
seção 4.3.

O mapa de calor da W17 segue o algoritmo de referência
([`headset/tools/heatmap_overlay.py`](../headset/tools/heatmap_overlay.py)): cada célula com olhar
deposita uma gaussiana, com o peso do tempo de olhar, num acumulador em ¼ de resolução, normalizado
pelo pico e pintado numa escala de azul, no navegador (`frontend/src/heatmap`).

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
