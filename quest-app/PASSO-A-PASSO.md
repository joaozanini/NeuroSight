# Passo a passo completo — do zero ao heatmap

Guia detalhado para montar o app de eye tracking no Meta Quest Pro (UE 5.5, C++, standalone)
e gerar o heatmap. Siga as fases na ordem. Onde aparecer ⚠️, é um ponto que costuma travar.

Legenda: `Menu → Submenu` = caminho de clique no editor/app.

---

## FASE A — Instalar as ferramentas (uma vez)

### A1. Unreal Engine 5.5
1. Abra o **Epic Games Launcher** → aba **Unreal Engine** → **Library**.
2. Clique no **`+`** → escolha a versão **5.5.x** → **Install**.
3. (Opcional) Em **Options**, confirme que **Android** está marcado em *Target Platforms*.

### A2. Visual Studio 2022
1. Baixe o **Visual Studio 2022 Community** (grátis).
2. No instalador, marque o workload **"Game development with C++"**.
3. Em **Individual components**, confirme: **MSVC v143**, **Windows 10/11 SDK**, **.NET Framework 4.8 SDK**.
4. Instale.

### A3. Toolchain Android (para empacotar pro Quest) ⚠️
> Esta é a parte que mais dá problema. As versões são casadas com a UE 5.5 — use exatamente estas.

**Versões para UE 5.5 (oficiais da Epic):**

| Item | Versão |
|---|---|
| Android Studio | **Koala 2024.1.2** (release de 29/08/2024) — *não* é o Flamingo das versões antigas |
| NDK | **r25b** = `25.1.8937393` |
| JDK | OpenJDK **17.0.6** (já vem embutido na engine — não precisa instalar à parte) |
| Android SDK (compile/target) | **34** (mínimo instalável: 26) |
| Build-tools | **34.0.0** |

Para Quest, a Meta exige **Min API 32 / Target API 34** — o Meta XR Project Setup Tool (Fase D2) ajusta isso depois.

**Opção 1 — Turnkey (mais fácil, recomendado):** deixa a Unreal baixar/instalar tudo na versão certa, sem você caçar versão.
- Por linha de comando (ajuste o caminho se instalou a engine em outro lugar):
  ```
  "C:\Program Files\Epic Games\UE_5.5\Engine\Build\BatchFiles\RunUAT.bat" Turnkey -command=InstallSdk -platform=Android
  ```
- Ou, com um projeto aberto, o editor oferece o setup automático ao tentar empacotar sem SDK.

**Opção 2 — Manual (Android Studio + SetupAndroid.bat):**
1. Baixe e instale o **Android Studio Koala 2024.1.2** (versão exata em developer.android.com/studio/archive, se precisar).
2. Abra o Android Studio uma vez e conclua o assistente inicial (instala um SDK base).
3. **More Actions → SDK Manager → aba "SDK Tools"** → marque **"Android SDK Command-Line Tools (latest)"** → **Apply**. (Instala o `cmdline-tools`, que o próximo passo precisa.)
4. **Feche** o Android Studio.
5. Rode `C:\Program Files\Epic Games\UE_5.5\Engine\Extras\Android\SetupAndroid.bat` (clique direito → *Executar como administrador*). Ele usa o `sdkmanager` para instalar **SDK 34 + build-tools 34.0.0 + NDK 25.1.8937393 + CMake** e seta `ANDROID_HOME`, `NDKROOT` e `JAVA_HOME` (apontando para o JDK embutido da engine). Quando perguntar das licenças, digite **`y`**.
6. **Reinicie o PC** (para aplicar as variáveis de ambiente).
7. Validação: no editor, *Project Settings → Platforms → Android SDK* — campos **SDK / NDK / JDK** preenchidos e sem aviso vermelho.

