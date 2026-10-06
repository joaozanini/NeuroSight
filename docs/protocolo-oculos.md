# NeuroSight: protocolo entre o óculos e o servidor

Contrato entre o app do Meta Quest Pro (Fase 7), o servidor (Fase 4) e o simulador
`web/scripts/device_simulator.py`, que faz o papel do óculos até o app novo existir. Quem mudar
uma mensagem, uma rota ou o JSON muda este documento junto.

- O servidor fica **fora do laboratório**. O óculos só faz conexões de saída: um WebSocket
  permanente e requisições HTTP para baixar os estímulos e enviar os dados.
- O **óculos é dono da reprodução** (decisão 2 do plano): ele guarda a sequência, conta o tempo das
  imagens, avança os vídeos ao terminarem e registra o instante real de cada troca. O site só manda
  intenções (próximo, anterior, ir para N, tela neutra, pausar, retomar). Uma queda da rede não para
  a coleta.
- Mensagens e JSON do óculos em **camelCase**; as rotas do site (navegador) seguem o snake_case do
  resto da API.

## 1. Identidade e autenticação

| O quê | Como |
|---|---|
| Endereço | `QUESTPRO_*` no servidor; no óculos, a URL base vem de `UNeuroSightSettings` (`https://<servidor>`). Tudo abaixo é relativo a `/api/v1`. |
| Chave do dispositivo | Uma chave compartilhada, `QUESTPRO_DEVICE_KEY` no servidor, enviada pelo óculos no cabeçalho `X-Device-Key` (no WebSocket, nos cabeçalhos do upgrade). Vazia = aberta (só no dev; o servidor avisa no log). Chave errada: HTTP 401 e, no WebSocket, fechamento com o código `4401`. |
| Id do óculos | `deviceId`: texto estável (até 64 caracteres, `[A-Za-z0-9._-]`), gerado pelo app na primeira execução e guardado no aparelho. Vai no `hello` e no cabeçalho `X-Device-Id` das rotas HTTP. |
| Nome | `name`, configurado no app ("Quest Pro 01"), aparece na W14 e na Q01. |

O servidor guarda cada óculos que já se conectou na tabela `devices` (id, nome, modelo, versão do
app, último IP, visto pela última vez). A sessão executada guarda o `device_id`, e só esse óculos
envia os dados dela.

## 2. WebSocket do óculos: `wss://<servidor>/api/v1/device/ws`

Cada mensagem é um objeto JSON em texto, com o campo `type`. Campos desconhecidos são ignorados
dos dois lados (assim dá para acrescentar campos sem quebrar a outra ponta).

### 2.1 Conexão, código de pareamento e batimento

1. O óculos conecta e manda `hello` em até 10 s (senão o servidor fecha com `4400`).
2. O servidor responde `welcome` com o **código de pareamento** de 4 dígitos, único entre os
   óculos conectados. Numa reconexão, o servidor tenta devolver o mesmo código.
3. O óculos manda `ping` a cada 15 s; o servidor responde `pong`. Sem nada recebido em 45 s, o
   servidor considera o óculos desconectado e fecha. O óculos reconecta sozinho (1 s, 2 s, 4 s...
   até 30 s) e manda um `hello` novo com o estado atual, que restaura o vínculo com a sessão
   (inclusive depois de o servidor reiniciar, já que o hub fica só em memória).
4. Um segundo `hello` com o mesmo `deviceId` (outra conexão) derruba a conexão antiga (`4409`).

```jsonc
// óculos → servidor
{
  "type": "hello",
  "protocol": 1,
  "deviceId": "questpro-7f3a9c",
  "name": "Quest Pro 01",
  "model": "Quest Pro",
  "appVersion": "1.0.0",
  "tracking": { "eye": "active", "face": "active" },
  // Estado atual: idle (Q01), loading (Q02), ready (carregado, sala neutra), running (Q03),
  // uploading (Q04). Fora de idle, vem a sessão e o que for do estado.
  "state": "running",
  "sessionId": "9c1e...",
  "load": { "loaded": 12, "total": 12 },
  "playback": { "position": 3, "neutral": false, "paused": false, "shown": [1, 2, 3], "lastCommandId": 17 }
}

// servidor → óculos
{ "type": "welcome", "pairingCode": "4827", "serverTime": "2026-10-06T14:10:00.123Z" }
```

