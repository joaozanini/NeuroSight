# NeuroSight: plano de implementação

> Documento de passagem entre sessões. Cada sessão lê este arquivo inteiro antes de começar e,
> ao terminar, atualiza **Status das fases** e **Registro de desvios**. O prompt para iniciar
> uma fase está no fim do arquivo.

## Status das fases

| Fase | Situação | Branch / commit | Observações |
|---|---|---|---|
| 0 Base técnica | concluída | `fase-0-base-tecnica` (`690ed32` backend, `d9269a4` frontend) | Ver as notas da Fase 0 abaixo. |
| 1 Contas, permissões e auditoria | concluída | `fase-1-contas` (`0c472a9` backend, `6141467` frontend) | Ver as notas da Fase 1 abaixo. |
| 2 Pacientes e estímulos | concluída | `fase-2-pacientes-estimulos` (`975b223` backend, `e29d8ff` frontend) | Ver as notas da Fase 2 abaixo. |
| 3 Configuração de sessões | concluída | `fase-3-sessoes` (`5be29c9` backend, `8e79b2c` frontend) | Ver as notas da Fase 3 abaixo. |
| 4 Execução ao vivo + simulador | concluída | `fase-4-ao-vivo` (`37e1ca8` backend e simulador, `cd33621` frontend) | Ver as notas da Fase 4 abaixo. |
| 5 Ingestão e análise | concluída | `fase-5-ingestao-analise` (`80fe1c0` backend e simulador, `d323355` frontend) | Ver as notas da Fase 5 abaixo. |
| 6 Início (dashboard) | concluída | `fase-6-inicio` (`0c4f3db` backend, `ed0cc84` frontend) | Ver as notas da Fase 6 abaixo. |
| 7 App do óculos (UE 5.5) | não iniciada | | |
| 8 Deploy e documentação | não iniciada | | |

### Notas da Fase 0 (para as próximas sessões)
- **Testes**: em `web/backend`, `pip install -r requirements-dev.txt` e `pytest` (SQLite temporário;
  com `NEUROSIGHT_TEST_PG_URL` os testes de migração também rodam num PostgreSQL). Em
  `web/frontend`, `npm run typecheck`, `npm test` e `npm run build` (o build roda o typecheck).
- **Migrações**: `web/backend/app/migrations`. A API chama `app.db.migrate()` ao subir. Tabela
  nova = modelo em `app/models/<domínio>.py` + `alembic revision --autogenerate -m "..."` (revisar
  o script). A convenção de nomes de índices e constraints está em `app/models/base.py`.
- **Rotas do site** (em português) ficam em `src/routes.ts` como placeholders. Ao implementar uma
  tela, troque o placeholder pela página no `App.tsx` e tire a entrada de `routes.ts`.
- **Menu**: `layouts/Sidebar.tsx` recebe `user`, `showAdmin`, `sessionsBadge` e `onLogout`. Hoje o
  `AppLayout` passa só `showAdmin`; a Fase 1 liga o login e a permissão, e a Fase 6 o selo.
- **Contratos já fixados no front**: valores de status em `src/lib/status.ts` (`configured`,
  `running`, `awaiting_data`, `completed`, `interrupted`; `active`, `invited`, `inactive`) e regras
  de senha em `src/lib/password.ts`, que o backend da Fase 1 precisa repetir.
- **Cliente da API**: `api.get/post/put/patch/delete` e `ApiError` (`status`, `message`, `detail`
  com os campos do 422) em `src/api/client.ts`; use `redirectOnUnauthorized: false` no login.
  Upload com progresso: `uploadFile()` em `src/api/upload.ts`. Datas e números em pt-BR:
  `src/lib/format.ts`.
- **Componentes**: exportados em `src/components/index.ts`; a vitrine `/dev/componentes` (só no
  `npm run dev`) mostra todos com os textos dos protótipos.
- As rotas antigas de leitura (`GET`/`DELETE /api/v1/sessions`) continuam, sem tela.

### Notas da Fase 1 (para as próximas sessões)
- **Proteger uma rota**: `user: CurrentUser` (só login) ou `Depends(require_permission("patients.view"))`,
  ambos em `app/security.py`. Os 12 ids ficam em `app/services/permissions.py` (e no tipo
  `Permission` de `src/api/auth.ts`); a matriz é lida do banco a cada request.
- **Auditar**: `audit.record(db, request, user, action, entity_type, label, entity_id, changes)` na
  mesma transação da mudança, com `audit.diff(antes, depois, rótulos)` sobre valores já legíveis
  (veja `accounts.snapshot`). Ações e tipos de item ficam em `app/services/audit.py` e já incluem
  os das próximas fases (`visibility_change`, `session_start`, `session_end`, `export`; `session`,
  `patient`, `stimulus`). O "Abrir …" da W23 sai de `ENTITY_LINKS` em `src/pages/admin/auditLabels.ts`.
- **Datas**: colunas novas usam `UtcDateTime` (`app/models/base.py`), que devolve sempre com fuso.
- **Front**: `useCurrentUser()` e `hasPermission(me, ...)` em `src/api/auth.ts`; rotas com permissão
  via `guarded(...)` no `App.tsx` (mostra "Sem acesso"). Tudo dentro de `RequireAuth`, que leva ao
  login com `?next=`. Erro de formulário inteiro: `FormAlert`.
- **Testes**: no backend, `tests/accounts.py` (`make_user`, `login`, `admin`, `researcher`,
  `audit_entries`); o banco é recriado a cada teste. No front, `mockApi` (`src/test/api.ts`) e os
  usuários `ADMIN`/`RESEARCHER` (`src/test/fixtures.ts`); toda tela interna precisa de `GET /me`.
- **Dados de exemplo**: `python -m app.seed --demo` cria os usuários da W19 (senha `NeuroSight#2026`).
  Para ver e-mails, Mailpit com `QUESTPRO_SMTP_HOST/PORT/SECURITY` (ver `web/README.md`).
- `sessions_as_owner` (W20) conta as sessões em que o usuário é o responsável (ligado na Fase 3).

### Notas da Fase 2 (para as próximas sessões)
- **O que a Fase 3 liga**: `sessions_count`, `last_session_at` e `sessions` dos pacientes
  (`_detail` em `routers/patients.py`; o schema `PatientSession` já existe) e a ordem da W06 pela
  última sessão; `stimuli.usage_count()` (devolve 0) e a lista `sessions` da W11 (`StimulusSession`),
  que também decidem se o estímulo pode ser excluído. Arquivados (`status = "archived"`) e pacientes
  inativos não entram em sessões novas.
- **Rotas**: `GET /patients` (`q`, `include_inactive`, 8 por página, `counts`), `GET /patients/next-code`,
  `POST /patients` e `PUT /patients/{id}` em multipart (`data` em JSON + `consent_file`),
  `PUT /patients/{id}/status`, `GET /patients/{id}/consent`. `GET /stimuli` (`q`, `kind`, `tag`,
  `include_archived`, 48 por página, `counts`), `GET /stimuli/tags`, `POST /stimuli/uploads` (um
  arquivo, vira rascunho), `DELETE /stimuli/uploads/{id}`, `POST /stimuli` (salva os rascunhos),
  `GET`/`PATCH /stimuli/{id}`, `PUT /stimuli/{id}/status`, `DELETE /stimuli/{id}`, `/thumbnail` e `/file`.
- **Versão para o óculos** (Fase 4): `device_status`, `device_format`, `device_sha256` (chave do cache
  no aparelho), `device_size_bytes` e dimensões em `stimuli`; o arquivo é
  `storage.stimulus_device(id, formato)`. Gerada em segundo plano depois de salvar e retomada ao subir
  a API (`services/stimuli.resume_pending`).
- **Front**: `?paciente=<id>` em `/sessoes/nova` é o "Nova sessão" da W06/W08 (o assistente deve
  abrir com ele); `/estimulos?enviar=1` abre a W10 (para o atalho da W04). Filtros na URL com
  `useUrlFilters` (`src/lib`). Componentes `StimulusThumbnail` e `DateField` (com `lib/dates.ts`).
- **Testes**: `tests/media_files.py` gera JPG, PNG, MP4/MOV e PDF; no front, `src/test/xhr.ts` simula
  os envios e o `mockApi` entende `FormData`. No `mockApi` a ordem das rotas importa: declare
  `GET /stimuli/tags` antes de `GET /stimuli/:id`, como no servidor.
- **Dados de exemplo**: `--demo` cria P-001 a P-015 (os da W06) e 17 estímulos (rostos 01 a 12,
  paisagens, frutas e os vídeos "Ondas na praia" e "Floresta com vento"), desenhados por
  `app/seed_media.py`, em nome de Ana Souza.

### Notas da Fase 3 (para as próximas sessões)
- **Tabelas** (`app/models/session.py`, migração `0004_sessions`): `sessions` (`type`
  `media_sequence`, `status`, `end_reason`, `record`, `visibility` `private|shared|all`, `patient_id`,
  `owner_id`, `duplicated_from_id`, `started_at`, `ended_at`), `session_stimuli` (`position` a partir
  de 1 e `duration_seconds` só nas imagens; vazio = troca manual; cada estímulo uma vez por sessão),
  `session_shares` e `session_markers` (`t` em segundos desde o início, `text`, `created_by_id`),
  esta ainda sem rota. `started_at`, `ended_at` e `end_reason` já existem para a Fase 4 preencher.
- **Quem vê**: `services/sessions.py` (`visible_clause`, `visible_to`, `can_view`, `session_date` =
  início ou, antes de executar, a configuração). Sessão que a pessoa não vê responde **404**. Use a
  mesma regra nas rotas novas (preparar, controle, análise, downloads).
- **Quem executa**: `can_run` = "Criar e executar sessões" **e** ser o responsável (W12 e W16 só
  mostram Preparar/Abrir controle nesse caso); a Fase 4 deve exigir o mesmo em `prepare`/`start`.
  `can_edit` (informações) = "Criar e executar" e (responsável ou "Ver de outros").
- **Rotas**: `GET /sessions` (`q`, `status`, `owner_id`, `since`, 8 por página), `GET /sessions/owners`,
  `POST /sessions` (o assistente; aceita `duplicated_from_id`), `GET`/`PATCH /sessions/{id}`,
  `GET /sessions/{id}/share-candidates` e `PUT /sessions/{id}/visibility`. O nome, o nascimento e o
  sexo do paciente só vêm para quem tem "Ver pacientes".
- **Fluxo antigo**: `LegacySession` (`legacy_sessions`), só leitura em `/legacy/sessions` (login ou
  `X-Api-Key`), sem tela. A ingestão antiga e o `require_api_key` saíram; a chave do dispositivo da
  Fase 4 é nova. `services/video.py` ficou para a Fase 5. A mídia antiga está em `<media>/<id>/`;
  para as sessões novas, sugiro `<media>/sessions/<id>/`.
- **Front**: `src/api/sessions.ts` (com `prepareSessionPath` e `controlSessionPath`, hoje placeholders
  da Fase 4) e `src/pages/sessions/`. Textos da sequência ("cerca de 1 min", "Vídeo inteiro (0:45)")
  em `sequence.ts`; o assistente em `wizard/`. `?duplicar=<id>` em `/sessoes/nova` é o "Duplicar
  para outro paciente". O filtro de período das listas está em `src/lib/periods.ts`.
