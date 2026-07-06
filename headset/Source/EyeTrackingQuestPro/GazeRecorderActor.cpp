// Copyright (c) 2026. Eye tracking + gravação + heatmap para Meta Quest Pro.

#include "GazeRecorderActor.h"

#include "EyeTrackerFunctionLibrary.h"
#include "EyeTrackerTypes.h"

#include "Components/StaticMeshComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "TextureResource.h"
#include "UnrealClient.h"

#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Camera/PlayerCameraManager.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/DateTime.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformTime.h"
#include "Modules/ModuleManager.h"
#include "Async/Async.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/Guid.h"

#include "IImageWrapper.h"
#include "IImageWrapperModule.h"

#if PLATFORM_ANDROID
#include "AndroidPermissionFunctionLibrary.h"
#include "AndroidPermissionCallbackProxy.h"
#endif

AGazeRecorderActor::AGazeRecorderActor()
{
	PrimaryActorTick.bCanEverTick = true;

	// Endpoint padrao da API = este PC na rede local (rota base; o codigo anexa /{id}/frames e
	// /{id}/complete). Pode ser sobrescrito no Details do ator. TEM que ser um endereco que o
	// oculos alcance (NAO localhost) — trocar aqui se o servidor mudar de IP/maquina.
	UploadUrl = TEXT("http://192.168.0.6:8000/api/v1/sessions");

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);

	GazeMarker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("GazeMarker"));
	GazeMarker->SetupAttachment(SceneRoot);
	GazeMarker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GazeMarker->SetCastShadow(false);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (SphereMesh.Succeeded())
	{
		GazeMarker->SetStaticMesh(SphereMesh.Object);
	}

	Capture = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("Capture"));
	Capture->SetupAttachment(SceneRoot);
	Capture->bCaptureEveryFrame = false;   // capturamos manualmente no ritmo de VideoFps
	Capture->bCaptureOnMovement = false;
	Capture->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
}

void AGazeRecorderActor::BeginPlay()
{
	Super::BeginPlay();

	StartTimeSeconds = FPlatformTime::Seconds();
	NextFrameTime = 0.f;
	NextJsonFlushTime = 5.f; // 1o flush periodico do gaze.json em ~5s (ver Tick)
	FrameIndex = 0;
	Samples.Reset();
	FrameList.Reset();

	// Permissão de eye tracking (obrigatória no build standalone do Quest).
	// Usamos o callback para só ativar o tracker depois que o usuário concede a permissão,
	// evitando que os primeiros frames de Tick() tentem ler gaze sem permissão concedida.
#if PLATFORM_ANDROID
	{
		static const FString EyePerm = TEXT("com.oculus.permission.EYE_TRACKING");
		if (UAndroidPermissionFunctionLibrary::CheckPermission(EyePerm))
		{
			// Já concedida em launch anterior — pode ativar direto.
			bPermissionReady = true;
			UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Permissao EYE_TRACKING ja concedida."));
		}
		else
		{
			TArray<FString> Perms;
			Perms.Add(EyePerm);
			UAndroidPermissionCallbackProxy* Proxy = UAndroidPermissionFunctionLibrary::AcquirePermissions(Perms);
			if (Proxy)
			{
				Proxy->OnPermissionsGrantedDelegate.AddWeakLambda(this,
					[this](const TArray<FString>& /*Permissions*/, const TArray<bool>& GrantResults)
					{
						bPermissionReady = GrantResults.ContainsByPredicate([](bool b){ return b; });
						UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Permissao EYE_TRACKING: %s"),
							bPermissionReady ? TEXT("concedida") : TEXT("negada — reinicie o app"));
					});
			}
		}
	}