`tracking.eye` e `tracking.face`: `active` (permissão concedida e extensão OpenXR ligada; o OpenXR
não informa a calibração), `no_permission`, `unavailable` (extensão ausente ou recurso desligado
nas configurações do Quest) ou `off` (desligado no app). Quando mudam (ex.: a permissão foi
concedida depois), o óculos manda `{"type": "status", "tracking": {...}}`.

### 2.2 Preparação (W14 → Q02)

Quando o pesquisador escolhe este óculos na W14 (pelo IP ou pelo código), o servidor manda `load`.
O óculos sai da Q01, mostra a Q02 e baixa o que não estiver no cache (a chave do cache é o
`sha256`). Um `load` novo substitui o anterior; `unload` volta para a Q01.

```jsonc
// servidor → óculos
{
  "type": "load",
  "session": {
    "id": "9c1e...",
    "title": "Rostos neutros e expressivos",
    "patientCode": "P-015",
    "record": true,
    // Captura da gravação (configurável no servidor, para caber na banda do laboratório).
    "capture": { "width": 1024, "height": 1024, "fps": 30, "jpegQuality": 80 },
    "stimuli": [
      {
        "position": 1,
        "stimulusId": "a41f...",
        "name": "Rosto neutro 01",
        "kind": "image",               // image | video
        "format": "jpg",               // jpg | png | mp4 (versão para o óculos)
        "url": "/api/v1/device/sessions/9c1e.../stimuli/a41f...",
        "sha256": "5d1c...",           // do arquivo que a url devolve
        "sizeBytes": 412345,
        "width": 2048, "height": 1365, // do arquivo que a url devolve
        "screenSeconds": 5.0,          // só imagens; null = troca manual
        "mediaSeconds": null,          // só vídeos: duração
        "hasAudio": null               // só vídeos
      }
    ]
  }
}
{ "type": "unload", "sessionId": "9c1e..." }

// óculos → servidor: a cada arquivo pronto (e logo no início, com o que já estava no cache)
{ "type": "load_progress", "sessionId": "9c1e...", "loaded": 9, "total": 12 }
// se um arquivo não puder ser baixado ou aberto (o óculos tenta 3 vezes antes)
{ "type": "load_failed", "sessionId": "9c1e...", "stimulusId": "a41f...", "message": "sha256 não confere" }
```

Com `loaded == total`, o óculos fica `ready`: mostra só a sala neutra até o início (texto da Q02).

### 2.3 Execução (W15 → Q03)

```jsonc
// servidor → óculos: o pesquisador clicou em "Iniciar sessão"
{ "type": "start", "sessionId": "9c1e...", "startedAt": "2026-10-06T14:26:03.512Z" }

// servidor → óculos: intenções do pesquisador
{ "type": "command", "sessionId": "9c1e...", "commandId": 17, "action": "next" }
// action: next | previous | goto (com "position": N) | neutral | pause | resume

// servidor → óculos: "Interromper sessão" na W15
{ "type": "interrupt", "sessionId": "9c1e..." }

// óculos → servidor: depois de QUALQUER mudança do que está na tela (comando ou troca automática)
{
  "type": "state",
  "sessionId": "9c1e...",
  "state": "running",
  "t": 36.52,                // segundos desde o início, no relógio do óculos
  "position": 3,             // cursor da sequência (null antes do primeiro estímulo)
  "neutral": false,          // tela neutra no lugar do estímulo
  "paused": false,           // vídeo pausado
  "shown": [1, 2, 3],        // posições que já apareceram ao menos uma vez
  "lastCommandId": 17
}

// óculos → servidor: o paciente/pesquisador apertou B (ou a sessão foi interrompida)
{ "type": "ended", "sessionId": "9c1e...", "reason": "button_b", "t": 312.4 }
```

Regras da reprodução, que o óculos aplica:

- Ao iniciar, a coleta começa com a **tela neutra** (`position: null`): o pesquisador escolhe o
  primeiro estímulo (texto da W14).
- `next` mostra `position + 1` (ou 1, antes do primeiro); depois do último, mostra a tela neutra e
  fica nela até o B. `previous` mostra `position − 1` (no mínimo 1). `goto` mostra a posição pedida,
  mesmo que já exibida. Comandos sem efeito (ex.: `previous` no primeiro) são ignorados.
- `neutral` troca o estímulo pela tela neutra e mantém o cursor; `next`/`previous`/`goto` saem dela.
- Imagem com `screenSeconds` avança sozinha quando o tempo acaba; sem tempo, espera o pesquisador.
  A contagem recomeça do zero sempre que a imagem volta à tela.
- Vídeo avança sozinho ao terminar. `pause`/`resume` só valem com um vídeo na tela; o vídeo que sai
  da tela e volta recomeça do início.