- **O que a Fase 5 troca na W16**: o cartão "Sequência da sessão" (largura inteira) dá lugar a
  "Estímulos exibidos" com as colunas da direita (Marcações, Arquivos), e "N na sequência" no resumo
  vira "N exibidos". "Analisar dados" já aparece nas Concluídas e Interrompidas.
- **Dados de exemplo**: `--demo` cria 26 sessões (as 23 que Ana vê nos últimos 30 dias, como na W12,
  com as contagens da W06, e três só do admin), com datas relativas a hoje. As executadas têm status
  e horários, **sem dados coletados**: a Fase 5 precisa gerar dados sintéticos para elas ou tratar a
  falta deles na W16/W17. Os pacientes de exemplo agora são cadastrados na data do TCLE.
- **Testes**: `tests/test_sessions.py` (`make_patient`, `make_stimulus`, `create`, `set_session`); no
  front, `src/pages/sessions/SessionPages.test.tsx`. O `test/setup.ts` desliga o `window.scrollTo`.
- O selo de sessões do menu continua para a Fase 6.

### Notas da Fase 4 (para as próximas sessões)
- **Protocolo**: `docs/protocolo-oculos.md` (aprovado pelo usuário antes do hub) é o contrato do
  óculos, do simulador e da Fase 7. Mudou o contrato, mude o documento junto.
- **Peças**: `services/live_hub.py` (hub em memória, thread-safe; o envio só enfileira na conexão),
  `services/execution.py` (o `load`, as transições e a auditoria do início e do fim),
  `routers/live.py` (site) e `routers/device.py` (óculos). Tabela `devices` e, em `sessions`,
  `device_id` (o óculos que executou; só ele envia os dados) e `data_received_at` (o `complete`).
- **Onde ficam os dados**: `storage.session_tracking(id)` (`<media>/sessions/<id>/tracking.json`) e
  `storage.session_frames_dir(id)` (`frames/NNNNNN.jpg`). O JSON é conferido só por cima (`version`
  2 e `meta.sessionId`); validar o resto, montar o MP4 (`services/video.assemble_mp4` com
  `frames[]` do JSON) e passar a Concluída ou Interrompida é da Fase 5, a partir do `complete`
  (`routers/device.complete_upload`, que hoje só grava `data_received_at`). A interrompida termina
  como Interrompida; o B e a queda, como Concluída (sugestão; `end_reason` diz o motivo).
- **Simulador**: `--truth arquivo.json` grava as exposições (`on`/`off` em segundos da sessão) e as
  fixações geradas (`start`, `end`, `duration`, `u`, `v` no estímulo), mais `samples` e
  `validSamples`, para os testes da Fase 5. Fixações de 200 a 600 ms a mais de 0,12 UV uma da outra
  (cerca de 7°: o painel tem 2,4 × 1,35 m a 2 m), sacadas de 30 ms, piscadas de 150 ms (inválidas) e
  latência de 120 a 250 ms até a 1ª fixação. Olhar a 72 Hz, facial a 30 Hz, quadros a 10 fps
  (`--frame-fps`). A lógica de geração está nas classes `Scanpath` e `Recording` do script.
- **Retrato ao vivo** (`GET`/`WS /sessions/{id}/live`): status, óculos, `nearby`, carga e o que está na
  tela, com `version` crescente. No site, `useLiveSession` e `keepNewest` (`src/api/live.ts`); as
  chaves do React Query ficam em `['live', id]`, fora de `['sessions']`, de propósito.
- **Para a Fase 6**: o selo do menu conta Em andamento + Aguardando dados; `data_received_at` diz se o
  óculos já terminou de enviar ("em envio" no KPI do admin).
- **Testes**: `tests/test_live.py` (o óculos é um WebSocket do TestClient; `sync(ws)` manda um ping e
  espera o pong para saber que o servidor já tratou o que veio antes; o `conftest` zera o hub). No
  front, `src/test/socket.ts` (WebSocket falso; `await sockets.push(...)`) e
  `src/pages/sessions/live/LivePages.test.tsx`.
- **Docker**: o `Dockerfile` ainda sobe com 2 workers, e o hub exige 1 (Fase 8). O compose já repassa
  `QUESTPRO_DEVICE_KEY`.

### Notas da Fase 5 (para as próximas sessões)
- **Peças**: `services/tracking.py` (confere o JSON v2 no `PUT tracking`; 422 com o caminho do
  problema), `services/analysis.py` (só cálculo, com numpy), `services/ingestion.py` (fila com uma
  thread depois do `complete`: MP4, análise e status final; `drain()` nos testes e `resume_pending()`
  ao subir) e `routers/session_data.py` (análise, gravação e downloads). O protocolo ganhou as seções
  4.2 (o que o servidor confere) e 4.3 (o que calcula).
- **Tabelas** (migração `0006_session_analysis`): `sessions.analysis` (JSON adiado: resumo,
  parâmetros, tamanhos, gravação com `frame_t` e `frame_gaze`, séries da legenda padrão a 10 Hz e os
  nomes das expressões; `{"error": ...}` quando falha) e `session_exposures` (uma linha por exibição,
  `seq` na ordem em que apareceu, com as métricas; `fixations`, `heat` e `face_means` adiados).
- **Estado dos dados**: `data_status` no detalhe da sessão (`none`, `waiting`, `processing`, `failed`
  com `data_error`, `ready`). A W16 completa e o "Analisar dados" só aparecem com `ready`. Status
  final pelo `end_reason` (`ingestion.FINAL_STATUS`): Concluída pelo B, Interrompida nos outros.
- **Rotas**: `GET /sessions/{id}/analysis`, `GET /sessions/{id}/recording` (Range, sem auditoria) e
  `GET /sessions/{id}/downloads/{tracking|recording|csv}?tz=` ("Exportar os dados", auditado como
  Exportação com o campo Arquivo). Nome dos arquivos: `<código>_<aaaa-mm-dd_hhmm>_<rastreamento.json |
  gravacao.mp4 | estimulos.csv>`. Mesma regra de quem vê: sessão que a pessoa não vê responde 404.
- **Gerador sintético**: `app/synthetic.py` (`Recording`, `Scanpath`, `VirtualClock`, `play`); o
  simulador o importa (precisa do repositório e do venv do backend) e `app/seed_tracking.py` roda o
  roteiro das sessões de exemplo. O `--demo` leva cerca de 1 min a mais (gravação de 640 × 400 a
  10 fps) e, rodado de novo, completa os dados que faltarem.
- **Para a Fase 6**: "Tempo de coleta no mês" pode usar `ended_at − started_at` (ou `analysis.duration`,
  no relógio do óculos); "em envio" é Aguardando dados sem `data_received_at`, e com ele está
  processando. As sessões de exemplo executadas têm dados, e algumas têm marcações.
- **Para a Fase 7**: os parâmetros do I-DT (`QUESTPRO_FIXATION_DISPERSION_DEG` e `_MIN_MS`) foram
  ajustados ao ruído do simulador; com o olhar real do Quest Pro, confira as fixações e ajuste se preciso.
- **Para a Fase 8**: os frames JPEG continuam no disco ao lado do MP4 (espaço em disco); com os 2
  workers do Docker atual, cada processo tem a própria fila (o `FOR UPDATE` no fim deixa só uma
  gravar). O teste de fumaça com Playwright da "Verificação ponta a ponta" continua fora do
  repositório, como nas fases anteriores: para entrar, falta decidir a dependência (playwright-core e
  o Chromium).
- **Testes**: `tests/test_analysis.py`, `tests/test_session_data.py` (`executed()` leva a sessão pelo
  óculos do TestClient e envia os dados do gerador) e `tests/test_simulator.py` (o simulador de
  verdade contra um uvicorn de teste, cerca de 10 s). No front, `pages/sessions/analysis/AnalysisPage.test.tsx`;
  o `test/setup.ts` desliga o canvas e simula o play e o pause do vídeo.

### Notas da Fase 6 (para as próximas sessões)
- **Peças**: `services/dashboard.py` (tudo calculado a cada pedido, sem tabela nova), `routers/dashboard.py`
  (`GET /dashboard?tz=` e `GET /dashboard/badge`) e `schemas/dashboard.py`; `audit.summary(entry)` monta a
  frase das "Últimas ações" ("Iniciou a sessão …", "Enviou 6 estímulos"). No site, `src/api/dashboard.ts`,
  `pages/home/` (`HomePage` e os textos que dependem dos números em `homeText.ts`) e o selo no `AppLayout`.