### A4. Plugin Meta XR (para a UE 5.5) ⚠️
⚠️ **NÃO pegue do Fab para a 5.5.** O Fab só oferece a versão **mais nova** do Meta XR (que mira a UE mais nova — hoje a 5.7). Instalar essa numa engine 5.5 causa *"The 'OculusXR' plugin was designed for build 5.7.0"* / *"modules built with a different engine version"*. Para a 5.5, baixe a versão específica:
1. Acesse **https://developers.meta.com/horizon/downloads/package/unreal-engine-5-integration/**.
2. No **seletor de versão** da página, escolha uma release que liste suporte à **UE 5.5** (família ~v76/v77; a v78 já é 5.6.1, a v85 é 5.7). O rótulo da página é a fonte da verdade.
3. Baixe o `.zip` e extraia a pasta `MetaXR` para `C:\Program Files\Epic Games\UE_5.5\Engine\Plugins\Marketplace\` (o Windows pede confirmação de admin).
4. Confira: abra `...\Marketplace\MetaXR\OculusXR.uplugin` e veja se o campo `"EngineVersion"` é **5.5.x** (não 5.7).

### A5. Python (para o heatmap)
1. Instale **Python 3** (python.org), marcando **"Add Python to PATH"**.
2. ⚠️ No Windows, digitar `python` pode abrir o **atalho da Microsoft Store** (um Python falso que não instala nada). Se isso acontecer, use o lançador **`py`** no lugar de `python` em TODOS os comandos.
3. Na pasta do repositório, instale as dependências:
   ```
   py -3 -m pip install -r tools/requirements.txt
   ```
   Verifique com: `py -3 -c "import cv2, numpy; print('OK')"`

---

## FASE B — Criar o projeto e deixar o repositório "flat"

### B1. Criar pelo template VR
1. UE 5.5 → **New Project** → categoria **Games** → **Virtual Reality**.
2. ⚠️ No template **Virtual Reality**, as opções de *Project Defaults* (Blueprint/C++, Target Platform, Quality, Raytracing, Starter Content) vêm **travadas/pré-configuradas** — isso é normal, os valores já são os certos pra VR (Scalable, raytracing off). NÃO precisa mexer. (Só o template **Blank** deixa editar tudo, porque não tem nada predefinido — mas não use o Blank: perderíamos o VRPawn/câmera/XR prontos.)
   - O template VR é **só Blueprint** (não há opção C++ aqui) — tudo bem, o C++ entra no passo **B3**.
   - O *Target Platform* travado não importa — miramos Android depois, via Meta XR Setup Tool (Fase D2).
3. Edite só o que está liberado:
   - **Project Name: `EyeTrackingQuestPro`**
   - **Location: `C:\GitHub\VR-EyeTracking-QuestPro`**
4. **Create**.

⚠️ O launcher cria uma subpasta: `C:\GitHub\VR-EyeTracking-QuestPro\EyeTrackingQuestPro\`.

### B2. Consolidar no repositório (layout flat)
1. Feche o editor.
2. No Explorer, entre em `C:\GitHub\VR-EyeTracking-QuestPro\EyeTrackingQuestPro\`, **selecione tudo**
   (`EyeTrackingQuestPro.uproject`, `Config`, `Content`, e `Source` se existir), **recorte**.
3. **Cole** em `C:\GitHub\VR-EyeTracking-QuestPro\` (a raiz do repo). Se o Windows perguntar para
   **mesclar** a pasta `Source`, clique **Sim** (ela junta com o `Source\EyeTrackingQuestPro\` que já tem
   o `GazeRecorderActor`).
4. Apague a subpasta `EyeTrackingQuestPro\` (agora vazia).
   - Resultado: `C:\GitHub\VR-EyeTracking-QuestPro\EyeTrackingQuestPro.uproject` na raiz, com
     `Source\EyeTrackingQuestPro\GazeRecorderActor.h/.cpp` no lugar.

### B3. Garantir que é um projeto C++ ⚠️
- **Se você criou pelo template C++**: o módulo já existe → pule para a Fase C.
- **Se criou pelo template Blueprint** (não há `Source\EyeTrackingQuestPro\*.Build.cs`):
  1. Abra o `EyeTrackingQuestPro.uproject` (duplo clique).
  2. No editor: **Tools → New C++ Class → Actor** → nome **`Bootstrap`** → **Create Class**.
     (É uma classe "descartável" só para a Unreal gerar o módulo C++ — `Build.cs`, `Target.cs`, etc.)
  3. Deixe compilar e abrir o Visual Studio.
  4. Feche o editor e o VS. No Explorer, **apague** `Source\EyeTrackingQuestPro\Bootstrap.h` e `Bootstrap.cpp`.
     (Mantemos só o `GazeRecorderActor`, que já está lá.)

---

## FASE C — Código C++

### C1. Conferir o GazeRecorderActor
Os arquivos `Source\EyeTrackingQuestPro\GazeRecorderActor.h` e `.cpp` já estão no repositório com a
lógica pronta (gaze → bolinha + projeção 2D + captura + `gaze.json`). Nada a fazer aqui, a não ser
conferir que existem.

⚠️ Se o seu projeto **não** se chama `EyeTrackingQuestPro`, abra o `.h` e troque o macro
`EYETRACKINGQUESTPRO_API` por `SEUPROJETO_API`.

### C2. Editar o `Source\EyeTrackingQuestPro\EyeTrackingQuestPro.Build.cs`
Abra no VS (ou bloco de notas) e deixe as dependências assim:
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

if (Target.Platform == UnrealTargetPlatform.Android)
{
    PrivateDependencyModuleNames.Add("AndroidPermission");
}
```