- O B só vale no estado `running` (*pressed*, com debounce). Ao receber `interrupt`, o óculos encerra
  como se fosse o B, com `reason: "interrupted"`.
- O óculos responde ao `interrupt` e aos `command` mesmo que eles cheguem atrasados; um `command` de
  outra sessão é ignorado.

### 2.4 Encerramento e envio (Q04)

Depois do `ended`, o óculos vai para `uploading` e envia os dados pelas rotas HTTP da seção 3 (o
JSON primeiro, depois os frames). Os envios pendentes ficam guardados no aparelho e são retomados ao
reabrir o app, até o `complete` responder 200. Terminado o envio, volta para a Q01.

Se a rede cair durante a sessão, o óculos continua coletando e guarda as mensagens `state` e `ended`
que não saíram: ao reconectar, o `hello` traz o estado atual e, se a sessão já acabou, o `ended`
pendente vai logo depois. Mesmo que o `ended` se perca, o envio do JSON (com `meta.endReason`)
encerra a sessão no servidor.

### 2.5 Erros

```jsonc
{ "type": "error", "code": "unknown_session", "message": "sessão não encontrada" }
```

Códigos de fechamento do WebSocket: `4400` hello inválido ou ausente, `4401` chave errada, `4408`
sem batimento, `4409` substituído por outra conexão do mesmo óculos.

## 3. Rotas HTTP do óculos

Todas com `X-Device-Key` e `X-Device-Id`. Os downloads aceitam `Range` (retomar arquivo grande).

| Rota | Para quê |
|---|---|
| `GET /device/sessions/{sessionId}/stimuli/{stimulusId}` | Versão do estímulo para o óculos. Só para o óculos vinculado à sessão. |
| `PUT /device/sessions/{sessionId}/tracking` | O JSON v2 (seção 4), `Content-Type: application/json`, até 512 MB. Reenviar substitui. |
| `GET /device/sessions/{sessionId}/frames` | `{"received": ["000001.jpg", ...]}`: o que já chegou, para retomar. |
| `POST /device/sessions/{sessionId}/frames` | Lote de JPEGs em multipart, campo `frames` (sugestão: 20 por lote), nome `NNNNNN.jpg`. Resposta `{"saved": [...], "rejected": [...], "receivedCount": N}`. Reenviar um nome sobrescreve. |
| `POST /device/sessions/{sessionId}/complete` | Fim do envio. Resposta `{"status": "awaiting_data", "missingFrames": [...]}`; se faltar frame listado no JSON, o óculos reenvia e chama de novo. |

Respostas de erro: `401` chave, `403` óculos que não é o da sessão, `404` sessão inexistente,
`409` estado que não aceita a operação (ex.: enviar dados de uma sessão que nunca começou), `422`
JSON fora do contrato (com `detail`).

## 4. JSON v2 da sessão (`tracking`)

Um arquivo por sessão, escrito pelo óculos durante a coleta (com flush periódico) e enviado ao fim.
Tempos `t` em **segundos desde `session_start`**, no relógio monotônico do óculos, com 3 casas ou
mais. UVs normalizados de 0 a 1, **origem no canto superior esquerdo**.

