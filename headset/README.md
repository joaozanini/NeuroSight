# VR Eye Tracking — Meta Quest Pro (Unreal Engine 5.5)

App de **eye tracking** para Meta Quest Pro que:

1. lê para onde o usuário está olhando e posiciona uma **bolinha vermelha** no ponto 3D;
2. **grava o vídeo** do que se vê (captura feita pelo próprio app);
3. exporta um **`gaze.json`** com a posição **2D (u,v)** do olhar relativa à gravação;
4. gera, offline, um **heatmap sobreposto ao vídeo** (script Python);
5. permite **validar** que o ponto 2D bate com a bolinha 3D e depois **desligar a bolinha**,
   confiando só no JSON.

> **Por que gravar dentro do app?** O vídeo e o (u,v) saem da **mesma câmera de captura** →
> alinhamento 2D↔vídeo exato e sincronização tempo↔frame automática. A bolinha cai
> exatamente sob o ponto do heatmap por construção.

---

## O que já está neste repositório

| Arquivo | O que é |
|---|---|
| `Source/EyeTrackingQuestPro/GazeRecorderActor.h/.cpp` | **Ator principal**: gaze → bolinha + projeção 2D + captura de frames + exportação do `gaze.json`. |
| `tools/heatmap_overlay.py` | Ferramenta offline: gera o **heatmap** ou o vídeo de **validação** a partir da sessão. |
| `tools/requirements.txt` | Dependências Python (`opencv-python`, `numpy`). |
| `.gitignore` | Ignora `Binaries/`, `Intermediate/`, `Saved/`, etc. |

O **shell do projeto Unreal** (template VR, `.uproject`, configurações de build) é criado no
**editor** seguindo os passos abaixo — essa parte é GUI e precisa ser feita por você.

---

## Pré-requisitos (uma vez)

1. **Unreal Engine 5.5** (Epic Games Launcher).
2. **Visual Studio 2022** com o workload *Game development with C++*.
3. **Toolchain Android para UE 5.5**: instale o Android Studio e rode
   `Engine/Extras/Android/SetupAndroid.bat` (instala NDK/SDK/JDK nas versões esperadas).
   Confira depois em *Project Settings → Platforms → Android SDK*.
4. **Plugin Meta XR para UE 5.5**: baixe no [Fab](https://www.fab.com/listings/24fc0e7b-56d2-4421-a794-500fd51985c8)
   ou na página de downloads da Meta e instale para a engine 5.5.
5. **Python 3** no PC: `pip install -r tools/requirements.txt`.

**No Quest Pro (essencial — sem isto o gaze volta zerado):**
- Modo desenvolvedor ligado.
- **Eye tracking calibrado**: *Configurações → Movement tracking → Eye tracking* (ativar + calibrar).

---

## Passo a passo

### 1. Criar o projeto (template VR, dentro deste repositório)

No Epic Games Launcher / UE 5.5: **Games → Virtual Reality**, C++ ou Blueprint (tanto faz —
vamos adicionar C++ a seguir). **Nome: `EyeTrackingQuestPro`**, local: `C:\GitHub\VR-EyeTracking-QuestPro`.

> O template VR já entrega o VRPawn com câmera que segue o HMD e o *tracking origin* correto —
> isso é o que faz o gaze (espaço de mundo) cair no lugar certo. Os controles/teleporte do
> template podem ser ignorados.

### 2. Adicionar a classe C++ e colar o código deste repo

- No editor: **Tools → New C++ Class → AActor**, nome **`GazeRecorderActor`**. Deixe o editor
  compilar (isso cria o módulo `Source/EyeTrackingQuestPro/`).
- **Substitua** o conteúdo dos arquivos gerados pelos deste repositório:
  `Source/EyeTrackingQuestPro/GazeRecorderActor.h` e `GazeRecorderActor.cpp`.

> Se você nomeou o projeto diferente de `EyeTrackingQuestPro`, troque o macro `EYETRACKINGQUESTPRO_API`
> (no `.h`) pelo `SEUPROJETO_API` correspondente.

### 3. Dependências do módulo — `Source/EyeTrackingQuestPro/EyeTrackingQuestPro.Build.cs`

Ajuste as listas de dependências:

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core", "CoreUObject", "Engine", "InputCore",
    "EyeTracker",          // UEyeTrackerFunctionLibrary, FEyeTrackerGazeData
    "HeadMountedDisplay",  // POV do HMD via PlayerCameraManager
    "RenderCore", "RHI",   // ReadPixels do render target
    "ImageWrapper",        // encode JPEG dos frames
    "Json"                 // exportação do gaze.json
});