#endif

	// Diagnostico: o eye tracker ja esta conectado? (No caminho OpenXR NAO existe StartEyeTracking;
	// o GetGazeData funciona com o tracker conectado + permissao concedida + calibracao no device.)
	UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] EyeTracker conectado: %s"),
		UEyeTrackerFunctionLibrary::IsEyeTrackerConnected() ? TEXT("sim") : TEXT("nao (pode conectar depois)"));

	// Pasta da sessão: Saved/GazeSessions/<timestamp>/frames
	const FString SessionId = FDateTime::Now().ToString(TEXT("%Y-%m-%d_%H-%M-%S"));
	SessionDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("GazeSessions"), SessionId);
	const FString FramesAbs = FPaths::Combine(SessionDir, FramesSubdir);
	FPlatformFileManager::Get().GetPlatformFile().CreateDirectoryTree(*FramesAbs);
	UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Sessão em: %s"), *SessionDir);

	// Render target da câmera de captura.
	RenderTarget = NewObject<UTextureRenderTarget2D>(this);
	RenderTarget->ClearColor = FLinearColor::Black;
	RenderTarget->InitCustomFormat(FrameWidth, FrameHeight, PF_B8G8R8A8, /*bForceLinearGamma=*/false);
	RenderTarget->UpdateResourceImmediate(true);
	Capture->TextureTarget = RenderTarget;
	Capture->FOVAngle = CaptureFovDeg;

	// Bolinha: escala (sphere do engine tem ~100 cm de diâmetro) + material.
	GazeMarker->SetWorldScale3D(FVector(MarkerSize / 100.f));
	if (MarkerMaterial)
	{
		GazeMarker->SetMaterial(0, MarkerMaterial);
	}
	else if (UMaterialInstanceDynamic* Dyn = GazeMarker->CreateDynamicMaterialInstance(0))
	{
		// Fallback: pode não ser vermelho se o material base não expuser "Color".
		// Prefira atribuir um material Unlit vermelho em MarkerMaterial.
		Dyn->SetVectorParameterValue(TEXT("Color"), FLinearColor::Red);
	}
	GazeMarker->SetVisibility(false);

	// Garante o módulo de imagem carregado na game thread (usado depois em background).
	FModuleManager::Get().LoadModule(FName("ImageWrapper"));

	bSessionActive = true;
}

void AGazeRecorderActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (bSessionActive)
	{
		WriteSessionJson();
		bSessionActive = false;
	}
	Super::EndPlay(EndPlayReason);
}

float AGazeRecorderActor::TimeSinceStart() const
{
	return static_cast<float>(FPlatformTime::Seconds() - StartTimeSeconds);
}

void AGazeRecorderActor::SetMarkerVisible(bool bVisible)
{
	bShowMarker = bVisible;
}

void AGazeRecorderActor::StopSessionAndQuit()
{
	if (bSessionActive)
	{
		WriteSessionJson();      // grava o gaze.json final (frames ja estao no disco)
		bSessionActive = false;  // para a captura/log
		UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Sessao encerrada pelo usuario (B): JSON salvo."));
	}

	// Se houver endpoint configurado, envia a sessao (JSON + frames) e SO fecha quando o upload
	// terminar (no callback final) ou no timeout de seguranca. Senao, fecha direto.
	if (!UploadUrl.IsEmpty())
	{
		BeginUploadSequence();
	}
	else
	{
		UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] UploadUrl vazio -> sem upload. Fechando."));
		QuitNow();
	}
}

void AGazeRecorderActor::RearmQuitFallback(float Seconds)
{
	if (bQuitting)
	{
		return;
	}
	// Enquanto houver progresso, re-arma o timer -> um upload em andamento nunca e morto no meio;
	// se travar (sem progresso por 'Seconds'), QuitNow fecha o app mesmo assim.
	GetWorldTimerManager().SetTimer(QuitFallbackTimer, this, &AGazeRecorderActor::QuitNow, Seconds, false);
}

