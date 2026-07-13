# QuestPro Eye-Tracking — App VR (Unreal Engine 5.5)

App standalone para **Meta Quest Pro** que registra **para onde a pessoa está olhando** dentro
de um ambiente 3D: grava o vídeo da cena, amostra o olhar a ~72–90 Hz, e ao final da sessão
**envia tudo automaticamente** para o [ambiente web companheiro](https://github.com/joaozanini/QuestPro-EyeTracking-Web),
onde cada sessão pode ser assistida **com ou sem heatmap** do olhar.

> 🧪 Validado em campo (13/07/2026): marcador 3D no ponto olhado, coordenadas de mundo e
> projeção 2D corretas, upload e heatmap funcionando de ponta a ponta.

## 🎬 Demonstração

O ambiente web exibindo uma sessão gravada por este app (heatmap, validação e vídeo puro):

![Demo do ambiente web](docs/demo-ambiente-web.gif)

🎥 [Vídeo completo da demonstração (1 min, MP4)](docs/demo-ambiente-web.mp4)

## Como funciona

```
[Quest Pro — este app]                                [Servidor]                [Navegador]
 OpenXR: raio do olhar (~72–90 Hz)                     API FastAPI               React
 ├─ raycast → ponto 3D olhado                          ├─ banco de dados         ├─ lista de sessões
 ├─ bolinha vermelha no ponto (validação, opcional)    ├─ monta o MP4            ├─ vídeo + heatmap
 ├─ captura de vídeo da cena (30 fps, 1024²)           └─ mídia em disco         └─ modo validação
 └─ botão B → envia JSON + frames ───── HTTP ────►
```

- **Alinhamento por construção:** o vídeo e a coordenada 2D `(u,v)` do olhar saem da **mesma
  câmera virtual, no mesmo tick** — o ponto do heatmap cai exatamente sobre o pixel olhado,
  sem calibração posterior.
- **Movimento da cabeça 100% compensado:** o olhar é composto com a pose do headset; cada
  amostra guarda o ponto **no mundo 3D** (absoluto) e **na tela** (u,v), para análises nos
  dois referenciais.
- A **bolinha vermelha** é um validador visual (o modo *Validate* do site desenha o (u,v)
  gravado — os dois devem coincidir). Para sessões reais, desligue-a no Details
  (`Show Marker`) sem afetar a gravação.

## 🌐 Ambiente web (repositório irmão)

O **[QuestPro-EyeTracking-Web](https://github.com/joaozanini/QuestPro-EyeTracking-Web)** é a
outra metade do sistema — feito sob medida para receber as sessões deste app:

- **Recebe** as sessões enviadas pelo botão B (upload em lotes com retomada) ou por script;
- **Armazena** metadados/amostras em banco (SQLite dev / PostgreSQL) e monta o **MP4 (H.264)**;
- **Visualiza** cada sessão com **heatmap em tempo real** (janela temporal, σ e opacidade
  ajustáveis ao vivo), **modo validação** (crosshair sobre o vídeo) e tema claro/escuro;
- Deploy documentado para servidor (Docker Compose): [`DEPLOY.md`](https://github.com/joaozanini/QuestPro-EyeTracking-Web/blob/main/DEPLOY.md).

## Estrutura deste repositório

| Caminho | O que é |
|---|---|
| `Source/EyeTrackingQuestPro/GazeRecorderActor.{h,cpp}` | O ator central: gaze → raycast → marcador → projeção 2D → captura de frames → `gaze.json` → upload |
| `Config/DefaultEngine.ini` | Configurações críticas (XR, Android, empacotamento) |
| `tools/heatmap_overlay.py` | Ferramenta offline de heatmap/validação (alternativa ao site) |
| `PASSO-A-PASSO.md` | Guia detalhado de setup do zero |

## Setup (resumo)

1. **Unreal Engine 5.5** + Visual Studio 2022 (workload *Game development with C++*).
2. **Android:** NDK **25.1.8937393**, SDK 34, **JDK 17** (o `jbr` do Android Studio).
   ⚠️ O editor usa a config **global** `%LOCALAPPDATA%\Unreal Engine\Engine\Config\UserEngine.ini` — confira lá se o empacotamento reclamar de NDK/JDK.
3. **Plugin Meta XR compatível com a 5.5** (página de downloads da Meta — a versão do Fab pode ser mais nova que a engine).
4. Plugins habilitados: `OpenXR`, `OpenXREyeTracker`, `AndroidPermission`, `OculusXR` (Meta XR — usado **só** para empacotar).

### ⚠️ Configurações que NÃO podem regredir

| Config | Valor | Por quê |
|---|---|---|
| `XrApi` | **`NativeOpenXR`** | O `GetGazeData` vem do caminho OpenXR da Epic. **Nunca rode o "Meta XR Setup Tool"** — ele reverte para OVRPlugin e o gaze morre. |
| `bEyeTrackingEnabled` | **`True`** | Injeta a feature `oculus.software.eye_tracking` no manifesto; sem ela o runtime não liga o eye tracking (permissão sozinha não basta). |
| `bPackageDataInsideApk` | **`True`** | Sem OBB separado; evita o erro "o app não está disponível" no sideload. |

Depois de mudar config Android/XR: **apague `Intermediate/Android`** antes de reempacotar
(senão o manifesto antigo é reaproveitado) e **desinstale o APK antigo** antes de instalar.

## Configuração do ator (Details do `GazeRecorderActor` na cena)

| Campo | Default | Função |
|---|---|---|
| `Upload Url` | `http://<ip>:8000/api/v1/sessions` | Rota **base** da API (o código anexa `/{id}/frames` e `/{id}/complete`). Vazio = só grava local. |
| `Api Key` | — | Mesmo valor da `QUESTPRO_API_KEY` do servidor |
| `Show Marker` | ✅ | Bolinha vermelha (desligue em sessões reais) |
| `Marker Size` | 30 cm | Diâmetro da bolinha |
| `Show Debug On Screen` | ✅ | HUD de diagnóstico (builds Development) |
| `Video Fps` / `Frame Width/Height` | 30 / 1024² | Só o vídeo — o gaze é sempre por tick |
| `Upload Batch Size` | 20 | Frames por requisição no upload |

## Rodar no óculos

1. **Platforms → Android (ASTC) → Package Project** (⚠️ não use o Build do Visual Studio — ele não faz *cook* do conteúdo).
2. `adb uninstall com.sinapsense.eyetrackingquestpro` → instale o APK novo (`Install_*.bat` ou `adb install -r`).
3. No Quest Pro: **Settings → Movement Tracking → Eye Tracking LIGADO + calibrado** (o toggle do sistema é separado da permissão do app!). Rode **standalone** (via Link o gaze não funciona).
4. Abra o app, aceite a permissão, olhe ao redor e aperte **B** — a sessão sobe e o app fecha.

### HUD de diagnóstico (canto da tela)

| Linha | Diz |
|---|---|
| `Conectado / Permissao` | Estado do tracker e da permissão |
| `Gaze valido / Conf / \|olho-cam\| / rej / reanc` | Validade, confiança (0/1), sanidade da origem e contadores de amostras descartadas/re-ancoradas |
| `Ponto 3D (mundo)` | Onde o raio fixou (valores sãos = centenas de cm) |
| `Marker: vis/mesh/mat/dist` | Estado da bolinha, com avisos automáticos |

## Dados gravados (por sessão)

```
Saved/GazeSessions/<YYYY-MM-DD_HH-MM-SS>/
├── gaze.json      meta + frames[] + samples[]
└── frames/000001.jpg ...
```

```json
{ "meta":    { "captureFovDeg": 82, "frameWidth": 1024, "frameHeight": 1024,
               "videoFps": 30, "uvOrigin": "top-left" },
  "frames":  [ { "idx": 1, "t": 0.027, "file": "frames/000001.jpg" } ],
  "samples": [ { "t": 0.027, "valid": true, "world": [x,y,z],
                 "uv": [0.512, 0.488], "confidence": 1.0 } ] }
```

O JSON tem *flush* periódico (~5 s): mesmo que o app seja morto, a sessão sobrevive.
Sem rede no momento? Puxe depois com `adb pull` e envie com o
[`replay_session.py`](https://github.com/joaozanini/QuestPro-EyeTracking-Web/blob/main/scripts/replay_session.py) do repo web.

## Heatmap offline (sem o site)

```bash
py tools/heatmap_overlay.py <pasta-da-sessao> --mode heatmap   # MP4 com heatmap
py tools/heatmap_overlay.py <pasta-da-sessao> --mode validate  # crosshair vs bolinha
```

## Solução de problemas (dores reais deste projeto)

| Sintoma | Causa/Fix |
|---|---|
| "O app não está disponível" | APK sem cook (Build do VS) ou OBB ausente → **Package Project** + `bPackageDataInsideApk=True` |
| Gaze sempre inválido | Eye tracking desligado/não calibrado nas Settings; rodando via Link; ou manifesto sem a feature (reempacote limpo com `bEyeTrackingEnabled=True`) |
| Coordenadas ~100× grandes / bolinha sumida | Bug de escala do Native OpenXR no Quest — **já tratado no código** (origem re-ancorada na câmera; ver contador `reanc` no HUD) |
| Cena inteira verde-água | Dados de iluminação corrompidos no cook → **Build Lighting Only** + Reflection Captures no editor, salvar e reempacotar |
| Erro de NDK/JDK ao empacotar | Config global `UserEngine.ini` (ver Setup) |