### C3. Gerar projeto do VS e compilar
1. No Explorer, clique direito no `EyeTrackingQuestPro.uproject` → **Generate Visual Studio project files**.
2. Abra o `EyeTrackingQuestPro.sln` no VS.
3. Configuração no topo: **Development Editor** + **Win64**.
4. ⚠️ **NÃO use "Build Solution"!** Isso tenta recompilar TODO o ferramental C# da Unreal (UBT, AutomationTool…), que exige **.NET 8 SDK** e falha com `NETSDK1045` se você tiver só um .NET mais antigo. Em vez disso, faça UMA destas:
   - **Mais simples (recomendado):** feche o VS e dê duplo clique no `EyeTrackingQuestPro.uproject` → se pedir *"rebuild missing modules?"*, **Yes** (usa o .NET embutido da Unreal, sem conflito de SDK); **ou**
   - no VS, no Solution Explorer, clique direito **só no projeto `EyeTrackingQuestPro`** (pasta *Games*) → **Build** (nunca "Build Solution").
5. Abra o editor (`.uproject` ou `F5` no VS) e confirme que não há erro de módulos.

⚠️ Se der erro de include/símbolo, me mande a mensagem do compilador — alguns nomes de header
mudam entre patches da engine e eu ajusto.

---

## FASE D — Plugins e configurações do projeto

### D1. Habilitar plugins
1. No editor: **Edit → Plugins**.
2. Habilite (caixa marcada): **OpenXR**, **OpenXR Eye Tracker**, **Android Permission**, **Meta XR**.
3. **NÃO** habilite o **Oculus VR** (descontinuado).
4. **Restart Now** quando pedir.
5. ⚠️ Em projeto **C++**, ao habilitar um plugin com módulos a compilar (como o Meta XR), o editor mostra *"The following modules are missing... Please build through your IDE"* e não carrega o plugin só com restart — isso é normal. O plugin fica habilitado no `.uproject`, mas você precisa **compilar pelo Visual Studio** (Development Editor / Win64) e reabrir o editor. Se der **"access denied"** escrevendo em `C:\Program Files\...`, rode o VS **como Administrador** e compile de novo.

### D2. Rodar o Meta XR Project Setup Tool
1. **Edit → Project Settings** → busque por **"Meta XR"** (seção *Plugins → Meta XR*).
2. Clique em **Launch Meta XR Project Setup Tool**.
3. Na janela, selecione a plataforma **Android** e clique em **Apply All** (ele corrige Vulkan,
   arm64, manifest, SDKs, forward shading, MSAA, etc.). Resolva também os itens marcados como
   *Required*.

### D3. Definir o backend de XR ⚠️ (crítico)
1. Ainda em *Project Settings → Plugins → Meta XR → General*.
2. Em **XR API**, escolha **Epic Native OpenXR (Recommended)**.
   > Isso é obrigatório: no backend *Meta XR with OVRPlugin* o `GetGazeData` (OpenXR Eye Tracker)
   > não funciona. Os checkboxes de tracking da Meta só aparecem no OVRPlugin — nós não precisamos
   > deles, pois usamos o OpenXR Eye Tracker.