void AGazeRecorderActor::BeginUploadSequence()
{
	const FString JsonPath = FPaths::Combine(SessionDir, TEXT("gaze.json"));
	FString JsonContent;
	if (!FFileHelper::LoadFileToString(JsonContent, *JsonPath))
	{
		UE_LOG(LogTemp, Warning, TEXT("[GazeRecorder] Nao consegui ler %s para upload. Fechando."), *JsonPath);
		QuitNow();
		return;
	}

	// Lista os frames ja gravados (escritos em background durante a sessao). Ordem lexicografica
	// dos nomes "000001.jpg" = ordem de captura.
	PendingFrameFiles.Reset();
	const FString FramesAbs = FPaths::Combine(SessionDir, FramesSubdir);
	IFileManager::Get().FindFiles(PendingFrameFiles, *FPaths::Combine(FramesAbs, TEXT("*.jpg")), true, false);
	PendingFrameFiles.Sort();
	NextFrameCursor = 0;
	InFlightBatches = 0;
	ServerSessionId.Reset();

	RearmQuitFallback(UploadTimeoutSeconds + 5.f);

	// Passo 1: cria a sessao no servidor enviando o gaze.json. A resposta traz o id e quantos
	// frames o servidor ja tem (para retomar um upload interrompido).
	const FHttpRequestRef Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(UploadUrl);
	Req->SetVerb(TEXT("POST"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Req->SetHeader(TEXT("X-Session-Id"), FPaths::GetCleanFilename(SessionDir));
	if (!ApiKey.IsEmpty())
	{
		Req->SetHeader(TEXT("X-Api-Key"), ApiKey);
	}
	Req->SetContentAsString(JsonContent);
	Req->SetTimeout(UploadTimeoutSeconds);
	Req->OnProcessRequestComplete().BindWeakLambda(this,
		[this](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
		{
			OnCreateComplete(Response, bSucceeded);
		});
	Req->ProcessRequest();
	UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Criando sessao na API %s (%d frames a enviar)..."),
		*UploadUrl, PendingFrameFiles.Num());
}

void AGazeRecorderActor::OnCreateComplete(FHttpResponsePtr Response, bool bSucceeded)
{
	const int32 Code = (bSucceeded && Response.IsValid()) ? Response->GetResponseCode() : 0;
	if (Code < 200 || Code >= 300)
	{
		UE_LOG(LogTemp, Error, TEXT("[GazeRecorder] Falha ao criar sessao na API (HTTP %d). Fechando."), Code);
		QuitNow();
		return;
	}

	TSharedPtr<FJsonObject> Obj;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
	if (FJsonSerializer::Deserialize(Reader, Obj) && Obj.IsValid())
	{
		Obj->TryGetStringField(TEXT("id"), ServerSessionId);
		double Received = 0.0;
		if (Obj->TryGetNumberField(TEXT("received_frames"), Received))
		{
			NextFrameCursor = FMath::Clamp(static_cast<int32>(Received), 0, PendingFrameFiles.Num());  // retomada
		}
	}

	if (ServerSessionId.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("[GazeRecorder] Resposta da API sem 'id'. Fechando."));
		QuitNow();
		return;
	}

	RearmQuitFallback(UploadTimeoutSeconds + 5.f);
	UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Sessao %s criada (retomando de %d/%d). Enviando frames..."),
		*ServerSessionId, NextFrameCursor, PendingFrameFiles.Num());
	PumpFrameBatches();
}

void AGazeRecorderActor::PumpFrameBatches()
{
	const int32 MaxInFlight = 2;  // throttle: no maximo 2 lotes simultaneos no stack HTTP do Quest
	while (InFlightBatches < MaxInFlight && NextFrameCursor < PendingFrameFiles.Num())
	{
		const int32 Start = NextFrameCursor;
		const int32 Count = FMath::Min(FMath::Max(1, UploadBatchSize), PendingFrameFiles.Num() - Start);
		NextFrameCursor += Count;
		++InFlightBatches;
		SendFrameBatch(Start, Count, 0);
	}

	if (InFlightBatches == 0 && NextFrameCursor >= PendingFrameFiles.Num())
	{
		SendComplete();  // todos os frames enviados -> finaliza
	}
}