- **Visões**: pelo perfil. O admin vê as sessões que pode ver, "Usuários ativos" (com "Gerenciar
  usuários") e a auditoria (com "Consultar a auditoria"); o pesquisador, só as sessões em que é o
  responsável. O selo do menu, o subtítulo e "Precisam de atenção" contam o mesmo conjunto: Em andamento
  e Aguardando dados.
- **Períodos** no fuso do navegador (`tz`): o mês até agora contra o mesmo trecho do mês anterior; as
  linhas de tendência são 8 semanas de 7 dias terminando agora (a de "Aguardando dados" é um retrato no
  fim de cada semana) e, na auditoria, 8 dias.
- **Selo**: chave `['sessions', 'badge']` do React Query, de propósito dentro de `['sessions']`: o que
  invalida as sessões atualiza o selo. Também se atualiza a cada 30 s (o óculos muda o status sem passar
  pelo navegador), como o Início.
- **Placeholders**: acabaram. `routes.ts` e `PlaceholderPage` saíram; toda rota está no `App.tsx`.
- **Auditoria com data**: `audit.record(..., at=)` só para o `app.seed`. O início e o fim na auditoria
  ficaram em `execution.record_start`/`record_end`, usados pela execução e pelo seed.
- **Testes**: `tests/test_dashboard.py`; no front, `pages/home/HomePage.test.tsx`.

### Decisões em aberto
- **Servidor de produção** (domínio, proxy reverso existente): confirmar na Fase 8.

### Registro de desvios
_Cada sessão anota aqui, com a fase, o que fez diferente deste plano e por quê._

- **Fase 0, migrações automáticas**: além da baseline para o `alembic stamp`, a API aplica as
  migrações ao subir e carimba sozinha um banco anterior ao Alembic (o comando manual continua
  valendo). No PostgreSQL um advisory lock serializa os workers, porque o Docker ainda sobe com 2.
  Testado num banco criado pelo código antigo, com a imagem Docker: dados preservados.
- **Fase 0, convenção de nomes** de índices, unique, check e FK no `Base.metadata`, para o Alembic
  conseguir alterar constraints depois (inclusive no SQLite). A PK ficou de fora para a baseline
  sair idêntica ao banco do servidor (`sessions_pkey`, conferido com `pg_dump`).
- **Fase 0, path traversal**: além de `//etc/passwd`, `..%2f` e `%2e%2e` também vazavam arquivos;
  todos foram corrigidos. De quebra, rotas `/api/...` inexistentes respondem 404 em JSON em vez do
  `index.html`, e a ingestão responde 400 (não 500) a um JSON que não é objeto.
- **Fase 0, fonte**: `@fontsource-variable/inter` (o pacote variável do Fontsource), só com o eixo
  de peso. As medidas nos PNGs batem com a Inter sem tamanho óptico; os títulos de página são
  600 com −0,02em, e o "NeuroSight" do painel, 600 com −0,03em.
- **Fase 0, rotas em português** (`/pacientes`, `/sessoes/:id/analise`, `/admin/usuarios`...) e
  placeholders por tabela (`routes.ts` + `PlaceholderPage`), em vez de um arquivo por tela.
- **Fase 0, menu sem login**: até a Fase 1 o menu esconde o rodapé (usuário e Sair) e mostra
  Administração para todos.
- **Fase 0, protótipos divergentes**, resolvidos pelas telas e não pelos PNGs avulsos:
  - miniatura do painel da marca com sidebar de 150 px (W01–W03), não 175 px (PNG do componente);
  - divisória do rodapé do menu a 16 px do usuário (W05, W06), não 24 px (PNG do componente);
  - botão secundário desabilitado em cinza (W06, W15), não esmaecido como na W21;
  - opções em cartão com duas aparências: borda de campo, sem destaque (W07), e borda clara com
    destaque azul na marcada (W18, W20).
- **Fase 0, etiquetas removíveis**: o TagInput mostra um "x" em cada etiqueta; o protótipo, estático,
  não mostra como tirar uma.
- **Fase 0, ambiente**: o Python 3.14 local instalou tudo sem `uv`. Os testes usam `httpx2`, que o
  Starlette 1.x pede para o TestClient. O `tsconfig` passou a acusar variáveis e parâmetros sem uso.
- **Fase 0, imagem e docs**: entrou um `.dockerignore` (o build local copiava `node_modules` e
  `.venv`) e o `alembic.ini` vai na imagem; o Dockerfile segue com `--workers 2` até a Fase 8. Nos
  docs, só os comandos novos (testes, migrações) no `web/README.md` e uma nota no `DEPLOY.md`; o
  resto fica para a Fase 8.
- **Fase 1, ações da auditoria**: além das sete da W22, entraram "Envio de convite" (reenvio) e
  "Redefinição de senha" (link pedido em "Esqueci minha senha" ou enviado pelo admin). Aceitar o
  convite, redefinir e trocar a senha viram "Edição" do usuário com o campo Senha (sem o valor). A
  matriz da W21 tem o tipo de item "Permissões", e exportar o CSV da auditoria fica registrado como
  "Exportação" (item "Sistema"). Registros sem usuário (o `app.seed`) aparecem como "Sistema".
- **Fase 1, trigger da auditoria** também no SQLite do dev, e no PostgreSQL bloqueia também o
  TRUNCATE. Por isso os testes recriam o banco a cada teste em vez de apagar linhas.
- **Fase 1, regras de acesso a mais**: ninguém muda o próprio perfil nem se desativa; o sistema
  nunca fica sem admin ativo; o JWT leva a `session_version`, então trocar ou redefinir a senha
  derruba as outras sessões, e desativar derruba de vez (reativar não ressuscita o cookie antigo).
  Um link novo invalida o anterior do mesmo tipo, desativar invalida os pendentes e reativar quem
  nunca criou a senha volta para "Convite pendente". Login com limite de 10 falhas em 15 minutos
  por IP e e-mail (em memória); "Esqueci minha senha" com intervalo de 60 s por conta.
- **Fase 1, chave do JWT**: `QUESTPRO_SECRET_KEY` ou, sem ela, uma chave gerada uma vez em
  `<media>/.secret_key` (vale entre reinícios e entre os 2 workers do Docker atual).
- **Fase 1, links de uso único**: definir a senha pelo convite ou pela redefinição já deixa a
  pessoa logada. Sem SMTP, o link do "Esqueci minha senha" vai para o log da API. Validade: convite
  7 dias, redefinição 2 horas (configuráveis).
- **Fase 1, telas além dos protótipos**: W03 do convite com o mesmo título e o subtítulo "Olá,
  <nome>. Crie uma senha para começar a usar o sistema."; estado "Link inválido ou expirado";
  modal "Copie o link do convite/de redefinição" quando o e-mail não sai; página "Sem acesso";
  na W20, convite pendente mostra "Reenviar convite" no lugar da redefinição, e o status oferece
  "Convite pendente"/"Inativo". Os filtros da W19 e da W22 ficaram uns 15 px mais largos que no
  PNG (o Select da Fase 0 reserva 44 px para a seta e o texto cortava). A tabela da W21 aparece
  inteira (o PNG corta a última linha).
- **Fase 1, filtros na URL** (`?perfil=&status=&pagina=` na W19, `?periodo=&usuario=&acao=&item=`
  na W22), para a lista voltar igual. Períodos da W22: Hoje, Últimos 7/30/90 dias e Todo o
  período, calculados no fuso do navegador. CSV com `;` e BOM (abre direto no Excel), datas no fuso
  do navegador e células que começam com `=`, `+`, `-` ou `@` escapadas.
- **Fase 1, extras de infraestrutura**: `pool_pre_ping` no engine (conexão caída depois de
  reiniciar o PostgreSQL); `tzdata` nas dependências (fusos do CSV na imagem slim).
- **Fase 1, deploy** (pendências fechadas depois, a pedido do usuário, no branch
  `fase-1-pendencias`): o `docker-compose.yml` passou a repassar `QUESTPRO_PUBLIC_BASE_URL`
  (padrão `http://localhost:<porta>`), `QUESTPRO_SECRET_KEY`, `QUESTPRO_COOKIE_SECURE` e
  `QUESTPRO_SMTP_*`, sem mexer no resto (workers, proxy e TLS continuam para a Fase 8). A API avisa
  no log quando serve o site com os links apontando para `localhost`.
- **Fase 1, rotas antigas de leitura** (`GET /api/v1/sessions...`, também resolvido em
  `fase-1-pendencias`): com `QUESTPRO_API_KEY` definida, exigem o login do site ou a `X-Api-Key`;
  sem a chave (dev) continuam abertas, como a escrita. O `replay_session.py` manda a chave também
  ao acompanhar o status. Isso não decide nada sobre a tabela antiga, que segue para a Fase 3.
- **Fase 2, cadastro do paciente em multipart**: os campos em JSON (`data`) e o PDF
  (`consent_file`) vão numa requisição só, para o termo entrar no mesmo registro da auditoria. A
  edição é `PUT` (o formulário inteiro) e inativar/reativar, `PUT /patients/{id}/status`.
- **Fase 2, regras do TCLE** (o protótipo é estático): assinado exige a data; o PDF é opcional
  ("PDF não anexado" na W08), até 20 MB e conferido pelo `%PDF-`. Anexar o PDF ou digitar a data
  marca o termo como assinado; desmarcar limpa a data e tira o PDF (o arquivo sai do disco depois de
  salvar). Obrigatórios na W07: código, nome, nascimento, sexo e óculos. O código aceita letras,
  números, `.`, `-` e `_` (até 20), fica em maiúsculas e é único; o sugerido é o maior P-NNN + 1.
- **Fase 2, telas além dos protótipos**: W06 com o selo "Inativo" (sem "Nova sessão") e o subtítulo
  "N pacientes cadastrados e M inativos" quando o filtro está ligado; W08 com "Cadastrada",
  "Cadastrado" ou "Cadastro feito em … por …" conforme o sexo, "Não assinado", "Nenhuma observação."
  e o cartão neutro "Reativar paciente"; W09 com o selo "Arquivado" e os estados vazios; W11 com
  "Uso em sessões" quando nunca foi usado, "Arquivar ou excluir estímulo" (com "Excluir estímulo",
  confirmado num modal) para o que nunca foi usado, "Estímulo arquivado" com "Desarquivar estímulo",
  "Duração" nos vídeos e um aviso se a versão para o óculos falhar.
- **Fase 2, permissões**: excluir e desarquivar exigem "Arquivar estímulos"; ver a biblioteca exige só
  o login (a W21 não tem permissão de ver estímulos); o menu esconde Pacientes sem "Ver pacientes".
- **Fase 2, auditoria**: o paciente aparece pelo código (o CSV é uma exportação). "Salvar na
  biblioteca" é um registro só ("2 imagens e 1 vídeo enviados à biblioteca", como a W22), com uma
  linha por estímulo no "O que mudou"; com um estímulo só, o registro leva o nome e o link. Ação
  nova "Exclusão", para o estímulo nunca usado.
- **Fase 2, envio (W10)**: "Salvar na biblioteca" fica ativo durante o envio, como no PNG, e espera os
  arquivos terminarem; "Remover" só nos arquivos com erro, como no PNG; Cancelar ou fechar descarta
  os rascunhos, e os esquecidos somem em 24 h (`QUESTPRO_DRAFT_HOURS`). O formato vem do conteúdo:
  um MOV renomeado para .mp4 é recusado, e um PNG com extensão .jpg entra como PNG.
- **Fase 2, biblioteca sem paginação visível**: o PNG da W09 não mostra paginação; a lista carrega 48
  por vez e busca mais ao rolar ("Mostrar mais" fica de reserva).
- **Fase 2, mídia**: miniatura JPEG cobrindo 640 × 400. Versão para o óculos no mesmo formato, até
  2048 px e já girada pelo EXIF (o UE não lê a rotação); vídeo H.264 yuv420p com AAC e faststart,
  até 2048 px no lado maior, só remontado quando já está nesse formato. Imagens até 100 megapixels e
  arquivos até 1 GB (`QUESTPRO_MAX_STIMULUS_MB`). A versão só é gerada depois de salvar na
  biblioteca e é retomada ao subir a API. Com os 2 workers do Docker atual, um advisory lock faz só
  um retomar, e a limpeza de rascunhos é em lote (apagar a mesma linha duas vezes derrubava a subida).
- **Fase 2, filtros na URL** (`?q=&inativos=1&pagina=` na W06; `?q=&tipo=imagens|videos&etiqueta=&arquivados=1`
  na W09). O `useUrlFilters` também entrou na W19 e na W22: o `setSearchParams` do React Router parte
  dos parâmetros do último render, e dois filtros trocados em seguida se sobrescreviam (achado na
  verificação no navegador).
- **Fase 2, medidas**: o filtro de etiqueta tem 218 px (192 no PNG; o Select reserva 44 px para a
  seta e "Todas as etiquetas" cortava) e o nome do cartão é 17 px, como no PNG.
- **Fase 2, verificação**: além dos testes, o fluxo da fase rodou num Chromium headless
  (playwright-core numa pasta fora do repositório) contra o build servido pela API sobre PostgreSQL,
  com o `--demo`: W06 a W11, o .mov recusado, a versão para o óculos e os registros na auditoria.
- **Fase 3, fluxo antigo** (decidido com o usuário no início da fase): a tabela `sessions` virou
  `legacy_sessions`, com os dados, só leitura e sem tela; as rotas de leitura foram para
  `/api/v1/legacy/sessions` e o `DELETE` saiu. A ingestão antiga (`POST /sessions`, `/frames`,
  `/complete`, que ocupava a URL do assistente), o `replay_session.py`, o `make_synthetic_session.py`
  e `web/synthetic/` também saíram: **o app atual do óculos não consegue enviar até a Fase 7**. O
  `README`, o `DEPLOY.md` e o README do óculos ganharam avisos; a reescrita fica para a Fase 8.
- **Fase 3, visibilidade**: a sessão nasce privada e só quem tem "Alterar a visibilidade" a muda (na
  matriz padrão, só o Admin, como na W21). A lista da W18 traz os usuários ativos menos o responsável
  e quem já vê todas as sessões (no PNG o admin não aparece); "Pesquisadores escolhidos" exige pelo
  menos um, e voltar para "Só o responsável" ou "Todos" limpa a lista. A auditoria registra
  "Visibilidade" e "Pesquisadores com acesso" (nomes).
- **Fase 3, contagens**: W06, W08 e o "Usado em" da W11 só listam as sessões que a pessoa pode ver. A
  W11 conta todas (é o que impede a exclusão) e completa com "Mais N sessões de outros
  pesquisadores."; o paciente aparece só pelo código para quem não tem "Ver pacientes".
- **Fase 3, ordem dos pacientes** (W06 e etapa 1 da W13): pelo movimento mais recente, a última
  sessão ou o cadastro, o que for mais novo. Isso concilia os PNGs: na W13 a P-015, recém-cadastrada e
  sem sessão, vem primeiro; na W06 a ordem é a da última sessão.
- **Fase 3, W12**: a data é o início da sessão ou, antes de executar, a configuração. O período padrão
  é "Últimos 30 dias", como no PNG (mesmas opções da W22). "Todos os responsáveis" lista quem tem
  sessão visível para a pessoa. Preparar e Abrir controle só para o responsável com "Criar e
  executar"; os outros veem Abrir. Os selects ficaram uns 20 px mais largos que no PNG (o texto
  cortava, como na W19/W22).