```jsonc
{
  "version": 2,
  "meta": {
    "sessionId": "9c1e...",
    "device": { "id": "questpro-7f3a9c", "name": "Quest Pro 01", "model": "Quest Pro" },
    "appVersion": "1.0.0",
    "startedAt": "2026-10-06T14:26:03.530Z",   // UTC, relógio do óculos
    "endedAt": "2026-10-06T14:31:15.930Z",
    "endReason": "button_b",                    // button_b | interrupted
    // Painel plano onde os estímulos aparecem, em metros, e a distância dos olhos até ele.
    // Com isso o servidor converte UV em graus de ângulo visual (fixações por I-DT).
    "panel": { "widthM": 2.4, "heightM": 1.35, "distanceM": 2.0 },
    // Gravação do que o paciente viu. null quando a sessão não é gravada.
    "capture": { "width": 1024, "height": 1024, "fps": 30, "fovDeg": 90 },
    "gazeHz": 72,
    // Nomes das expressões de XR_FB_face_tracking2, na ordem das colunas de face.weights.
    // null quando o rastreamento facial não está ativo.
    "faceExpressions": ["BROW_LOWERER_L", "...", "TONGUE_RETREAT"]
  },
  // A sequência como o óculos a recebeu.
  "stimuli": [
    { "position": 1, "stimulusId": "a41f...", "kind": "image", "sha256": "5d1c...",
      "width": 2048, "height": 1365, "screenSeconds": 5.0, "mediaSeconds": null }
  ],
  // Tudo o que mudou na tela, em ordem de t.
  "events": [
    { "t": 0.0,    "type": "session_start" },
    { "t": 0.0,    "type": "neutral_on" },
    { "t": 4.215,  "type": "neutral_off" },
    { "t": 4.215,  "type": "stimulus_on",  "position": 1, "stimulusId": "a41f...", "cause": "command" },
    { "t": 9.216,  "type": "stimulus_off", "position": 1, "stimulusId": "a41f..." },
    { "t": 9.216,  "type": "stimulus_on",  "position": 2, "stimulusId": "b77e...", "cause": "auto" },
    { "t": 20.5,   "type": "video_pause",  "position": 4 },
    { "t": 24.0,   "type": "video_resume", "position": 4 },
    { "t": 312.4,  "type": "session_end",  "reason": "button_b" }
  ],
  // Uma amostra por leitura do olhar (meta: 72 Hz ou mais).
  "gaze": [
    {
      "t": 4.229,
      "valid": true,            // o OpenXR deu um olhar válido
      "conf": 1.0,              // confiança (0 a 1)
      "onStim": true,           // o olhar caiu dentro da área do estímulo (sem as faixas pretas)
      "stimUv": [0.512, 0.488], // posição no estímulo ORIGINAL; null fora dele ou na tela neutra
      "frameUv": [0.507, 0.493] // posição no quadro da gravação; null fora do quadro ou sem gravação
    }
  ],
  // Expressões faciais em colunas (o rastreamento facial tem a própria taxa).
  "face": {
    "t": [4.231, 4.245],
    "weights": [[0.01, 0.0, "... 70 valores de 0 a 1 ..."], ["..."]],
    // Confiança de XR_FB_face_tracking2 por região: [parte de baixo, parte de cima].
    "confidence": [[0.98, 0.95], [0.97, 0.95]]
  },
  // Quadros da gravação, na ordem; o MP4 é montado no servidor. [] sem gravação.
  "frames": [ { "idx": 1, "t": 0.012, "file": "000001.jpg" } ]
}
```

- **Estímulo dentro do painel**: o estímulo aparece inteiro, centralizado e com a proporção
  preservada (*contain*), e o resto do painel fica preto. A área ocupada sai das dimensões em
  `stimuli[]` e de `meta.panel`; `stimUv` já desconta as faixas.
- **Tela neutra**: entre `neutral_on` e `neutral_off` não há estímulo; `onStim` é `false`.
- **Vídeo pausado**: a imagem parada continua na tela; o olhar continua valendo para o estímulo.
- `face` é `null` sem rastreamento facial; `frames` é `[]` sem gravação.

### 4.1 As 70 expressões (`XR_FB_face_tracking2`)

Na ordem de `XrFaceExpression2FB`, sem o prefixo `XR_FACE_EXPRESSION2_` e o sufixo `_FB`. O que vale
é a lista em `meta.faceExpressions`; esta é a referência.

```
BROW_LOWERER_L BROW_LOWERER_R CHEEK_PUFF_L CHEEK_PUFF_R CHEEK_RAISER_L CHEEK_RAISER_R
CHEEK_SUCK_L CHEEK_SUCK_R CHIN_RAISER_B CHIN_RAISER_T DIMPLER_L DIMPLER_R EYES_CLOSED_L
EYES_CLOSED_R EYES_LOOK_DOWN_L EYES_LOOK_DOWN_R EYES_LOOK_LEFT_L EYES_LOOK_LEFT_R
EYES_LOOK_RIGHT_L EYES_LOOK_RIGHT_R EYES_LOOK_UP_L EYES_LOOK_UP_R INNER_BROW_RAISER_L
INNER_BROW_RAISER_R JAW_DROP JAW_SIDEWAYS_LEFT JAW_SIDEWAYS_RIGHT JAW_THRUST LID_TIGHTENER_L
LID_TIGHTENER_R LIP_CORNER_DEPRESSOR_L LIP_CORNER_DEPRESSOR_R LIP_CORNER_PULLER_L
LIP_CORNER_PULLER_R LIP_FUNNELER_LB LIP_FUNNELER_LT LIP_FUNNELER_RB LIP_FUNNELER_RT
LIP_PRESSOR_L LIP_PRESSOR_R LIP_PUCKER_L LIP_PUCKER_R LIP_STRETCHER_L LIP_STRETCHER_R
LIP_SUCK_LB LIP_SUCK_LT LIP_SUCK_RB LIP_SUCK_RT LIP_TIGHTENER_L LIP_TIGHTENER_R LIPS_TOWARD
LOWER_LIP_DEPRESSOR_L LOWER_LIP_DEPRESSOR_R MOUTH_LEFT MOUTH_RIGHT NOSE_WRINKLER_L
NOSE_WRINKLER_R OUTER_BROW_RAISER_L OUTER_BROW_RAISER_R UPPER_LID_RAISER_L UPPER_LID_RAISER_R
UPPER_LIP_RAISER_L UPPER_LIP_RAISER_R TONGUE_TIP_INTERDENTAL TONGUE_TIP_ALVEOLAR
TONGUE_FRONT_DORSAL_PALATE TONGUE_MID_DORSAL_PALATE TONGUE_BACK_DORSAL_VELAR TONGUE_OUT
TONGUE_RETREAT
```