void AGazeRecorderActor::SendFrameBatch(int32 Start, int32 Count, int32 Retry)
{
	const FString FramesAbs = FPaths::Combine(SessionDir, FramesSubdir);
	const FString Boundary = TEXT("----QuestProBoundary") + FGuid::NewGuid().ToString(EGuidFormats::Digits);

	// Monta o corpo multipart/form-data a mao (UE nao tem helper): cada frame e uma parte
	// name="frames"; filename="000001.jpg" (o servidor usa o filename pra nomear o arquivo).
	TArray<uint8> Body;
	auto AppendAscii = [&Body](const FString& S)
	{
		const FTCHARToUTF8 Conv(*S);
		Body.Append(reinterpret_cast<const uint8*>(Conv.Get()), Conv.Length());
	};

	int32 Appended = 0;
	for (int32 i = Start; i < Start + Count && i < PendingFrameFiles.Num(); ++i)
	{
		const FString FileName = PendingFrameFiles[i];
		TArray<uint8> FileData;
		if (!FFileHelper::LoadFileToArray(FileData, *FPaths::Combine(FramesAbs, FileName)))
		{
			UE_LOG(LogTemp, Warning, TEXT("[GazeRecorder] Frame ilegivel, pulando: %s"), *FileName);
			continue;
		}
		AppendAscii(FString::Printf(TEXT("--%s\r\n"), *Boundary));
		AppendAscii(FString::Printf(TEXT("Content-Disposition: form-data; name=\"frames\"; filename=\"%s\"\r\n"), *FileName));
		AppendAscii(TEXT("Content-Type: image/jpeg\r\n\r\n"));
		Body.Append(FileData);
		AppendAscii(TEXT("\r\n"));
		++Appended;
	}
	AppendAscii(FString::Printf(TEXT("--%s--\r\n"), *Boundary));

	if (Appended == 0)
	{
		// nada legivel neste lote -> libera o slot e segue
		--InFlightBatches;
		PumpFrameBatches();
		return;
	}

	const FString Url = FString::Printf(TEXT("%s/%s/frames"), *UploadUrl, *ServerSessionId);
	const FHttpRequestRef Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(Url);
	Req->SetVerb(TEXT("POST"));
	Req->SetHeader(TEXT("Content-Type"), FString::Printf(TEXT("multipart/form-data; boundary=%s"), *Boundary));
	if (!ApiKey.IsEmpty())
	{
		Req->SetHeader(TEXT("X-Api-Key"), ApiKey);
	}
	Req->SetContent(MoveTemp(Body));
	Req->SetTimeout(UploadTimeoutSeconds);
	Req->OnProcessRequestComplete().BindWeakLambda(this,
		[this, Start, Count, Retry](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
		{
			OnBatchComplete(Start, Count, Retry, Response, bSucceeded);
		});
	Req->ProcessRequest();
}

void AGazeRecorderActor::OnBatchComplete(int32 Start, int32 Count, int32 Retry, FHttpResponsePtr Response, bool bSucceeded)
{
	const int32 MaxRetries = 3;
	const int32 Code = (bSucceeded && Response.IsValid()) ? Response->GetResponseCode() : 0;

	if (Code >= 200 && Code < 300)
	{
		RearmQuitFallback(UploadTimeoutSeconds + 5.f);  // progrediu -> adia o fallback
		--InFlightBatches;
		UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Lote [%d..%d] OK (HTTP %d). Cursor %d/%d."),
			Start, Start + Count - 1, Code, FMath::Min(NextFrameCursor, PendingFrameFiles.Num()), PendingFrameFiles.Num());
		PumpFrameBatches();
	}
	else if (Retry < MaxRetries)
	{
		// mantem o slot in-flight e re-tenta o MESMO lote
		UE_LOG(LogTemp, Warning, TEXT("[GazeRecorder] Lote [%d..%d] falhou (HTTP %d). Retry %d/%d."),
			Start, Start + Count - 1, Code, Retry + 1, MaxRetries);
		SendFrameBatch(Start, Count, Retry + 1);
	}
	else
	{
		--InFlightBatches;
		UE_LOG(LogTemp, Error, TEXT("[GazeRecorder] Lote [%d..%d] falhou em definitivo (HTTP %d). Seguindo (upload parcial)."),
			Start, Start + Count - 1, Code);
		PumpFrameBatches();
	}
}