- **Fase 3, W13** (o protótipo é estático):
  - etapa 1 com cinco pacientes ativos por vez e a linha "Mais N pacientes. Busque pelo nome ou
    código para encontrar outro."; com `?paciente=` o assistente abre direto nas Informações;
  - Título e Objetivo obrigatórios; Observações opcional;
  - imagem entra com 5 s; o tempo aceita de 0,1 a 3.600 s, com vírgula; vídeos não têm tempo (avançam
    sozinhos ao terminar). O total diz "cerca de" e, havendo troca manual, "mais de". A linha da
    revisão segue o PNG ("12 imagens, cerca de 1 min, com troca automática a cada 5 s") e muda para
    "com troca automática", "com troca manual" ou "com troca automática e manual";
  - "Nascida em", "Nascido em" ou "Nascimento em" conforme o sexo;
  - Salvar abre a W16; Salvar e preparar abre a preparação (placeholder até a Fase 4). Voltar,
    Trocar e Editar guardam o que já foi preenchido, mas sair do assistente descarta tudo;
  - a sequência também se reordena pelo teclado (espaço, setas, espaço), com anúncios em português.
- **Fase 3, duplicar**: "Duplicar para outro paciente" reabre o assistente (`?duplicar=`) com título,
  objetivo, observações, gravação e sequência copiados, um aviso no topo e o paciente a escolher; os
  estímulos arquivados ficam de fora (o aviso diz quantos). A sessão nova guarda a origem
  (`duplicated_from_id`, "Duplicada de" na auditoria e "Origem" na W16).
- **Fase 3, W16 antes dos dados**: "Configurada em" no lugar de "Data e hora", Duração "—", "N na
  sequência" e um cartão "Sequência da sessão" (Nº, Estímulo, Tipo, Tempo de tela) no lugar dos
  estímulos exibidos. O botão principal segue o status: Preparar sessão, Abrir controle ou Analisar
  dados. "Editar informações" edita no próprio cartão o título, o objetivo, as observações e, só
  enquanto Configurada, a gravação. O admin vê também Alterar visibilidade (como na W18).
- **Fase 3, verificação**: além dos testes (migrações também num PostgreSQL descartável), o fluxo
  rodou num Chromium headless contra o build servido pela API sobre PostgreSQL com o `--demo`: W12 e
  filtros, ordem da W06, assistente completo (arrastar com mouse e teclado), W16 com edição, Bruno sem
  acesso, admin compartilhando pela W18, Bruno com acesso, duplicar + Salvar e preparar, W08, W11,
  W22/W23 e W20.
- **Fase 4, decisões combinadas com o usuário** (com o protocolo, antes do hub): uma chave só para
  todos os óculos (`QUESTPRO_DEVICE_KEY`, vazia = aberta no dev), com cada óculos identificado pelo
  `deviceId` que ele gera e registrado na tabela `devices`; "Iniciar sessão" exige o eye tracking
  ativo, e o emotion tracking inativo só gera um aviso na W14.
- **Fase 4, rotas a mais**: `POST /sessions/{id}/release` ("Cancelar" da W14 manda o `unload`) e o
  retrato da sessão também por `GET /sessions/{id}/live`. O `devices/nearby` ficou em
  `/devices/nearby` (é do navegador, não da sessão).
- **Fase 4, retrato com versão**: a resposta de uma rota (ex.: o `prepare`) chegava depois do
  retrato mais novo vindo do WebSocket e o voltava ("0 de 1" depois de "1 de 1"; achado na
  verificação no navegador). O retrato ganhou `version` (microssegundos, cresce mesmo se a API
  reiniciar) e o site fica com o maior.
- **Fase 4, ciclo e fim**: a sessão começa na tela neutra (o pesquisador escolhe o 1º estímulo, como diz
  a W14); `previous` no primeiro e `next` depois da tela neutra do fim são ignorados. O fim pelo B
  fica na auditoria em nome do responsável, com o IP do óculos e o user-agent
  `NeuroSight/<versão> (<nome>; <modelo>)` ("App NeuroSight no Meta Quest" na W23). O óculos que volta
  sem a sessão em andamento encerra-a como `disconnected`; o JSON que chega sem o `ended` também
  encerra (com o `meta.endReason`). O `complete` só grava `data_received_at`: o status segue
  Aguardando dados até a Fase 5.