### D4. Adicionar a permissão de eye tracking
Pelo editor (mais fácil):
1. *Project Settings → Platforms → Android → Advanced APKPackaging* → campo **Extra Permissions**.
2. **+** e adicione exatamente: `com.oculus.permission.EYE_TRACKING`.

Ou editando `Config\DefaultEngine.ini`:
```ini
[/Script/AndroidRuntimeSettings.AndroidRuntimeSettings]
+ExtraPermissions=com.oculus.permission.EYE_TRACKING
```

### D5. Conferir as configurações de Android
Em *Project Settings → Platforms → Android*:
- **Package name** definido (ex.: `com.suaempresa.eyetrackingquestpro`) — se houver botão **Configure Now**, clique.
- **Support arm64** marcado; **Support armv7** desmarcado.
- *Build* → **Support Vulkan** marcado; **Support OpenGL ES3.2** desmarcado.
- *Project Settings → Rendering → Mobile* → **Mobile HDR** **desmarcado** (obrigatório para VR).

---

## FASE E — Material da bolinha e colocar o ator na cena

### E1. Material vermelho (Unlit)
1. No **Content Browser**, clique direito → **Material** → nome `M_GazeMarker_Red`.
2. Abra-o. No nó principal, painel *Details* → **Shading Model = Unlit**.
3. Crie um nó **Constant3Vector** (tecla **3** + clique), pinte de **vermelho**, ligue na entrada
   **Emissive Color**.
4. **Save**.
   > Unlit faz a bolinha aparecer forte em qualquer iluminação.

### E2. Colocar o GazeRecorderActor no nível
1. Abra o mapa principal do template VR (algo como `Content/VRTemplate/Maps/VRTemplateMap`).
2. Coloque o **GazeRecorderActor** na cena. ⚠️ Atores C++ NÃO aparecem na lista rápida do *Place Actors* — use um destes:
   - **Content Browser → pasta `C++ Classes` → `EyeTrackingQuestPro` → `GazeRecorderActor`** → arraste pro viewport (mais confiável). Se não vir a pasta `C++ Classes`, clique em **Settings** (engrenagem do Content Browser) e marque **"Show C++ Classes"**.
   - ou painel **Place Actors** → **caixa de busca** no topo → digite `Gaze` → arraste pra cena.
3. Selecione-o e no painel **Details**:
   - **Marker Material** = `M_GazeMarker_Red`.
   - Confira: **Show Marker** = `true`, **Capture Fov Deg** = 82, **Frame Width/Height** = 1024,
     **Video Fps** = 15.
4. **Save** (`Ctrl+S`).

---

## FASE F — Preparar o Quest Pro

### F1. Modo desenvolvedor
1. No app **Meta Horizon** (celular) → **Devices** → seu Quest Pro → **Headset Settings →
   Developer Mode** → **ON**. (Precisa ter uma "organização"/conta de desenvolvedor criada.)
2. Conecte o Quest no PC por USB-C. No headset, **aceite** o prompt *Allow USB debugging*.
3. No PC, valide: `adb devices` deve listar o headset.

### F2. Calibrar o eye tracking ⚠️ (sem isto o gaze vem zerado)
1. No headset: **Settings → Movement tracking** → ative **Eye tracking**.
2. Faça a **calibração** de eye tracking quando solicitado.

---

## FASE G — Empacotar, instalar e rodar

### G1. Empacotar o APK
1. Na barra superior do editor: **Platforms → Android → Android (ASTC)** → **Package Project**.
2. Escolha uma pasta de saída. Ao final, haverá um `.apk` (e possivelmente um `.obb`).
   > Alternativa: o Meta XR tem um **Quick Deploy** que builda e instala direto no device.

### G2. Instalar no headset
```
adb install -r "caminho\para\EyeTrackingQuestPro.apk"
```
(Se houver `.obb`, o deploy do editor/Meta já o instala; via adb manual, copie o `.obb` para
`/sdcard/Android/obb/<package>/`.)

### G3. Rodar a sessão
1. No Quest, abra o app (em **Apps → Unknown Sources**).
2. **Aceite o prompt de permissão** de eye tracking.
3. Com a bolinha ligada, **olhe em volta** por alguns segundos.
4. **Feche o app** (isso dispara a gravação do `gaze.json`).