void AGazeRecorderActor::SendComplete()
{
	const FString Url = FString::Printf(TEXT("%s/%s/complete"), *UploadUrl, *ServerSessionId);
	// O servidor monta o MP4 aqui (pode demorar com muitos frames) -> timeout e fallback folgados.
	RearmQuitFallback(UploadTimeoutSeconds + 35.f);

	const FHttpRequestRef Req = FHttpModule::Get().CreateRequest();
	Req->SetURL(Url);
	Req->SetVerb(TEXT("POST"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	if (!ApiKey.IsEmpty())
	{
		Req->SetHeader(TEXT("X-Api-Key"), ApiKey);
	}
	Req->SetContentAsString(TEXT("{}"));
	Req->SetTimeout(UploadTimeoutSeconds + 30.f);
	Req->OnProcessRequestComplete().BindWeakLambda(this,
		[this](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
		{
			const int32 Code = (bSucceeded && Response.IsValid()) ? Response->GetResponseCode() : 0;
			UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Complete -> HTTP %d. Encerrando."), Code);
			QuitNow();
		});
	Req->ProcessRequest();
	UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Finalizando sessao (complete) — montando MP4 no servidor..."));
}

void AGazeRecorderActor::QuitNow()
{
	if (bQuitting)
	{
		return;
	}
	bQuitting = true;
	GetWorldTimerManager().ClearTimer(QuitFallbackTimer);
	UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, /*bIgnorePlatformRestrictions=*/false);
}

void AGazeRecorderActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bSessionActive)
	{
		return;
	}

	// 1) Coloca a câmera de captura na POV do HMD.
	FVector CamLoc = GetActorLocation();
	FRotator CamRot = GetActorRotation();
	if (APlayerCameraManager* CM = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		CamLoc = CM->GetCameraLocation();
		CamRot = CM->GetCameraRotation();
	}
	Capture->SetWorldLocationAndRotation(CamLoc, CamRot);

	// 2) Eye tracking -> ponto 3D -> projeção 2D.
	const float T = TimeSinceStart();
	FGazeSample S;
	S.Time = T;

#if PLATFORM_ANDROID
	// Fallback anti-travamento: se o callback de permissao nao disparou (perdido/race) mas a
	// permissao ja foi concedida, libera a leitura. So roda enquanto bPermissionReady for false
	// (curto-circuita depois), entao o custo de JNI fica limitado ao intervalo pre-concessao.
	if (!bPermissionReady && UAndroidPermissionFunctionLibrary::CheckPermission(TEXT("com.oculus.permission.EYE_TRACKING")))
	{
		bPermissionReady = true;
	}
#endif

	// Exige direcao de olhar nao-degenerada: no caminho OpenXR, GetGazeData pode retornar true
	// com direcao ~zero quando o tracker ainda nao tem dado valido (sem calibracao/foco).
	FEyeTrackerGazeData Gaze;
	if (bPermissionReady && UEyeTrackerFunctionLibrary::GetGazeData(Gaze) && !Gaze.GazeDirection.IsNearlyZero())
	{
		const FVector Start = Gaze.GazeOrigin;
		const FVector Dir = Gaze.GazeDirection.GetSafeNormal();
		const FVector End = Start + Dir * MaxTraceDistance;

		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(GazeTrace), /*bTraceComplex=*/false, this);
		const bool bHit = GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params);
		const FVector P3D = bHit ? Hit.ImpactPoint : End;

		bool bInFront = false;
		const FVector2D UV = ProjectToCaptureUV(P3D, CamLoc, CamRot, bInFront);

		S.bValid = true;
		S.World = P3D;
		S.UV = bInFront ? UV : FVector2D(-1.f, -1.f);
		S.Confidence = Gaze.ConfidenceValue;

		GazeMarker->SetWorldLocation(P3D);
		GazeMarker->SetVisibility(bShowMarker);
	}
	else
	{
		S.bValid = false;
		GazeMarker->SetVisibility(false);
	}
	Samples.Add(S);