A legenda padrão da W17 usa `INNER_BROW_RAISER` (Sobrancelha interna elevada), `LIP_CORNER_PULLER`
(Canto da boca puxado) e `EYES_CLOSED` (Olhos fechados), com a média dos lados L e R.

## 5. Lado do site (navegador)

Para referência; o óculos não usa estas rotas.

| Rota | Para quê |
|---|---|
| `GET /devices/nearby` | Óculos conectados com o mesmo IP público do navegador e livres (W14, "Encontrado na rede"). |
| `POST /sessions/{id}/prepare` | `{"device_id": "..."}` ou `{"pairing_code": "4827"}`: vincula o óculos e manda o `load`. |
| `POST /sessions/{id}/release` | "Cancelar" da W14: desfaz o vínculo e manda o `unload`. |
| `POST /sessions/{id}/start` | Configurada → Em andamento (auditado como "Início de sessão") e manda o `start`. |
| `POST /sessions/{id}/control` | `{"action": "next" \| "previous" \| "goto" \| "neutral" \| "pause" \| "resume", "position": N}`. |
| `POST /sessions/{id}/interrupt` | Em andamento → Aguardando dados, motivo "interrompida pelo pesquisador" (auditado como "Fim de sessão"); manda o `interrupt`. |
| `GET`/`POST /sessions/{id}/markers` | Marcações da W15, com `t` calculado no servidor a partir de `started_at`. |
| `GET /sessions/{id}/live` | Retrato do que está acontecendo (abaixo). |
| `WS /sessions/{id}/live` | O mesmo retrato, enviado de novo a cada mudança. Login pelo cookie do site. |

Preparar, iniciar, controlar, interromper e marcar exigem "Criar e executar sessões" **e** ser o
responsável pela sessão (o `can_run` da Fase 3). O retrato:

```jsonc
{
  "type": "live",
  // Cresce a cada mudança (em microssegundos, continua crescendo se a API reiniciar). A resposta de
  // uma rota pode chegar depois de um retrato mais novo vindo do WebSocket: vale o de versão maior.
  "version": 1791297963512004,
  "session_id": "9c1e...",
  "status": "running",
  "started_at": "2026-10-06T14:26:03.512Z",
  "device": {
    "id": "questpro-7f3a9c", "name": "Quest Pro 01", "online": true, "pairing_code": "4827",
    "same_network": true, "paired_by": "network",   // network | code
    "state": "running", "tracking": { "eye": "active", "face": "active" }
  },
  "nearby": [],                                      // só antes de vincular um óculos
  "load": { "loaded": 12, "total": 12, "error": null },
  "playback": { "position": 3, "neutral": false, "paused": false, "shown": [1, 2, 3] }
}
```

### Ciclo do status e motivo do fim

| De | Para | Quando | `end_reason` |
|---|---|---|---|
| Configurada | Em andamento | `start` (W14) | |
| Em andamento | Aguardando dados | `ended` do óculos (B) | `button_b` |
| Em andamento | Aguardando dados | "Interromper sessão" (W15) | `interrupted` |
| Em andamento | Aguardando dados | o óculos voltou sem a sessão (o app fechou no meio) ou o JSON chegou sem o `ended` | `disconnected` ou o `meta.endReason` |
| Aguardando dados | Concluída ou Interrompida | processamento dos dados (Fase 5) | |

O "Início de sessão" e o "Fim de sessão" ficam na auditoria em nome do responsável. No fim pelo B,
o IP e o navegador do registro são os do óculos ("NeuroSight 1.0.0, Quest Pro 01").
