// Copyright (c) 2026. Eye tracking + gravação + heatmap para Meta Quest Pro.

#include "GazeRecorderActor.h"

#include "EyeTrackerFunctionLibrary.h"
#include "EyeTrackerTypes.h"

#include "Components/StaticMeshComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "TextureResource.h"
#include "UnrealClient.h"

#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Camera/PlayerCameraManager.h"
#include "UObject/ConstructorHelpers.h"

#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/DateTime.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformTime.h"
#include "Modules/ModuleManager.h"
#include "Async/Async.h"
#include "Serialization/JsonWriter.h"

#include "IImageWrapper.h"
#include "IImageWrapperModule.h"

#if PLATFORM_ANDROID
#include "AndroidPermissionFunctionLibrary.h"
#endif

AGazeRecorderActor::AGazeRecorderActor()
{
	PrimaryActorTick.bCanEverTick = true;

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
#if PLATFORM_ANDROID
	{
		TArray<FString> Perms;
		Perms.Add(TEXT("com.oculus.permission.EYE_TRACKING"));
		UAndroidPermissionFunctionLibrary::AcquirePermissions(Perms);
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
		UE_LOG(LogTemp, Display, TEXT("[GazeRecorder] Sessao encerrada pelo usuario (B): JSON salvo, fechando o app."));
	}
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

	FEyeTrackerGazeData Gaze;
	if (UEyeTrackerFunctionLibrary::GetGazeData(Gaze))
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