#if !UE_BUILD_SHIPPING
	// HUD de diagnostico na tela (build Development; nao aparece em Shipping). Toggle: bShowDebugOnScreen.
	// Chaves fixas (101..107) fazem cada linha ATUALIZAR no lugar em vez de empilhar.
	if (bShowDebugOnScreen && GEngine)
	{
		const bool bConn = UEyeTrackerFunctionLibrary::IsEyeTrackerConnected();
		const int32 PxX = (S.UV.X >= 0.f) ? FMath::RoundToInt(S.UV.X * FrameWidth) : -1;
		const int32 PxY = (S.UV.Y >= 0.f) ? FMath::RoundToInt(S.UV.Y * FrameHeight) : -1;
		GEngine->AddOnScreenDebugMessage(101, 2.f, FColor::Cyan,
			FString::Printf(TEXT("[EyeTracking] Conectado: %s  Permissao: %s"),
				bConn ? TEXT("SIM") : TEXT("NAO"),
				bPermissionReady ? TEXT("OK") : TEXT("aguardando")));
		GEngine->AddOnScreenDebugMessage(102, 2.f, S.bValid ? FColor::Green : FColor::Red,
			FString::Printf(TEXT("Gaze valido: %s   Confidence: %.2f"), S.bValid ? TEXT("SIM") : TEXT("NAO"), S.Confidence));
		GEngine->AddOnScreenDebugMessage(103, 2.f, FColor::White,
			FString::Printf(TEXT("GazeOrigin: %s"), *Gaze.GazeOrigin.ToString()));
		GEngine->AddOnScreenDebugMessage(104, 2.f, FColor::White,
			FString::Printf(TEXT("GazeDir:    %s"), *Gaze.GazeDirection.ToString()));
		GEngine->AddOnScreenDebugMessage(105, 2.f, FColor::White,
			FString::Printf(TEXT("Ponto 3D (mundo): %s"), *S.World.ToString()));
		GEngine->AddOnScreenDebugMessage(106, 2.f, FColor::White,
			FString::Printf(TEXT("Screen X,Y: %d , %d px   (uv %.3f , %.3f)"), PxX, PxY, S.UV.X, S.UV.Y));
		GEngine->AddOnScreenDebugMessage(107, 2.f, FColor::Yellow,
			FString::Printf(TEXT("Amostras: %d   Frames: %d   t=%.1fs"), Samples.Num(), FrameList.Num(), T));

		// Estado do MARKER: diagnostica "gaze valido mas bolinha invisivel" (mesh/material ausentes,
		// bolinha colada no olho = clipada pelo near plane, ou longe demais = raio sem hit).
		const float MarkerDistM = S.bValid ? FVector::Dist(S.World, CamLoc) / 100.f : -1.f;
		UMaterialInterface* MarkerMat = GazeMarker->GetMaterial(0);
		const TCHAR* DistWarn = TEXT("");
		if (S.bValid && MarkerDistM >= 0.f && MarkerDistM < 0.3f)
		{
			DistWarn = TEXT("  <- COLADO NO OLHO (trace batendo em algo? near clip)");
		}
		else if (S.bValid && MarkerDistM > (MaxTraceDistance / 100.f) * 0.99f)
		{
			DistWarn = TEXT("  <- raio sem hit (bolinha no fim do raio, pequena demais p/ ver)");
		}
		const FVector MarkerPos = GazeMarker->GetComponentLocation(); // onde a bolinha REALMENTE esta (mesmo oculta)
		GEngine->AddOnScreenDebugMessage(108, 2.f, FColor::Orange,
			FString::Printf(TEXT("Marker: vis=%d  mesh=%s  mat=%s  dist=%.2fm%s"),
				GazeMarker->IsVisible() ? 1 : 0,
				GazeMarker->GetStaticMesh() ? TEXT("OK") : TEXT("NULL!"),
				MarkerMat ? *MarkerMat->GetName() : TEXT("NULL"),
				MarkerDistM, DistWarn));
		GEngine->AddOnScreenDebugMessage(109, 2.f, FColor::Orange,
			FString::Printf(TEXT("Marker pos (mundo): X=%.0f Y=%.0f Z=%.0f cm   escala=%.2f (diam=%.0fcm)"),
				MarkerPos.X, MarkerPos.Y, MarkerPos.Z,
				GazeMarker->GetComponentScale().X, GazeMarker->GetComponentScale().X * 100.f));
	}