- **Fase 4, W14** (o protótipo é estático): o óculos que aparece na mesma rede é escolhido sozinho,
  uma vez; sem óculos, o cartão diz "Procurando o óculos / Nenhum óculos nesta rede ainda" e o campo
  vira "O óculos está em outra rede? Digite o código…"; pareado pelo código, "Pareado pelo código" e
  "Conectado pelo código de pareamento."; desconectado, selo "Desconectado". Os rastreamentos mostram
  Ativo, Sem permissão, Indisponível ou Desligado (o eye tracking inativo em vermelho, o facial em
  laranja). O rodapé muda conforme o que falta ("Aguarde o óculos carregar os estímulos.", "Marque que
  o óculos está no paciente para iniciar." etc.). Estímulo que não carrega aparece com "Tentar de
  novo". Cancelar libera o óculos e volta para a W16. Só o responsável (o `can_run`) vê a tela.
- **Fase 4, W15** (o protótipo é estático): na tela neutra, o cabeçalho diz "Antes do estímulo 1 de N"
  ou "Depois do estímulo N de M" e a legenda "Tela neutra" (no fim, "Fim da sequência. Aperte o B no
  óculos para encerrar."); com vídeo pausado o botão vira "Retomar vídeo"; as pílulas mostram "Sem
  gravação", "Óculos desconectado" (com um aviso e os comandos desligados) e os rastreamentos
  inativos. Vídeos tocam mudos na prévia, acompanhando a pausa (a sincronia é aproximada). Marcações
  da mais nova para a mais antiga. "Interromper sessão" pede confirmação num modal. Quando a sessão
  acaba (B ou interrupção), volta para a W16 com um aviso. Logo só com o traço (`Logo variant="mark"`).
  A prévia segue a proporção do PNG (1247 × 652).
- **Fase 4, simulador**: quadros a 10 fps por padrão (`--frame-fps`; o `meta.capture.fps` diz o que foi
  gravado), facial a 30 Hz, cache dos estímulos e envios pendentes em `~/.neurosight-simulador`.
- **Fase 4, deploy**: o compose passou a repassar `QUESTPRO_DEVICE_KEY` e o `.env.example` traz as
  variáveis da captura; o `Dockerfile` continua com 2 workers até a Fase 8 (o `DEPLOY.md` avisa que a
  execução ao vivo exige 1). Os placeholders de tela cheia saíram (não sobrou nenhum).
- **Fase 4, verificação**: além dos testes (migrações também num PostgreSQL descartável), o fluxo
  rodou num Chromium headless contra o build servido pela API (SQLite, `--demo`) com dois simuladores:
  W14 achando o óculos pela rede e trocando para outro pelo código (o primeiro recebeu o `unload`),
  carregamento, início, próximo, tela neutra, anterior, clique na sequência, troca automática,
  marcação e o B (`--auto-end`) levando a Aguardando dados com o envio completo; sessão com vídeo
  (pausar e retomar) interrompida pelo modal; queda do óculos no meio (W15 "Óculos desconectado") e a
  volta dele encerrando a sessão como `disconnected`; W22 e W23 com o início e o fim.
- **Fase 5, decisões combinadas com o usuário** (no início da fase): as sessões de exemplo executadas
  ganham dados sintéticos (o gerador do simulador foi para `app/synthetic.py`, porque a imagem Docker
  não leva `web/scripts`); a queda (`disconnected`) termina como Interrompida, e não como Concluída (a
  sugestão da Fase 4); e uma linha por exibição: o estímulo que volta à tela aparece de novo nos
  "Estímulos exibidos", na tira da W17 e no CSV, com as próprias métricas (o plano dizia "uma linha
  por estímulo"; sem repetição, dá no mesmo).
- **Fase 5, I-DT com junção**: além de 1° e 100 ms, fixações vizinhas a menos de 75 ms e 0,5° viram
  uma. Sem isso, o ruído do próprio simulador (σ perto de 0,1°) partia de 1 a 6 fixações por sessão
  (as de até 600 ms chegam perto de 1° de amplitude); com a junção, a contagem bate com a gerada. A
  duração vai do primeiro ao último instante mais um período de amostragem (sem viés), e os dois
  parâmetros do plano viraram `QUESTPRO_FIXATION_*`.
- **Fase 5, onde ficam os resultados**: em `sessions.analysis` e `session_exposures`, como no plano,
  mas com o JSON grande adiado (`deferred`) para não pesar nas listas; o mapa de calor é uma grade de
  80 × 80 (as células com olhar), e não as amostras, para não crescer com a duração; as séries
  guardadas são só as três da legenda padrão, e as 70 expressões entram como média por exibição no CSV.
- **Fase 5, validação no envio**: o `PUT tracking` confere o contrato inteiro (seção 4.2 do protocolo)
  e responde 422 com o caminho do problema; `meta.capture` virou obrigatório quando há `frames` (um
  teste da Fase 4 mandava frames sem ele).
- **Fase 5, ingestão**: o status só muda no fim do processamento; uma falha deixa Aguardando dados com o
  motivo (aviso na W16) e é tentada de novo ao subir a API; o `complete` repetido numa sessão já
  processada responde 200 com o status final; um JSON reenviado reabre o envio até o próximo
  `complete`. Os frames JPEG continuam no disco ao lado do MP4.
- **Fase 5, W16** (o protótipo é estático): "N exibidos" conta os estímulos distintos; antes dos dados,
  a sequência continua, com um aviso ("O óculos ainda está enviando…", "…estão sendo processados…" ou
  a falha), e a página se atualiza a cada 5 s; "Analisar dados" só com os dados prontos; sem gravação,
  "Sessão sem gravação"; sem "Exportar os dados", os arquivos aparecem sem Baixar. A W15 já leva o
  status novo para a W16 ao terminar. Medidas do PNG: linhas de 48 px, miniaturas de 48 × 30, colunas
  de 654 e 397 px, marcações em 15 px e o detalhe dos arquivos em 14 px.
- **Fase 5, W17** (o protótipo é estático): a exibição escolhida fica na URL (`?exibicao=N`) e
  escolher leva a gravação ao começo dela; o cursor do gráfico segue a gravação (sem gravação, fica no
  começo da exibição); a tira também anda pelas setas; o gráfico tem faixas clicáveis (e pelo
  teclado), marcações com o texto cortado antes da próxima e o eixo de tempo em passos de 5 s a 1 h.
  O mapa de calor usa o tempo de olhar das amostras válidas (σ de 4% da largura, perto de 2°), e a
  trajetória, as fixações numeradas. A gravação fica numa tela de 16:10, como no PNG, com o quadro
  contido (o óculos grava 1024 × 1024 por padrão). Estados a mais: sem gravação, sem facial, sem
  estímulo exibido e dados não processados. Os textos da W17 no PNG são menores que os da W16
  (títulos de 18 px, apoio de 15 px, rótulos de 14 px e valores de 22 px).
- **Fase 5, simulador**: a coleta passou a ser estrita (`< t`), para a amostra do instante da troca ir
  para a tela nova; a piscada no rosto usa a amostra de olhar do mesmo instante (antes, a última do
  trecho, o que no relógio virtual errava as piscadas); o vídeo é lido em sequência e a imagem é
  reduzida uma vez só; o `--truth` traz as amostras de cada exibição.
- **Fase 5, PostgreSQL**: dois problemas que o SQLite dos testes não pega, achados na verificação: o
  `FOR UPDATE` com os joins automáticos (paciente e responsável) é recusado (agora trava só a linha da
  sessão), e o JSONB não guarda a ordem das chaves (a API ordena as séries pela legenda).
- **Fase 5, teste instável da W13**: "Salvar e preparar leva à preparação" já falhava às vezes no commit
  anterior (2 de 3 rodadas da suíte inteira): o `findBy` achava o título do estado "carregando" da W14,
  que era trocado antes do `expect`. Virou `waitFor`.
- **Fase 5, verificação**: além dos testes (migrações também num PostgreSQL descartável), o fluxo rodou
  num Chromium headless contra o build servido pela API sobre PostgreSQL com o `--demo`: W16 e W17 das
  sessões de exemplo comparadas com os PNGs (medidas e larguras de texto), e uma sessão nova com o
  simulador (duas imagens com tempo, uma de troca manual e um vídeo; marcação, pausa e retomada,
  Anterior repetindo um estímulo e o B automático): W16 de Aguardando dados a Concluída, 6 exibições
  com início, fim, amostras e fixações iguais às do `--truth` e o tempo até a 1ª fixação a até 14 ms,
  a gravação tocando com o círculo, o JSON baixado idêntico ao enviado, o CSV, o MP4 e as três
  Exportações na W22 e na W23.
- **Fase 6, decisões combinadas com o usuário** (no início da fase): a variação dos KPIs do mês compara
  com o mesmo trecho do mês anterior (1 a 6 de outubro contra 1 a 6 de setembro), e não com o mês
  inteiro; as linhas de tendência mostram as últimas 8 semanas; e o `--demo` passou a datar os registros
  da auditoria (usuários, pacientes, estímulos e sessões na data do que representam) e a registrar o
  início e o fim das sessões executadas (o fim pelo B com o user-agent do óculos). Só vale para bancos
  semeados de novo; antes, tudo caía em "hoje".
- **Fase 6, rota a mais**: `GET /dashboard/badge`, porque o menu consulta o selo em todas as telas e o
  `/dashboard` inteiro é mais pesado.
- **Fase 6, o que cada número conta** (o protótipo é estático): uma sessão conta no período em que
  começou (as Configuradas não entram); "Pacientes acompanhados" são os pacientes distintos dessas
  sessões; "Tempo de coleta" soma `ended_at − started_at` das já encerradas; "Aguardando dados" vai do fim
  da execução até o `data_received_at` (a linha é um retrato no fim de cada semana, e o último ponto é o
  valor do cartão). Em "Usuários ativos", o "+N" são os ativos cadastrados no mês e a linha usa a data
  de cadastro, porque não há histórico de quando cada um passou a ativo. "Registros na auditoria hoje"
  compara com ontem até a mesma hora. Sem mudança ou sem base de comparação, a variação some, e o
  rodapé diz "neste mês" no lugar de "desde <mês>".
- **Fase 6, W04** (o protótipo é estático):
  - o subtítulo vai por extenso até dez ("Uma sessão está…", "Três sessões precisam…") e tem a versão
    "Nenhuma …"; a seção "Precisam de atenção" vazia diz "Nenhuma sessão em andamento ou aguardando dados.";
  - "Últimas ações da auditoria" deixa os logins de fora (como no PNG, que mostra 7 registros hoje e só 3
    ações do dia); o número do cartão conta todos;
  - "Sessões recentes" deixa de fora as Em andamento, como os dois PNGs (que omitem a da P-014), porque
    elas já estão em "Precisam de atenção";
  - horários "Iniciada às 14:10", "ontem às …" ou "em dd/mm/aaaa às …"; depois do fim, "recebendo dados",
    "processando os dados" ou "falha no processamento", e no cartão "em envio", "processando" ou "com
    falha";
  - "Abrir controle" só para o responsável com "Criar e executar"; os outros veem "Ver sessão". Os botões
    do topo seguem as permissões (Novo paciente, Enviar estímulos, Nova sessão);
  - a página se atualiza a cada 30 s. Abaixo de 1180 px, os KPIs ficam em 2 × 2 e o horário desce para
    baixo da sessão; o `PageHeader` deixa as ações descerem quando falta largura (a 1024 px, os três
    botões espremiam o "Olá, Carlos"), sem mudar nada nas larguras dos protótipos.
- **Fase 6, `UtcDateTime`**: passa a converter para UTC também na ida. O SQLite descartava o fuso de um
  horário fora de UTC (o começo do mês em São Paulo virava 00:00 UTC); no PostgreSQL não mudava nada.
- **Fase 6, verificação**: além dos testes, um PostgreSQL descartável com o `--demo` e a API servindo o
  build. Um conferidor fora do repositório recalculou com SQL próprio todos os números do `/dashboard`
  (Ana e Carlos: KPIs, mês anterior, linhas, atenção, recentes e auditoria), e todos bateram. Depois, num
  Chromium headless com o simulador, a sessão nova de Ana foi preparada e iniciada pela W14: o Início
  passou de duas a três sessões (selo 2 → 3, "Abrir controle" para Ana e "Ver sessão" com o responsável
  para o admin, "Iniciou a sessão …" na auditoria). Depois do B, "processando os dados" e a Concluída:
  selo de volta a 2, "Sessões no mês" +1, "Tempo de coleta" +20,0 s (a duração da sessão), a sessão no
  topo das recentes com 2 estímulos e "Encerrou a sessão …" na auditoria. Capturas a 1440 e 1024 px.
- **Depois da Fase 6, transição entre as telas** (pedido do usuário; os protótipos são estáticos): os
  layouts usam o `PageTransition` (`src/layouts/`) no lugar do `<Outlet />`. A página nova entra com fade
  e 8 px de subida em 0,2 s, como os modais (sem animação com "reduzir movimento"), e uma navegação nova
  começa do topo; voltar e avançar deixam a rolagem com o navegador. A tela é o caminho: mudar só os
  parâmetros (filtros, página, `?exibicao=`) não anima, e trocar de caminho recria a página (antes,
  `/sessoes/A` → `/sessoes/B` reaproveitava o componente). Para o `AppLayout`, as abas da Administração
  são uma tela só, e o `AdminLayout` anima só o conteúdo da aba. Layout novo: use `<PageTransition />`.

---

## Contexto
O repositório é o sistema da IC: um app Unreal que grava o olhar numa **cena 3D** e uma
plataforma web que só **recebe e mostra** sessões. A descrição nova do projeto e os 38
protótipos em `web/docs/pages/` pedem outro produto. O pesquisador cadastra pacientes e
estímulos (imagens e vídeos), configura a sessão no site, **controla ao vivo** o que o Meta
Quest Pro mostra, coleta **olhar e expressões faciais** e analisa os dados depois. Há dois perfis
(Admin e Pesquisador), permissões editáveis, visibilidade das sessões e auditoria.

- **Pesquisador**: cadastra pacientes, envia estímulos, cria, executa e analisa sessões.
- **Admin**: tudo isso, mais usuários, permissões, visibilidade e auditoria.
- **Paciente**: só um cadastro; não usa o site. As sessões ficam vinculadas a ele.
- **Fluxo**: o óculos fica aguardando → o site configura e envia a sessão → o óculos baixa os
  estímulos → o pesquisador controla a apresentação → o botão B encerra → o óculos envia o JSON e
  a gravação → o servidor guarda e processa → análise no site.
- O óculos mostra **só imagens e vídeos** (nada de cena 3D como estímulo), numa sala neutra.
- **A API fica num servidor remoto**, fora do laboratório.

## Estado do código antes da Fase 0
- **Backend** (`web/backend/app`, cerca de 540 linhas):
  - FastAPI com SQLAlchemy 2 síncrono e **uma tabela só** (`models.py`, `sessions`, com o olhar
    em JSON/JSONB). O banco é criado por `create_all` (`db.py`), sem Alembic e sem schemas
    Pydantic. Não há log nem testes.
  - A única proteção é uma API key opcional (`security.py`); todas as leituras são públicas.
  - Ingestão em três passos, create/frames/complete (`routers/ingest.py`), com o MP4 montado em
    background pelo ffmpeg do imageio-ffmpeg (`services/video.py`). O storage em disco fica em
    `services/storage.py`.
  - O Docker sobe com `--workers 2`.
  - **Falha de segurança**: o fallback da SPA (`main.py`, `spa_fallback`) faz `os.path.join` com
    um caminho vindo do usuário, o que permite ler arquivos fora da pasta (ex.: `GET //etc/passwd`).
- **Frontend** (`web/frontend/src`, cerca de 1.400 linhas):
  - React 18, react-router 6, Vite 5 e TS strict, com um CSS global de tema escuro (`styles.css`).
  - Só duas páginas: a lista de sessões e o viewer.
  - Reaproveitável: o heatmap em canvas com splatting gaussiano (`heatmap/heatmapEngine.ts`) e o
    modo de validação com mira (`heatmap/HeatmapOverlay.tsx`).
  - Não há login, formulários, testes ou lint, e `tsc` falha por falta de `@types/node`.
- **Óculos** (`headset/`, UE 5.5):
  - Um único ator, `AGazeRecorderActor` (`Source/EyeTrackingQuestPro/GazeRecorderActor.cpp`),
    sobre o VR Template.
  - O olhar vem do OpenXR (`UEyeTrackerFunctionLibrary::GetGazeData`, com `XrApi=NativeOpenXR`).
    O ator faz raycast na cena 3D e projeta o ponto em UV de câmera.
  - Os frames são capturados por SceneCapture com `ReadPixels` **síncrono**, o que derruba a
    amostragem para 22 Hz.
  - O upload é por HTTP ao apertar B, com a URL fixa no construtor.
  - Não há **rastreamento facial** (`bFaceTrackingEnabled=False`), canal de comando vindo do site,
    carregamento de estímulos nem UI própria.
  - Bugs: segurar B dispara `StopSessionAndQuit` em todo tick, e B também abre o menu do template.
  - **Não regredir** (ver `headset/README.md`): `XrApi=NativeOpenXR`, `bEyeTrackingEnabled=True`,
    `bPackageDataInsideApk=True`. Nunca rodar o Meta XR Setup Tool.
- **Contrato atual** do `gaze.json`: `meta{captureFovDeg,frameWidth,frameHeight,videoFps,uvOrigin}`,
  `frames[{idx,t,file}]` e `samples[{t,valid,world,uv,confidence}]`.

## Decisões de arquitetura
0. **Telas = protótipos.** O frontend implementa exatamente as telas de `web/docs/pages/`
   (W01–W23 e componentes), e o app do óculos implementa as Q01–Q04. As duas páginas atuais
   saem; delas fica só a lógica do heatmap e da mira.
1. **API num servidor remoto; site ↔ óculos via esse servidor (WebSocket)**. O óculos abre uma
   conexão de saída para `wss://<servidor>/api/v1/device/ws`, autenticada pela chave do
   dispositivo, e o navegador abre outra para a sessão ao vivo. O servidor guarda num hub em
   memória quais dispositivos estão online e repassa comandos e estados; por causa desse hub, a
   API roda com **1 worker**. Como o servidor fica fora do laboratório:
   - **"Mesma rede" (W14)** significa que navegador e óculos chegam ao servidor pelo **mesmo IP
     público** (o NAT do laboratório). Para isso o proxy precisa repassar o IP real:
     `X-Forwarded-For` no proxy e `--proxy-headers`/`forwarded-allow-ips` no uvicorn. Se a rede
     usar vários IPs de saída, entra o código de pareamento de 4 dígitos, **atribuído pelo
     servidor** no `hello`.
   - **HTTPS/WSS é obrigatório**: proxy reverso com TLS automático (Caddy), upgrade de WebSocket,
     e limite de corpo e timeouts que aguentem uploads longos. O óculos valida o certificado com
     o bundle de CAs do UE.
   - **A gravação (centenas de MB por sessão) sobe pela internet.** O upload é retomável por nome
     de arquivo e roda depois do B. Resolução, fps e qualidade da captura são configuráveis, para
     caber na banda do laboratório.
   - **Os estímulos também descem pela internet** na preparação (Q02). Por isso existe a versão
     reduzida para o óculos, e o cache por sha256 evita baixar de novo o que já está no aparelho.
2. **O óculos é dono da reprodução**. Ele guarda a sequência e os timers das imagens, avança os
   vídeos ao terminarem e registra o instante real de cada troca. O site só envia intenções
   (próximo, anterior, ir para N, tela neutra, pausar/retomar). Assim os tempos de início dos
   estímulos não dependem da latência da rede, e uma queda do Wi-Fi não para a coleta. Depois do
   último estímulo, o óculos mostra a tela neutra até o B.
3. **Ciclo de status**: Configurada → Em andamento → Aguardando dados → Concluída ou Interrompida.
   O motivo do fim fica em `end_reason` (botão B, interrompida pelo pesquisador, queda). Uma
   sessão interrompida também envia o que coletou. O app do óculos guarda localmente os uploads
   pendentes e os retoma ao reabrir.
4. **Contrato v2 do JSON**. `meta` traz sessão, dispositivo, versão do app, início em UTC,
   geometria do painel, captura e nomes das 70 expressões. Depois vêm:
   - `stimuli[]`;
   - `events[]`: `stimulus_on/off`, `neutral_on/off`, `video_pause/resume`, `session_start/end`;
   - `gaze[]`: `t`, `valid`, `conf`, `onStim`, `stimUv` (UV no estímulo original, já
     descontadas as faixas pretas) e `frameUv` (para desenhar o círculo sobre a gravação);
   - `face`: `t[]` e `weights[][]` em colunas, mais as confianças;
   - `frames[]`.
   O documento fica em `docs/protocolo-oculos.md` e é escrito no início da Fase 4, **antes** do
   código do óculos. As marcações (W15) ficam só no servidor, com `t` calculado a partir do
   início da sessão.
5. **Rastreamento facial** por um plugin próprio do projeto, `headset/Plugins/NeuroSightXR`
   (`LoadingPhase: PostConfigInit`), que implementa `IOpenXRExtensionPlugin` com
   `XR_FB_face_tracking2` (70 blendshapes). Ele convive com o `XR_EXT_eye_gaze_interaction` já
   validado e não exige voltar ao OVRPlugin. Um arquivo `_APL.xml` acrescenta a permissão
   `com.oculus.permission.FACE_TRACKING` e o `uses-feature` `oculus.software.face_tracking`.
6. **Gravação**: continua o pipeline de frames JPEG → upload em lotes → MP4 no servidor, que já
   foi validado. Mudanças: o readback vira **assíncrono** (`FRHIGPUTextureReadback`) e a amostragem
   do olhar se desacopla da captura, com meta de 72 Hz ou mais. A retomada passa a usar a lista de
   nomes já recebidos, em vez de uma contagem.
7. **Estímulos no servidor**: ao receber um arquivo, o servidor verifica os magic bytes
   (JPG/PNG/MP4), extrai resolução e duração, gera miniatura e uma versão para o óculos (imagem
   com até 2048 px; vídeo H.264 com faststart). Tudo usa o ffmpeg do imageio-ffmpeg e o OpenCV,
   que já são dependências. O óculos baixa os arquivos, guarda em cache por sha256, mostra imagens
   via `FImageUtils::ImportFileAsTexture2D` e vídeos via Media Framework (plugin ElectraPlayer),
   com áudio.
8. **Autenticação e acesso**:
   - Cookie httpOnly com JWT. O usuário é recarregado a cada request, então um usuário inativado
     é bloqueado na hora. Senhas com argon2.
   - Convites e redefinições usam tokens de uso único, guardados como hash e com validade.
     A senha atual continua valendo até o link de redefinição ser usado.
   - E-mail por SMTP configurável. Sem SMTP, o admin vê e copia o link; no compose de dev, Mailpit.
   - As permissões ficam na tabela `role_permissions`, semeada com a matriz da W21. "Gerenciar
     usuários" e "alterar permissões" ficam travadas para o Admin no servidor.
   - A auditoria é só de inserção (trigger no Postgres bloqueia UPDATE/DELETE) e guarda IP,
     user-agent e o diff antes/depois.
   - Exportações e a tela de análise identificam o paciente só pelo código.
9. **Frontend** mantém React 18, Vite 5 e Router 6, e passa para **CSS Modules** com tokens
   globais no tema claro dos protótipos (o tema escuro sai). A fonte Inter vem de `@fontsource`,
   sem CDN. Bibliotecas novas:
   - TanStack Query para os dados do servidor;
   - react-hook-form + zod para formulários;
   - @dnd-kit para ordenar a sequência;
   - lucide-react para ícones.
   Os gráficos (sparkline e expressões) são SVG próprios, sem biblioteca. O heatmap reaproveita
   `heatmapEngine.ts` com uma escala de azul. Os uploads com progresso usam XHR.
10. **Mantidos**: o prefixo `QUESTPRO_` e os nomes de volumes e banco, para não quebrar o deploy.
    A marca da interface passa a ser NeuroSight.

## Telas por fase (arquivos em `web/docs/pages/`)

| Fase | Protótipos |
|---|---|
| 0 | `Componente · Menu lateral.png`, `Componente · Painel da marca.png` |
| 1 | `W01 · Login.png`, `W02 · Esqueci minha senha.png`, `W02 · Link enviado.png`, `W03 · Definir nova senha.png`, `W05 · Meu perfil.png`, `W19 · Lista de usuários.png`, `W20 · Novo usuário.png`, `W20 · Editar usuário.png`, `W21 · Perfis e permissões.png`, `W22 · Auditoria.png`, `W23 · Detalhes do registro.png` |
| 2 | `W06 · Lista de pacientes.png`, `W07 · Novo paciente.png`, `W07 · Editar paciente.png`, `W08 · Detalhes do paciente.png`, `W09 · Biblioteca de estímulos.png`, `W10 · Envio de estímulos.png`, `W11 · Detalhes do estímulo.png`, `Componente · Miniatura do estímulo.png` |
| 3 | `W12 · Lista de sessões.png`, `W13 · Etapa 1 paciente.png`, `W13 · Etapa 2 informações.png`, `W13 · Etapa 3 estímulos.png`, `W13 · Etapa 4 revisão.png`, `W16 · Detalhes da sessão.png` (cabeçalho, resumo, informações), `W18 · Visibilidade da sessão.png` |
| 4 | `W14 · Preparação da sessão.png`, `W15 · Controle da sessão ao vivo.png` |
| 5 | `W16 · Detalhes da sessão.png` (estímulos exibidos, marcações, arquivos), `W17 · Análise da sessão.png` |
| 6 | `W04 · Início (admin).png`, `W04 · Início (pesquisador).png` |
| 7 | `Q01 · Início do aplicativo.png`, `Q02 · Carregamento da sessão.png`, `Q03 · Apresentação dos estímulos.png`, `Q04 · Encerramento e envio.png`, `Componente · Ambiente do óculos.png` |

## Especificação extraída dos protótipos
Resumo para orientar; **o PNG é a referência final** de textos e layout.

**Visual**:
- Tema claro, fonte Inter.
- Cores (aproximadas, conferir nos PNGs): azul primário perto de `#3B5BEB`, fundo da página
  `#F5F6FA`, cartões brancos com cantos arredondados, texto azul-marinho perto de `#1B2340`.
- Selos de status:
  - Em andamento: azul com ponto;
  - Aguardando dados: laranja;
  - Configurada: contorno cinza;
  - Interrompida: vermelho;
  - Concluída: verde;
  - Ativo: verde; Convite pendente: laranja; Inativo: cinza.
- Zona de perigo: cartão com borda vermelha e botão vermelho de contorno.
- Datas `dd/mm/aaaa`, horários relativos ("Hoje, 14:10", "Ontem, 17:30"), vírgula decimal
  ("5,0 s", "2,8 MB").

**Menu lateral**:
- Itens: Início, Sessões (selo com o número de sessões em andamento ou aguardando dados),
  Pacientes, Estímulos e Administração (só para quem tem permissão).
- Embaixo: avatar com iniciais, nome e perfil (leva a Meu perfil) e "Sair" em vermelho.
- A W15 é em tela cheia, sem menu.

**Autenticação** (W01–W03), com o painel da marca à direita:
- W01: e-mail e senha com olho, "Esqueci minha senha", "Ainda não tem acesso? Peça ao
  administrador do sistema."
- W02: e-mail → "Confira seu e-mail" com "Enviar de novo".
- W03: senha com regras marcadas ao vivo (≥ 8 caracteres, maiúsculas e minúsculas, número,
  símbolo) e confirmação. A mesma tela serve para aceitar o convite.

**W04 Início**:
- Admin:
  - KPIs: Usuários ativos (com convites pendentes), Sessões no mês (variação contra o mês
    anterior), Aguardando dados (nome da sessão "em envio"), Registros na auditoria hoje ("o
    último às …").
  - Listas: Precisam de atenção (com "Ver sessão"), Últimas ações da auditoria, Sessões recentes
    (com o responsável).
- Pesquisador:
  - KPIs: Sessões no mês, Pacientes acompanhados, Aguardando dados, Tempo de coleta no mês.
  - Listas: Precisam de atenção (com "Abrir controle" para a sessão em andamento) e Suas
    sessões recentes (com a contagem de estímulos).
- Ambos: KPIs com sparkline e variação; ações Novo paciente, Enviar estímulos e Nova sessão.

**W05 Meu perfil**: nome, e-mail e perfil só para leitura ("definidos pelo administrador"), e
alterar senha (atual, nova com as regras, confirmação).

**Pacientes** (W06–W08):
- W06:
  - Busca por nome ou código, "Mostrar inativos" e 8 por página.
  - Colunas: Código, Nome, Nascimento, Sessões, Última sessão.
  - Ações: Editar e Nova sessão (o wizard abre com o paciente escolhido).
- W07:
  - Identificação: código P-NNN sugerido, "identifica o paciente nas análises e exportações,
    sem expor o nome"; nome; nascimento; sexo (Feminino, Masculino, Prefiro não informar).
  - Experimento: óculos ou lentes (Não, Óculos de grau, Lentes de contato); TCLE assinado, com
    data e PDF anexado; observações.
  - Na edição: "As alterações ficam registradas na auditoria".
- W08:
  - Idade, termo com "Ver termo (PDF)", situação.
  - Histórico de sessões (Sessão, Data, Responsável, Estímulos, Status).
  - Inativar paciente: "sai das listas e não recebe novas sessões; os dados continuam
    guardados".

**Estímulos** (W09–W11):
- W09:
  - Cards com miniatura (selo de duração nos vídeos), nome, tipo e etiquetas.
  - Busca por nome ou etiqueta, Todos/Imagens/Vídeos, filtro de etiqueta, "Mostrar arquivados".
  - Subtítulo com as contagens.
- W10 (modal):
  - Arrastar e soltar; formatos JPG, PNG e MP4.
  - Cada arquivo sobe na hora, com progresso e tamanho. Formato errado mostra "Formato não
    aceito" com Remover.
  - Ao selecionar um arquivo: Nome (vem do nome do arquivo), Descrição e Etiquetas.
  - "Salvar na biblioteca" confirma os rascunhos; Cancelar descarta.
- W11:
  - Prévia, formato, resolução, tamanho, enviado por e em.
  - Edição de nome, descrição e etiquetas.
  - "Usado em N sessões".
  - Arquivar: o que já foi usado não pode ser excluído; o arquivado sai da biblioteca e não
    entra em novas sessões.

**Sessões**:
- W12:
  - Subtítulo "Suas sessões e as que outros pesquisadores liberaram para você".
  - Busca por título ou paciente; filtros de status, responsável e período.
  - Colunas: Sessão + paciente, Responsável, Data, Status, Visibilidade (Privada, Compartilhada,
    Aberta a todos).
  - Ação conforme o status: Abrir controle, Preparar ou Abrir.
- W13 (wizard):
  - Etapa 1: busca e lista de pacientes, com "Cadastrar paciente".
  - Etapa 2: paciente com Trocar; Título, Objetivo, Observações, "Gravar a sessão".
  - Etapa 3: biblioteca (busca, abas, Adicionar/Adicionado) e sequência arrastável. Cada imagem
    tem o tempo em segundos; em branco, a troca é manual. Total: "N estímulos, cerca de X min".
  - Etapa 4: revisão com Editar por bloco; Salvar ou Salvar e preparar. "A sessão fica com o
    status Configurada até ser executada".
- W14 (preparar):
  - Checklist: mesma rede (automático), app aberto no óculos, "o óculos está no paciente" (marcado
    à mão).
  - Cartão do óculos: nome, "Encontrado na rede", Conectado, Eye tracking, Emotion tracking,
    Gravação, mais o campo de código de pareamento.
  - "Estímulos no óculos: N de M carregados". Iniciar sessão só quando tudo estiver pronto.
- W15 (ao vivo):
  - Topo: Gravando, Óculos conectado, Eye tracking, Emotion tracking, tempo de sessão e
    Interromper sessão.
  - "Em exibição no óculos" com "Estímulo N de M" e a forma de troca.
  - Controles: Anterior, Tela neutra, Pausar vídeo (desligado em imagens), Próximo estímulo.
  - Aviso "Para encerrar, aperte o botão B".
  - Sequência clicável (Exibido, Em exibição, Pendente) e marcações com o tempo da sessão.
- W16 (detalhes):
  - Título com o status; ações Duplicar para outro paciente e Analisar dados (Alterar
    visibilidade para quem tem permissão).
  - Resumo: responsável, data e hora, duração, estímulos exibidos, gravação, visibilidade.
  - Informações com Editar; "Os dados coletados não podem ser alterados".
  - Estímulos exibidos (Nº, estímulo, início, tempo de tela), marcações, arquivos (JSON e MP4
    com tamanho e Baixar).
- W17 (análise):
  - Baixar JSON e Baixar CSV por estímulo; tira numerada de estímulos.
  - "Estímulo N: nome, exibido de mm:ss a mm:ss", com as abas Mapa de calor e Trajetória do olhar
    sobre o estímulo.
  - Métricas: fixações, duração média da fixação, tempo até a 1ª fixação, amostras válidas.
  - Gravação da sessão com o círculo do olhar, sincronizada com o estímulo e o gráfico.
  - Gráfico "Expressões faciais ao longo da sessão": intensidade de 0 a 1, faixas listradas por
    estímulo (clicar seleciona), linhas das marcações e cursor do tempo atual.
  - Legenda padrão: Sobrancelha interna elevada, Canto da boca puxado, Olhos fechados.
- W18 (modal de visibilidade):
  - Só o responsável, Pesquisadores escolhidos (lista com busca) ou Todos os pesquisadores.
  - "A mudança fica registrada na auditoria".

**Administração** (abas Usuários, Perfis e permissões, Auditoria):
- W19:
  - Busca e filtros de perfil e status.
  - Status: Ativo, Convite pendente, Inativo. O próprio usuário tem o selo "Você".
  - Ações: Editar, Desativar, Reenviar convite, Ativar. "Usuários não são excluídos, só
    desativados".
- W20:
  - Novo: nome, e-mail, perfil com descrição → "Salvar e enviar convite", e o cartão "Como o
    acesso é liberado".
  - Editar: também o status, e o cartão de Acesso (último acesso, criado em e por, sessões como
    responsável) com "Enviar redefinição de senha".
- W21: matriz com 12 permissões.

  | Grupo | Permissão | Admin | Pesquisador |
  |---|---|---|---|
  | Pacientes | Ver pacientes | ✓ | ✓ |
  | Pacientes | Cadastrar e editar | ✓ | ✓ |
  | Pacientes | Inativar | ✓ | – |
  | Estímulos | Enviar e editar | ✓ | ✓ |
  | Estímulos | Arquivar | ✓ | – |
  | Sessões | Criar e executar | ✓ | ✓ |
  | Sessões | Ver de outros pesquisadores | ✓ | – |
  | Sessões | Alterar visibilidade | ✓ | – |
  | Sessões | Exportar dados | ✓ | ✓ |
  | Administração | Gerenciar usuários | ✓ (travada) | – |
  | Administração | Alterar permissões | ✓ (travada) | – |
  | Administração | Consultar auditoria | ✓ | – |

  Botões Descartar e Salvar, desligados quando não há mudanças.
- W22:
  - Filtros de período, usuário, ação e tipo de item; Exportar CSV; 10 por página.
  - Colunas: data e hora, usuário, ação (Login, Criação, Edição, Mudança de visibilidade, Início
    de sessão, Fim de sessão, Exportação), item afetado (tipo + descrição), IP, Detalhes.
  - "Somente leitura".
- W23 (modal):
  - Quem (com o perfil) e De onde (IP + navegador e sistema).
  - Item afetado com link.
  - Tabela "O que mudou" com Campo, Antes e Depois.

**Óculos** (sala neutra cinza com piso em grade; painéis flutuantes azul-marinho):
- Q01:
  - Selo "Aguardando sessão" e "Pronto para receber a sessão".
  - Nome do óculos e código de pareamento.
  - Linhas de rede, eye tracking e rastreamento facial.
- Q02: "Recebendo sessão", título e código do paciente, "Estímulos no óculos N de M".
- Q03: o estímulo numa tela plana grande.
- Q04: "Enviando os dados", com o JSON (enviado) e a gravação (%).
- **Ajustes combinados**:
  - O OpenXR não informa a calibração, então mostrar "Ativo" (permissão + extensão OK).
  - O SSID exige permissão de localização, então mostrar "Conectado ao servidor" e o IP.

---

## Fases
Cada fase termina testável. Os critérios de "pronto" valem para a revisão.

### Fase 0: Base técnica
- **Backend**:
  - Alembic com uma baseline **igual ao esquema atual**, para dar `alembic stamp head` no banco
    que já está no servidor.
  - `models/` e `schemas/` Pydantic divididos por domínio; logging; endpoints `def` para I/O
    bloqueante.
  - Corrigir o path traversal do fallback da SPA.
  - pytest com TestClient e SQLite temporário.
- **Frontend**:
  - Dependências da decisão 9, mais `@types/node`, vitest e Testing Library. Scripts `typecheck`
    e `test`; o build passa a rodar o typecheck.
  - Tokens do tema claro. Componentes de base: Button, TextField, PasswordField com as regras,
    Textarea, Select, Checkbox, RadioCard, Tabs, Segmented, SearchInput, Table, Pagination,
    StatusBadge, Tag, TagInput, Card, StatCard com sparkline, Modal, Stepper, Dropzone com
    progresso via XHR, Avatar, Toast, DangerZone, PageHeader com o link de voltar.
  - `AppLayout` com o menu lateral e `AuthLayout` com o painel da marca.
  - Rotas de todas as telas como placeholders.
  - Cliente da API com tratamento de erro e redirecionamento no 401.
  - Proxy `/api` com `ws: true`. Marca NeuroSight no título, favicon e nomes.
  - As páginas antigas saem; `src/heatmap/` fica para a Fase 5.
- **Pronto quando**:
  - `pytest`, `npm run typecheck`, `npm test` e `npm run build` passam.
  - O app abre com o menu lateral e as rotas placeholder.
  - `GET //etc/passwd` não devolve o arquivo.

### Fase 1: Contas, permissões e auditoria
- **Tabelas** `users`, `auth_tokens`, `role_permissions` e `audit_log`, com a trigger que bloqueia
  UPDATE/DELETE no Postgres.
- **Rotas**:
  - `auth`: login, logout, esqueci, redefinir, aceitar convite;
  - `me`: perfil e troca de senha;
  - `users`: lista com filtros, criar com convite, editar, ativar/desativar, reenviar convite,
    enviar redefinição;
  - `permissions`: ler e salvar a matriz;
  - `audit`: lista com filtros, detalhe e CSV em streaming.
- **Serviços**: senhas, tokens, e-mail (SMTP ou link para copiar), dependência
  `require_permission(...)` e `audit.record(...)` com diff. O login também é auditado.
- **`python -m app.seed`**: cria o primeiro admin e mostra o link de convite, e semeia a matriz
  padrão. Com `--demo`, cria também usuários de exemplo.
- **Frontend**: as telas da fase, guarda de rotas por permissão e o item Administração
  condicional no menu.
- **Pronto quando**:
  - o admin convida um pesquisador, ele cria a senha pelo link e entra;
  - desativar bloqueia o acesso na hora;
  - a matriz muda o que o pesquisador vê;
  - cada ação aparece na auditoria com o diff.

### Fase 2: Pacientes e estímulos
- **`patients`**: código P-NNN sugerido, TCLE em PDF com download autenticado, inativar e
  reativar.
- **`stimuli` + `stimulus_tags`**:
  - Upload de um arquivo por request, para ter progresso por arquivo. O arquivo fica como
    rascunho até "Salvar na biblioteca".
  - Processamento de mídia da decisão 7, com a versão para o óculos gerada em background.
  - Arquivar; excluir só se nunca foi usado.
- "Usado em N sessões" e "Histórico de sessões" ficam vazios até a Fase 3.
- **Pronto quando**:
  - dá para cadastrar, editar, inativar e reativar paciente com PDF;
  - JPG, PNG e MP4 são aceitos e um `.mov` é recusado;
  - os filtros por tipo e etiqueta funcionam;
  - arquivar funciona.

### Fase 3: Configuração de sessões
- **Antes de tudo**, confirmar a decisão em aberto sobre o fluxo antigo.
- **Tabelas**: a nova `sessions` (com `type` padrão "fluxo de imagens e vídeos", `status`,
  `record`, `visibility`, responsável e paciente), `session_stimuli` (posição e duração),
  `session_shares` e `session_markers` (usada na Fase 4).
- **Visibilidade**: o usuário vê a sessão se for o dono, OU se ela estiver aberta a todos, OU
  compartilhada com ele, OU se tiver a permissão "ver de outros".
- **Funcionalidades**: wizard, duplicar para outro paciente, editar informações e alterar
  visibilidade, as duas com auditoria. Ligar "Usado em" e "Histórico de sessões" da Fase 2.
- **Pronto quando**: dá para criar uma sessão Configurada pelo wizard, editar, duplicar e mudar a
  visibilidade, e a lista filtra corretamente para cada usuário.

### Fase 4: Execução ao vivo + simulador
- **Primeiro**, escrever `docs/protocolo-oculos.md` (mensagens do WebSocket, rotas do dispositivo,
  JSON v2). Ele também guia a Fase 7.
- **Backend**:
  - `services/live_hub.py` (dispositivos, pareamento, vínculo com a sessão, broadcast) e a
    tabela `devices`.
  - WebSockets do dispositivo e do navegador.
  - REST: `prepare`, `start`, `control`, `interrupt`, `markers`, `devices/nearby`.
  - Rotas do dispositivo: download dos estímulos, `tracking` (recebe e guarda o JSON v2),
    `frames`, `complete`.
  - Transições Configurada → Em andamento → Aguardando dados, com o início e o fim auditados.
- **`web/scripts/device_simulator.py`**: substitui o `replay_session.py` e emula o óculos.
  - Faz o hello, mostra o código, baixa os estímulos e obedece aos comandos.
  - Gera olhar e expressões sintéticos, com fixações de posição e duração conhecidas.
  - Faz o upload ao "apertar B" (Enter ou `--auto-end`).
- **Pronto quando**, usando o simulador:
  - o preparo acha o dispositivo pelo IP ou pelo código e chega a "M de M carregados";
  - dá para iniciar, avançar, voltar, mostrar a tela neutra, pausar e marcar;
  - o "B" leva a sessão de Em andamento para Aguardando dados.

### Fase 5: Ingestão e análise
- **Ingestão**: validação do JSON v2 e montagem do MP4, reaproveitando `services/video.py`.
- **`services/analysis.py`** com numpy:
  - segmentação por estímulo a partir dos eventos;
  - fixações por I-DT (1°, 100 ms; graus calculados pela geometria do painel);
  - fixações, duração média, tempo até a 1ª fixação e % de amostras válidas;
  - séries de expressões reamostradas para cerca de 10 Hz.
  Os resultados ficam em `sessions.analysis` (JSONB) e em `session_exposures`.
- **Status final** Concluída ou Interrompida.
- **Downloads**: JSON bruto, CSV com uma linha por estímulo e o MP4, com Exportação auditada.
- **Frontend**:
  - W16 completa;
  - W17: heatmap reaproveitando `heatmapEngine.ts` com paleta azul, trajetória, gravação com o
    círculo do olhar (reaproveita o modo de validação) e gráfico de expressões em SVG.
- **Pronto quando**: a sessão do simulador vira Concluída e a W17 mostra métricas que batem com o
  que o simulador gerou (com testes automatizados).

### Fase 6: Início
- `GET /dashboard` com os KPIs e as séries de cada perfil, "Precisam de atenção" e o número do
  selo do menu.
- **Pronto quando**: os números batem com os dados do `--demo` e com a sessão do simulador.

### Fase 7: App do óculos (Windows + UE 5.5; pode começar depois do protocolo da Fase 4)
- **Classes C++ novas**:
  - `UNeuroSightSettings` (DeveloperSettings, com override por `Saved/neurosight.json` enviado via
    adb), que substitui a URL fixa;
  - `UNeuroSightSubsystem`, a máquina de estados Q01 → Q02 → pronto → Q03 → Q04;
  - cliente WebSocket (módulo `WebSockets`, com reconexão e heartbeat);
  - `FStimulusCache`, para baixar com progresso;
  - `AStimulusScreen`: plano com material dinâmico, ajuste de proporção e tela neutra;
  - `UGazeRecorderComponent`, refatorado do ator atual, com interseção no plano e readback
    assíncrono;
  - `FSessionWriter` para o JSON v2 com flush periódico;
  - `FSessionUploader` com fila persistente.
- **Botão B**: só vale no estado "rodando", com trigger *Pressed* e debounce. Tirar o B do menu do
  template.
- **Plugin `NeuroSightXR`** (decisão 5) e pedido em tempo de execução das permissões EYE e FACE.
- **Log** com categoria própria `LogNeuroSight`.
- **Passo a passo no editor** em `headset/docs/`, para o usuário executar, porque `.uasset` não se
  gera pelo terminal:
  - mapa da sala neutra (reaproveita os materiais de grade de `LevelPrototyping`);
  - `M_StimulusScreen`;
  - 3 widgets UMG sobre classes C++ com `BindWidget`;
  - pawn simplificado, sem teleporte, menu ou arma;
  - ativar ElectraPlayer.
- **Pronto quando**:
  - o target de editor compila com `Build.bat`;
  - no aparelho, o fluxo Q01 → Q04 completa uma sessão real, que aparece Concluída no site com
    olhar e expressões.

### Fase 8: Deploy e documentação
- **Compose**: 1 worker, Caddy com TLS e WebSocket, Mailpit no perfil dev e as variáveis novas
  (SMTP, `PUBLIC_BASE_URL`, chave do dispositivo, proxies confiáveis para o IP real).
- **Documentação**: `DEPLOY.md`, `README.md`, `web/README.md` e `headset/README.md` atualizados.
- **Pronto quando**: `docker compose up` sobe tudo com HTTPS, e o simulador funciona apontando para
  o servidor.

## Riscos
- **Compilar e testar o C++ do óculos exige o Windows com UE 5.5 e o Quest Pro.**
- Verificar se o `openxr.h` do UE 5.5 já define `XR_FB_face_tracking2`; se não definir, declarar
  as structs localmente. O usuário precisa ativar "Expressões faciais naturais" no Quest.
- O Python 3.14 local pode não ter wheels de alguma dependência; nesse caso, usar `uv` com 3.12,
  igual ao Docker.
- Banda do laboratório para subir a gravação, mitigada pela decisão 1.

## Verificação ponta a ponta (depois da Fase 5)
1. Subir `uvicorn` + `npm run dev` (ou `docker compose up`) e rodar `python -m app.seed --demo`.
2. Logar como admin e convidar um pesquisador (link no Mailpit ou copiado).
3. Cadastrar um paciente e enviar estímulos.
4. Criar a sessão pelo wizard.
5. Rodar `device_simulator.py`, preparar, iniciar, controlar e marcar.
6. Encerrar e ver Aguardando dados → Concluída.
7. Conferir a análise, os downloads e os registros na auditoria.

Há também um teste de fumaça com Playwright desse fluxo.

## Convenções
- **Idioma**: comentários, docstrings, mensagens de erro, textos da UI e commits em português.
  Identificadores em inglês, JSON da API em snake_case, contrato do óculos em camelCase.
- **Python**:
  - cada módulo abre com uma docstring do porquê;
  - routers usam `router = APIRouter()` e são montados em `main.py` com o prefixo;
  - `Depends(get_db)`;
  - SQLAlchemy 2 (`select()`, `db.get`, `db.scalars`).
- **TypeScript**:
  - sem ponto e vírgula, aspas simples, 2 espaços, vírgula final;
  - componentes como `export default function Nome()`;
  - `import type` em linha separada;
  - páginas terminam em `Page`.
- **UE C++**: prefixos A/F/U, `b` em bools, `TObjectPtr` em UPROPERTY, `TEXT()`, comentários em
  português, `#if PLATFORM_ANDROID` nas partes do Android.
- **Commits**: em português, sem linhas de coautoria ou de "Generated with Claude Code".

---

## Como iniciar uma fase numa nova sessão
Cole o prompt abaixo trocando `<N>` e `<nome>`, e acrescente o complemento da fase, se houver.

```text
Estou implementando o NeuroSight (monorepo: web/ = FastAPI + React, headset/ = Unreal 5.5 para o Meta Quest Pro).

Leia primeiro, por inteiro, o docs/PLANO-IMPLEMENTACAO.md. Ele tem o contexto, as decisões de arquitetura, a especificação das telas, as convenções e a seção "Status das fases", que diz o que as sessões anteriores já fizeram.

Tarefa desta sessão: implementar a Fase <N> (<nome>) do plano.

Antes de escrever código:
1. Confira no git e no código se as fases anteriores estão como o Status diz. Se algo não bater, me avise antes de continuar.
2. Abra os protótipos desta fase em web/docs/pages/ (lista em "Telas por fase") e siga-os fielmente: textos, campos, estados e ações.
3. Leia o código que vai mudar e reaproveite o que já existe.
4. Se alguma decisão do plano não se encaixar no código real, me pergunte em vez de improvisar.

Para fechar a fase:
- Testes e typecheck passando. Suba a aplicação e verifique o fluxo da fase de ponta a ponta (a partir da Fase 4, com web/scripts/device_simulator.py no lugar do óculos).
- Atualize no plano as seções "Status das fases" e "Registro de desvios".
- Faça commit num branch fase-<N>-<nome-curto>, com mensagens em português e sem linhas de coautoria ou de "Generated with Claude Code". Não faça push.
- Termine com um resumo: o que foi feito, como verificou e o que ficou pendente.
```

**Complementos por fase**:
- **Fase 3**: "Antes de mexer na tabela sessions atual, me pergunte sobre a decisão em aberto do
  fluxo antigo."
- **Fase 4**: "Comece por docs/protocolo-oculos.md e me mostre antes de implementar o hub."
- **Fase 7**:
  > Esta sessão roda no clone do Windows, com o UE 5.5 instalado. Valide o C++ compilando o
  > target de editor com Build.bat; não abra o editor. O que exigir o editor (mapa, material,
  > widgets, input) vai num passo a passo em headset/docs/ para eu executar. Não altere XrApi,
  > bEyeTrackingEnabled nem bPackageDataInsideApk, e não edite .uasset/.umap pelo terminal.
- **Fase 8**: "Antes de mudar o docker-compose e o DEPLOY.md, me pergunte o domínio do servidor e
  se ele já tem um proxy reverso."
