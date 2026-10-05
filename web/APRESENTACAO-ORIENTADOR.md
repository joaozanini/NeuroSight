# Sistema de Coleta e Visualização de Rastreamento Ocular em RV — Visão Técnica

**Aluno:** João Zanini
**Plataforma-alvo:** Meta Quest Pro (eye tracking integrado) · build standalone Android

Sistema completo para **aquisição, transporte, armazenamento e análise visual de dados de
rastreamento ocular** em ambientes de Realidade Virtual: um aplicativo nativo no headset
(Unreal Engine 5.5, C++) e uma plataforma web (FastAPI + PostgreSQL + React) que recebe as
sessões e as exibe com sobreposição de mapa de calor. Ao final, o pedido de infraestrutura.

---

## 1. Arquitetura

```
[Quest Pro — app UE 5.5/C++]                [Servidor — Docker]                  [Navegador]
 OpenXR (XR_EXT_eye_gaze_interaction)        FastAPI (Python 3.12)                React + TS (SPA)
 ├─ gaze ~72–90 Hz (por tick)                ├─ ingestão create/frames/complete   ├─ lista de sessões
 ├─ SceneCapture 1024², 30 fps → JPEG        ├─ montagem MP4 (H.264) em bg        ├─ <video> + <canvas>
 ├─ projeção 3D→(u,v) na MESMA câmera        ├─ PostgreSQL (JSONB)                └─ heatmap client-side
 └─ upload em lotes multipart ───HTTP───►    └─ mídia em filesystem    ───────►      (parâmetros ao vivo)
```

**Decisões de projeto e justificativas:**

| Decisão | Justificativa |
|---|---|
| Eye tracking via **OpenXR nativo** (`XR_EXT_eye_gaze_interaction`, plugin Epic) e não via Movement SDK/OVRPlugin da Meta | A extensão entrega um único raio de olhar **já em espaço de mundo** (pose do olho composta com tracking-to-world), suficiente para a pergunta de pesquisa ("onde o usuário olha"); menos acoplamento a SDK proprietário; os dois caminhos são mutuamente exclusivos no engine. O plugin Meta XR permanece apenas para empacotamento/manifesto Android. |
| Gravação **in-app** (frames JPEG da própria cena) em vez de captura externa | O vídeo e a coordenada 2D saem da **mesma câmera virtual no mesmo tick** → alinhamento espacial e temporal exatos *por construção*, sem calibração nem sincronização a posteriori. |
| **MP4 montado no servidor**, não no device | Evita encoder nativo/JNI no headset; OpenCV/ffmpeg (libx264, yuv420p) no servidor com fallback e registro do codec. |
| **Heatmap renderizado no cliente** (canvas 2D) | Parâmetros (janela, σ, opacidade) ajustáveis em tempo real sem reprocessamento; o servidor não armazena vídeo derivado. |
| Amostras em **coluna JSONB** (tabela única `sessions`) | O padrão de acesso dominante é "todas as amostras de uma sessão de uma vez" (overlay no cliente); uma leitura, sem joins. Colunas achatadas (contagens, fps, status) atendem a listagem. |

## 2. Aquisição no headset

- **Gaze por tick de jogo** (~72–90 Hz), independente da taxa de vídeo. Cada amostra: raio de
  olhar em espaço de mundo → *raycast* contra a cena → ponto 3D fixado `P`.
- **Projeção 2D:** `P` é projetado na câmera de captura (perspectiva, FOV horizontal θ=82°):

  ```
  d = P − C   (no referencial da câmera: x = d·right, y = d·up, z = d·forward)
  u = 0.5 + 0.5·(x/z)/tan(θ/2)
  v = 0.5 − 0.5·(y/z)/(tan(θ/2)·H/W)      origem no canto superior-esquerdo
  ```
- **Vídeo:** SceneCapture 1024×1024 a 30 fps (configurável), JPEG q85, encode em thread de
  background (a game thread não bloqueia). O instante real `t` de cada frame é registrado —
  o intervalo entre frames **não é assumido uniforme** (ver §6).
- **Compensação de movimento:** a pose do olho é composta com a transformação
  tracking→mundo do headset; rotação/translação da cabeça ficam integralmente absorvidas.
  Cada amostra carrega **as duas representações**: ponto no mundo (análises no referencial
  da cena) e (u,v) no vídeo (análises no referencial do campo visual).
- **Robustez:** flush periódico do JSON (~5 s) protege contra encerramento abrupto;
  permissão de eye tracking tratada com callback + re-checagem; HUD de diagnóstico em
  builds Development (estado do tracker, validade, coordenadas, estado do marcador).

## 3. Contrato de dados (`gaze.json`)

```json
{
  "meta":    { "captureFovDeg": 82, "frameWidth": 1024, "frameHeight": 1024,
               "videoFps": 30, "uvOrigin": "top-left" },
  "frames":  [ { "idx": 1, "t": 0.027, "file": "frames/000001.jpg" } ],
  "samples": [ { "t": 0.027, "valid": true, "world": [x, y, z],
                 "uv": [0.512, 0.488], "confidence": 1.0 } ]
}
```
`valid=false` em piscadas/perda de rastreio (então `uv=[-1,-1]`); `confidence` no caminho
OpenXR é binária (0/1) e não é usada como critério de validade.