#endif

	// 3) Captura de frame no ritmo de VideoFps.
	if (VideoFps > 0.f && T >= NextFrameTime)
	{
		NextFrameTime += 1.f / VideoFps;
		const int32 Idx = ++FrameIndex;
		CaptureAndSaveFrame(Idx);

		FGazeFrame F;
		F.Index = Idx;
		F.Time = T;
		F.File = FString::Printf(TEXT("%s/%06d.jpg"), *FramesSubdir, Idx);
		FrameList.Add(F);
	}

	// 4) Flush periodico do gaze.json (~a cada 5s). Protege a sessao: no Quest standalone o
	//    EndPlay nem sempre dispara (botao Home / tirar o headset / OS mata o app), e sem isto
	//    os frames .jpg ficariam orfaos sem gaze.json e o heatmap quebraria.
	if (T >= NextJsonFlushTime)
	{
		NextJsonFlushTime += 5.f;
		WriteSessionJson();
	}
}

FVector2D AGazeRecorderActor::ProjectToCaptureUV(const FVector& WorldPoint, const FVector& CamLoc, const FRotator& CamRot, bool& bOutInFront) const
{
	const FVector D = WorldPoint - CamLoc;
	const FRotationMatrix Rot(CamRot);
	const FVector Fwd = Rot.GetUnitAxis(EAxis::X);
	const FVector Right = Rot.GetUnitAxis(EAxis::Y);
	const FVector Up = Rot.GetUnitAxis(EAxis::Z);

	const float Z = FVector::DotProduct(D, Fwd);
	bOutInFront = Z > KINDA_SMALL_NUMBER;
	if (!bOutInFront)
	{
		return FVector2D(-1.f, -1.f);
	}

	const float X = FVector::DotProduct(D, Right);
	const float Y = FVector::DotProduct(D, Up);

	const float HalfTanH = FMath::Tan(FMath::DegreesToRadians(CaptureFovDeg) * 0.5f);
	const float Aspect = (FrameWidth > 0) ? (static_cast<float>(FrameHeight) / static_cast<float>(FrameWidth)) : 1.f;
	const float HalfTanV = HalfTanH * Aspect;

	const float U = 0.5f + 0.5f * (X / Z) / HalfTanH;
	const float V = 0.5f - 0.5f * (Y / Z) / HalfTanV; // origem top-left
	return FVector2D(U, V);
}