// AndroidPermission só faz sentido no Android (o include está sob #if PLATFORM_ANDROID).
if (Target.Platform == UnrealTargetPlatform.Android)
{
    PrivateDependencyModuleNames.Add("AndroidPermission");
}
```

### 4. Plugins — *Edit → Plugins*

Habilite: **OpenXR**, **OpenXR Eye Tracker**, **Android Permission**, **Meta XR**.
**Não** habilite o `Oculus VR` (descontinuado na UE 5.x). Reinicie o editor quando pedir.

### 5. Gerar os arquivos do VS e compilar

Feche o editor. Botão direito no `EyeTrackingQuestPro.uproject` → **Generate Visual Studio project files**.
Abra o `.sln`, compile (`Development Editor`, `Win64`) e reabra o projeto.

### 6. Material vermelho + colocar o ator no nível

- Crie um material simples: **Shading Model = Unlit**, **Emissive Color = vermelho**
  (assim a bolinha aparece forte em qualquer iluminação). Salve, ex.: `M_GazeMarker_Red`.
- Arraste um **`GazeRecorderActor`** para o nível. No painel *Details*:
  - **Marker Material** = `M_GazeMarker_Red`;
  - confira `Capture Fov Deg` (82), `Frame Width/Height` (1024), `Video Fps` (15), `Show Marker` (true).

### 7. Configurar para Quest standalone

- *Project Settings → Plugins → Meta XR* → **Launch Meta XR Project Setup Tool** → aplique as
  **recommended settings** de Android (Vulkan on, OpenGL ES off, arm64, package name, SDKs,
  forward shading + MSAA).
- **XR API = Epic Native OpenXR** (obrigatório — o backend *Meta XR with OVRPlugin* NÃO ativa o
  OpenXR Eye Tracker, e o `GetGazeData` voltaria vazio).
- Permissão de eye tracking em `Config/DefaultEngine.ini`:
  ```ini
  [/Script/AndroidRuntimeSettings.AndroidRuntimeSettings]
  +ExtraPermissions=com.oculus.permission.EYE_TRACKING
  ```

### 8. Empacotar e instalar

- *Platforms → Android → Package Project* (gera o APK), ou use o deploy rápido do Meta XR.
- Instale no headset: `adb install -r caminho/para/o.apk`.
- Abra o app no Quest Pro e **conceda a permissão** de eye tracking quando perguntado.

### 9. Rodar uma sessão e puxar os dados

1. Com a **bolinha ligada**, olhe em volta por alguns segundos.
2. **Feche o app** (o `EndPlay` grava o `gaze.json`).
3. O caminho exato da sessão é logado no boot (procure por `[GazeRecorder] Sessão em:` no
   `adb logcat`). Em geral:
   ```
   adb pull /sdcard/Android/data/com.SEU_PACOTE/files/UnrealGame/EyeTrackingQuestPro/EyeTrackingQuestPro/Saved/GazeSessions/<id> ./session
   ```
   A pasta `./session` terá `gaze.json` e `frames/`.

### 10. Validar e gerar o heatmap (no PC)

```bash
pip install -r tools/requirements.txt

# Validação: o marcador verde deve cair EM CIMA da bolinha vermelha em todos os frames.
python tools/heatmap_overlay.py ./session --mode validate

# Heatmap sobreposto ao vídeo.
python tools/heatmap_overlay.py ./session --mode heatmap --out heatmap.mp4

# (opcional) heatmap agregado da sessão inteira como PNG.
python tools/heatmap_overlay.py ./session --static-heatmap aggregate.png
```

### 11. Confiar no JSON e desligar a bolinha

Validado o casamento 2D↔3D, é só desligar a bolinha (não atrapalha mais a experiência) — o
log e a gravação continuam normalmente:
- no *Details* do ator: **Show Marker = false**, ou
- em runtime/Blueprint: `SetMarkerVisible(false)`.

---

## Formato do `gaze.json`

```json
{
  "meta":   { "captureFovDeg": 82.0, "frameWidth": 1024, "frameHeight": 1024,
              "videoFps": 15.0, "uvOrigin": "top-left" },
  "frames": [ { "idx": 1, "t": 0.000, "file": "frames/000001.jpg" } ],
  "samples":[ { "t": 0.000, "valid": true, "world": [x,y,z],
                "uv": [0.512, 0.488], "confidence": 0.94 } ]
}
```
- `uv` é normalizado em `[0,1]`, origem no canto superior-esquerdo → pixel = `(u·W, v·H)`.
- `valid=false` em piscadas; nesses frames a bolinha some e o `uv` vem `[-1,-1]`.

---

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| Gaze sempre inválido / bolinha não aparece | Permissão de eye tracking não concedida; eye tracking não calibrado no device; **XR API** não está em *Epic Native OpenXR*. Cheque `IsEyeTrackerConnected()` e o `adb logcat`. |
| Bolinha aparece cinza, não vermelha | O fallback dinâmico não achou o parâmetro de cor — atribua um material **Unlit vermelho** em `Marker Material`. |
| `frames` vazio no JSON | `Video Fps` = 0, ou a sessão foi fechada cedo demais. |
| App engasga ao gravar | Custo do SceneCapture + readback. Reduza `Video Fps` (ex.: 10), `Frame Width/Height` (ex.: 768). É um modo de pesquisa, não de produto final. |
| O nó/função de eye tracking some na UE 5.6.0 | Bug conhecido — corrigido na **5.6.1**. (Aqui usamos 5.5.) |

---

## Notas técnicas

- `UEyeTrackerFunctionLibrary::GetGazeData` devolve `GazeOrigin`/`GazeDirection` em **espaço de
  mundo**; por isso usamos o VRPawn do template VR (tracking origin correto).
- Eye tracking existe **só no Quest Pro** (Quest 2/3/3S não têm o hardware).
- **"MP4 direto do headset"**: o padrão grava `frames + json` e o Python monta o vídeo. Para um
  MP4 já pronto saindo do device, o upgrade é um encoder nativo (MediaCodec via JNI/UPL) ou um
  plugin pago (ex.: Runtime Video Recorder).
- **Fallback de gaze**: se o caminho OpenXR teimar em voltar zerado no firmware do device, a
  alternativa é o Meta Movement SDK (backend OVRPlugin) — mais trabalhoso, porém "oficial" da Meta.