## 4. Protocolo de ingestão (headset → API)

Sessões chegam a centenas de MB (≈150 MB/min a 30 fps), então o upload é **em lotes, com
retomada**:

1. `POST /sessions` — corpo = `gaze.json`; header `X-Session-Id` (timestamp da sessão) é a
   **chave de idempotência** (`UNIQUE` no banco; re-execuções convergem para o mesmo registro).
   Resposta inclui `received_frames` → o device **retoma** de onde parou.
2. `POST /sessions/{id}/frames` — multipart com ~20 JPEGs por requisição, ≤2 requisições em
   voo, 3 tentativas por lote; escrita idempotente por nome de arquivo; validação de assinatura JPEG.
3. `POST /sessions/{id}/complete` — dispara a montagem do MP4 **assíncrona** (máquina de
   estados `uploading → processing → complete|failed`); a resposta é imediata para não
   estourar timeouts de cliente/proxy em sessões longas.

## 5. Visualização e algoritmo do heatmap

Porta fiel (TypeScript) do algoritmo de referência em Python. Para o instante de reprodução
com tempo de gaze `t` e janela `W` (default 1,5 s):

- amostras elegíveis: `valid ∧ uv∈[0,1]² ∧ ts∈[t−W, t]`;
- cada uma deposita uma gaussiana 2D (σ = 35 px, raio 3σ) num acumulador float, com peso de
  **decaimento linear** `w = max(0, 1 − (t−ts)/W)`;
- normalização pelo pico, colormap JET, composição alfa (α = 0,5) apenas onde a intensidade
  normalizada > 0,02.

Desempenho: acumulador em ¼ de resolução + LUT + `requestAnimationFrame` com recomputação
apenas quando muda o frame de gaze — custo por quadro desprezível para ~10³ amostras.
Modo **validação** desenha um marcador na amostra válida mais próxima do frame corrente.

## 6. Correção temporal (detalhe metodológico)

O MP4 é reproduzido a fps constante, mas os frames capturados têm **Δt não uniforme**.
Mapear `currentTime` diretamente em `sample.t` acumularia deriva. O viewer faz:

```
currentTime → índice do frame (⌊currentTime·fps⌋) → t real do frame (frames[idx].t) → janela sobre sample.t
```
mantendo o heatmap na linha do tempo do gaze, não na do container de vídeo.

## 7. Validação do pipeline

- **Marcador 3D**: esfera vermelha posicionada no ponto olhado, visível na gravação;
  o modo validação desenha o (u,v) registrado sobre o vídeo — a coincidência dos dois
  valida aquisição, projeção e sincronização de ponta a ponta. Desativável para coleta real.
- **Sessão sintética**: gerador de sessões com trajetória de olhar conhecida (Lissajous)
  exercita ingestão e heatmap de forma determinística, sem headset.
- Pipeline web verificado E2E (ingestão real e sintética, retomada, montagem H.264,
  range requests, autenticação de escrita).

## 8. Segurança e privacidade

- **Nenhuma imagem do participante é capturada** (sem câmeras/rosto/olho); registra-se a
  cena virtual e coordenadas do olhar.
- Dados hospedados **na infraestrutura da universidade**; mídia em filesystem, metadados no
  PostgreSQL (sem blobs no banco).
- Endpoints de **escrita** exigem chave (`X-Api-Key`, comparação em tempo constante);
  leitura/site na mesma origem (sem CORS em produção). HTTPS terminável por proxy reverso
  (Caddy) caso a universidade forneça domínio.

## 9. Infraestrutura solicitada

| Item | Especificação | Observação |
|---|---|---|
| VM Linux | Ubuntu 22.04+, 2 vCPU, 4 GB RAM | executa o stack via Docker Compose |
| **Disco** | **≥ 50 GB** | ≈150 MB por minuto de sessão |
| Rede | IP fixo ou hostname | endereço configurado no headset |
| **Firewall** | **1 porta TCP (8000/80) aberta à internet** | coleta fora do campus; sem isso, restrito à rede interna |
| Software | Docker + Compose | deploy em um comando (`docker compose up -d --build`) |

Runbook completo (instalação, testes em camadas, operação, backup, alternativa sem Docker)
em `DEPLOY.md` no repositório.

## 10. Estado atual

| Etapa | Status |
|---|---|
| Aquisição (gaze + vídeo + validação por marcador) | ✅ implementado |
| Upload resiliente headset→servidor (lotes, retomada, idempotência) | ✅ implementado |
| API, banco, montagem MP4 assíncrona | ✅ implementado e testado E2E |
| Viewer com heatmap/validação em tempo real | ✅ implementado e testado |
| Deploy na VM institucional | ⏳ aguardando provisionamento |
| Estudo de campo com o headset | ⏳ em andamento |

---

*Repositórios: `VR-EyeTracking-QuestPro` (aplicativo UE 5.5/C++) e `QuestPro-EyeTracking-Web`
(API + web). Detalhes de implantação em `DEPLOY.md`; documentação técnica nos READMEs.*