void AGazeRecorderActor::CaptureAndSaveFrame(int32 FrameIdx)
{
	if (!RenderTarget)
	{
		return;
	}

	Capture->CaptureScene();

	FTextureRenderTargetResource* RTResource = RenderTarget->GameThread_GetRenderTargetResource();
	if (!RTResource)
	{
		return;
	}

	TArray<FColor> Pixels;
	FReadSurfaceDataFlags Flags(RCM_UNorm, CubeFace_MAX);
	Flags.SetLinearToGamma(false);
	if (!RTResource->ReadPixels(Pixels, Flags))
	{
		return;
	}

	const int32 W = FrameWidth;
	const int32 H = FrameHeight;
	const int32 Quality = JpegQuality;
	const FString FilePath = FPaths::Combine(SessionDir, FString::Printf(TEXT("%s/%06d.jpg"), *FramesSubdir, FrameIdx));

	// Encode JPEG + escrita em disco em background (não trava a game thread).
	AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, [Pixels = MoveTemp(Pixels), W, H, Quality, FilePath]() mutable
	{
		IImageWrapperModule& Mod = FModuleManager::GetModuleChecked<IImageWrapperModule>(FName("ImageWrapper"));
		TSharedPtr<IImageWrapper> Wrapper = Mod.CreateImageWrapper(EImageFormat::JPEG);
		if (!Wrapper.IsValid())
		{
			return;
		}

		// JPEG é opaco: força alpha 255.
		for (FColor& C : Pixels)
		{
			C.A = 255;
		}

		if (Wrapper->SetRaw(Pixels.GetData(), static_cast<int64>(Pixels.Num()) * sizeof(FColor), W, H, ERGBFormat::BGRA, 8))
		{
			const TArray64<uint8>& Data = Wrapper->GetCompressed(Quality);
			FFileHelper::SaveArrayToFile(Data, *FilePath);
		}
	});
}

void AGazeRecorderActor::WriteSessionJson()
{
	FString Out;
	const TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Out);
	W->WriteObjectStart();

	W->WriteObjectStart(TEXT("meta"));
	W->WriteValue(TEXT("captureFovDeg"), CaptureFovDeg);
	W->WriteValue(TEXT("frameWidth"), FrameWidth);
	W->WriteValue(TEXT("frameHeight"), FrameHeight);
	W->WriteValue(TEXT("videoFps"), VideoFps);
	W->WriteValue(TEXT("uvOrigin"), TEXT("top-left"));
	W->WriteObjectEnd();

	W->WriteArrayStart(TEXT("frames"));
	for (const FGazeFrame& F : FrameList)
	{
		W->WriteObjectStart();
		W->WriteValue(TEXT("idx"), F.Index);
		W->WriteValue(TEXT("t"), F.Time);
		W->WriteValue(TEXT("file"), F.File);
		W->WriteObjectEnd();
	}
	W->WriteArrayEnd();

	W->WriteArrayStart(TEXT("samples"));
	for (const FGazeSample& S : Samples)
	{
		W->WriteObjectStart();
		W->WriteValue(TEXT("t"), S.Time);
		W->WriteValue(TEXT("valid"), S.bValid);
		W->WriteArrayStart(TEXT("world"));
		W->WriteValue(S.World.X);
		W->WriteValue(S.World.Y);
		W->WriteValue(S.World.Z);
		W->WriteArrayEnd();
		W->WriteArrayStart(TEXT("uv"));
		W->WriteValue(S.UV.X);
		W->WriteValue(S.UV.Y);
		W->WriteArrayEnd();
		W->WriteValue(TEXT("confidence"), S.Confidence);
		W->WriteObjectEnd();
	}
	W->WriteArrayEnd();

	W->WriteObjectEnd();
	W->Close();

	int32 ValidCount = 0;
	for (const FGazeSample& S : Samples)
	{
		if (S.bValid) { ++ValidCount; }
	}

	const FString JsonPath = FPaths::Combine(SessionDir, TEXT("gaze.json"));
	FFileHelper::SaveStringToFile(Out, *JsonPath);
	UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] JSON salvo: %s (%d amostras, %d validas, %d frames)"), *JsonPath, Samples.Num(), ValidCount, FrameList.Num());
}