---

## FASE H — Puxar os dados e gerar o heatmap (no PC)

### H1. Descobrir o caminho da sessão
O app loga o caminho no boot. Veja:
```
adb logcat -s LogTemp:V | findstr GazeRecorder
```
Procure a linha `[GazeRecorder] Sessão em: ...`.

### H2. Puxar a pasta da sessão
```
adb pull "/sdcard/Android/data/com.SEU_PACOTE/files/UnrealGame/EyeTrackingQuestPro/EyeTrackingQuestPro/Saved/GazeSessions/<id>" ./session
```
(Use o caminho exato que apareceu no logcat.) A pasta `./session` terá `gaze.json` e `frames/`.

### H3. Validar (a bolinha é a verdade de campo)
```
py tools/heatmap_overlay.py ./session --mode validate
```
Abra o `session/validate.mp4`: o **marcador verde** deve cair **em cima da bolinha vermelha** em
todos os frames. Se cair, o JSON 2D está correto.

### H4. Gerar o heatmap
```
py tools/heatmap_overlay.py ./session --mode heatmap --out heatmap.mp4
py tools/heatmap_overlay.py ./session --static-heatmap aggregate.png   # opcional
```

---

## FASE I — Confiar no JSON e desligar a bolinha
Validado o casamento 2D↔3D, desligue a bolinha (não atrapalha mais a experiência) — o log e a
gravação continuam:
- no *Details* do ator: **Show Marker = false**; ou
- em Blueprint/código: `SetMarkerVisible(false)`.

---

## Tabela de problemas comuns

| Sintoma | Causa provável / correção |
|---|---|
| Gaze sempre inválido, bolinha não aparece | Permissão não concedida; eye tracking não calibrado; **XR API ≠ Epic Native OpenXR**. Cheque `IsEyeTrackerConnected()` e o `adb logcat`. |
| Erro de compilação C++ | Header mudou de nome no seu patch da engine — me mande a mensagem do compilador. |
| Bolinha cinza (não vermelha) | Atribua o material **Unlit vermelho** em *Marker Material*. |
| `frames` vazio no JSON | `Video Fps` = 0, ou app fechado cedo demais. |
| App engasga ao gravar | Reduza `Video Fps` (10) e `Frame Width/Height` (768). É modo de pesquisa, não de produto. |
| `adb` não acha o device | Cabo de dados (não só de carga); aceitar *USB debugging* no headset; `adb kill-server && adb start-server`. |
| `SetupAndroid.bat` falha com **Exit code 5** | NDK 25.1.8937393 não instalou. **Olhe a saída no console acima do "exit 5"** — duas causas comuns: **(a) "Java version 17 or higher is required"** → você tem um `JAVA_HOME` antigo; o script só usa o Java do Studio se `JAVA_HOME` não existir. Corrija: `setx JAVA_HOME "C:\Program Files\Android\Android Studio\jbr"` + `$env:JAVA_HOME="...jbr"` e re-rode. **(b) Licença não aceita** (modo `-noninteractive` do Turnkey) → rode o `.bat` na mão e digite `y`. Confirme que `...\Sdk\ndk\25.1.8937393` passou a existir. |
| `SetupAndroid.bat` falha com Exit code 3 | Faltou instalar o "Android SDK Command-Line Tools (latest)" no SDK Manager do Android Studio. |
| Classe C++ (ex.: `GazeRecorderActor`) **compila mas NÃO aparece** no editor (nem em Place Actors, nem em C++ Classes) | Quase sempre falta a seção **`"Modules"`** no `.uproject` (comum quando o projeto foi convertido pra C++ "na mão"). Sem ela o editor não carrega o módulo do jogo. Adicione, no `.uproject`, antes de `"Plugins"`: `"Modules":[{"Name":"<NomeDoModulo>","Type":"Runtime","LoadingPhase":"Default"}],` e reabra o editor. Não precisa recompilar se o DLL já existe e o BuildId bate. |
| "Build Solution" falha com `NETSDK1045` (.NET 8) | Não use "Build Solution"; veja a Fase C3. |
