// Copyright (c) 2026. Eye tracking + gravação + heatmap para Meta Quest Pro.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Interfaces/IHttpRequest.h"   // FHttpResponsePtr nas assinaturas dos callbacks de upload
#include "GazeRecorderActor.generated.h"

class UStaticMeshComponent;
class USceneCaptureComponent2D;
class UTextureRenderTarget2D;
class UMaterialInterface;

/** Uma amostra de gaze (registrada a cada frame de jogo). */
USTRUCT()
struct FGazeSample
{
	GENERATED_BODY()

	/** Segundos desde o início da sessão. */
	float Time = 0.f;

	/** false em piscadas / quando o eye tracker não tem dado válido. */
	bool bValid = false;

	/** Ponto 3D do olhar, em espaço de mundo (onde a bolinha é posicionada). */
	FVector World = FVector::ZeroVector;

	/** Projeção 2D normalizada [0..1] na câmera de captura. Origem no canto superior-esquerdo. */
	FVector2D UV = FVector2D(-1.f, -1.f);

	/** Confiança reportada pelo eye tracker (0..1). */
	float Confidence = 0.f;
};

/** Um frame de vídeo capturado. */
USTRUCT()
struct FGazeFrame
{
	GENERATED_BODY()

	int32 Index = 0;
	float Time = 0.f;
	/** Caminho relativo à pasta da sessão, ex.: "frames/000001.jpg". */
	FString File;
};

/**
 * Ator central do projeto.
 *
 * A cada frame:
 *  - lê o eye tracking (UEyeTrackerFunctionLibrary::GetGazeData);
 *  - faz um raycast e posiciona a bolinha vermelha no ponto 3D do olhar;
 *  - projeta esse ponto numa câmera de captura mono (que segue o HMD) -> (u,v) 2D;
 *  - registra uma amostra de gaze.
 * No ritmo de VideoFps, captura um frame da mesma câmera e grava como .jpg.
 * Ao encerrar (EndPlay), grava a pasta de sessão: frames/000001.jpg + gaze.json.
 *
 * Como o vídeo e o (u,v) saem da MESMA câmera, o alinhamento 2D<->vídeo é exato e a
 * sincronização tempo<->frame é automática.
 *
 * Requisitos: plugins OpenXR + OpenXR Eye Tracker habilitados, XR API = Epic Native OpenXR,
 * e a permissão com.oculus.permission.EYE_TRACKING (no manifesto + solicitada em runtime).
 * Basta colocar uma instância no nível.
 */
UCLASS()
class EYETRACKINGQUESTPRO_API AGazeRecorderActor : public AActor
{
	GENERATED_BODY()

public:
	AGazeRecorderActor();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** Liga/desliga a bolinha em runtime SEM afetar o log/gravação. */
	UFUNCTION(BlueprintCallable, Category = "Gaze")
	void SetMarkerVisible(bool bVisible);

	/** Encerra a sessão: grava o gaze.json final, para a captura e FECHA o app.
	 *  Ligue isto ao botão B do controle direito (ver instruções no guia). */
	UFUNCTION(BlueprintCallable, Category = "Gaze")
	void StopSessionAndQuit();

protected:
	// ---------------- Configuração ----------------

	/** Mostra a bolinha vermelha. O log/gravação rodam de qualquer forma. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gaze")
	bool bShowMarker = true;

	/** HUD de diagnóstico na tela (eye tracker conectado, gaze válido, screen X/Y, etc.).
	 *  Funciona em build Development (não em Shipping). Desligue para sessões "limpas". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gaze")
	bool bShowDebugOnScreen = true;

	/** Alcance do raycast do olhar (cm). */
	UPROPERTY(EditAnywhere, Category = "Gaze")
	float MaxTraceDistance = 1500.f;

	/** Diâmetro da bolinha (cm). 30 cm = bem visível p/ diagnóstico; reduza p/ sessões reais
	 *  (ajustável no Details da instância, sem recompilar). */
	UPROPERTY(EditAnywhere, Category = "Gaze")
	float MarkerSize = 30.f;

	/** Material da bolinha (de preferência Unlit/Emissive vermelho). Se nulo, cria um dinâmico vermelho. */
	UPROPERTY(EditAnywhere, Category = "Gaze")
	TObjectPtr<UMaterialInterface> MarkerMaterial;

	/** FOV horizontal da câmera de captura (graus). Define a projeção 2D E o enquadramento do vídeo. */
	UPROPERTY(EditAnywhere, Category = "Capture")
	float CaptureFovDeg = 82.f;

	UPROPERTY(EditAnywhere, Category = "Capture")
	int32 FrameWidth = 1024;

	UPROPERTY(EditAnywhere, Category = "Capture")
	int32 FrameHeight = 1024;

	/** Taxa de captura dos frames de VÍDEO (Hz). NÃO afeta o gaze, que é amostrado a cada
	 *  frame de jogo (~72-90 Hz). Mais alto = vídeo mais suave, porém mais carga de GPU/readback. */
	UPROPERTY(EditAnywhere, Category = "Capture")
	float VideoFps = 30.f;

	/** Qualidade JPEG (0-100). */
	UPROPERTY(EditAnywhere, Category = "Capture")
	int32 JpegQuality = 85;

	/** Endpoint da API: a rota .../api/v1/sessions. Ao encerrar (botão B) a sessão é enviada em
	 *  3 passos: cria (gaze.json) -> envia os frames em lotes -> finaliza. Vazio = não envia. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Upload")
	FString UploadUrl;

	/** Chave enviada no header X-Api-Key em todas as requisições do upload. Deixe igual à
	 *  QUESTPRO_API_KEY do servidor; vazio = não envia o header (servidor aberto/dev). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Upload")
	FString ApiKey;

	/** Timeout de cada requisição HTTP do upload (segundos). */
	UPROPERTY(EditAnywhere, Category = "Upload")
	float UploadTimeoutSeconds = 15.f;

	/** Quantos frames JPEG por requisição multipart. Lotes menores = menos memória/risco no Quest. */
	UPROPERTY(EditAnywhere, Category = "Upload")
	int32 UploadBatchSize = 20;

	// ---------------- Componentes ----------------

	UPROPERTY(VisibleAnywhere, Category = "Gaze")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, Category = "Gaze")
	TObjectPtr<UStaticMeshComponent> GazeMarker;

	UPROPERTY(VisibleAnywhere, Category = "Capture")
	TObjectPtr<USceneCaptureComponent2D> Capture;

	UPROPERTY(Transient)
	TObjectPtr<UTextureRenderTarget2D> RenderTarget;

private:
	/** Projeta um ponto de mundo na câmera de captura. Retorna (u,v) normalizado, origem top-left. */
	FVector2D ProjectToCaptureUV(const FVector& WorldPoint, const FVector& CamLoc, const FRotator& CamRot, bool& bOutInFront) const;

	/** Captura um frame e dispara o encode/escrita JPEG em background. */
	void CaptureAndSaveFrame(int32 FrameIdx);

	/** Escreve gaze.json com meta + frames[] + samples[]. */
	void WriteSessionJson();

	float TimeSinceStart() const;

	/** Sequência de upload ao encerrar: cria a sessão (gaze.json) -> envia os frames em lotes ->
	 *  finaliza (monta o MP4 no servidor). Só fecha o app no fim ou no timeout de segurança. */
	void BeginUploadSequence();
	void OnCreateComplete(FHttpResponsePtr Response, bool bSucceeded);
	void PumpFrameBatches();
	void SendFrameBatch(int32 Start, int32 Count, int32 Retry);
	void OnBatchComplete(int32 Start, int32 Count, int32 Retry, FHttpResponsePtr Response, bool bSucceeded);
	void SendComplete();
	/** (Re)arma o timer que fecha o app se o upload travar por 'Seconds' sem progresso. */
	void RearmQuitFallback(float Seconds);
	/** Fecha o app (uma vez só). */
	void QuitNow();

	bool bQuitting = false;
	FTimerHandle QuitFallbackTimer;

	// Em Android, aguarda a permissão de eye tracking ser concedida pelo usuário antes de iniciar
	// o tracker. Em outras plataformas considera concedido automaticamente.
#if PLATFORM_ANDROID
	bool bPermissionReady = false;
#else
	bool bPermissionReady = true;
#endif

	// Estado da sequência de upload (create -> frames -> complete).
	FString ServerSessionId;
	TArray<FString> PendingFrameFiles;
	int32 NextFrameCursor = 0;
	int32 InFlightBatches = 0;

	FString SessionDir;
	const FString FramesSubdir = TEXT("frames");
	double StartTimeSeconds = 0.0;
	float NextFrameTime = 0.f;
	float NextJsonFlushTime = 0.f;
	int32 FrameIndex = 0;

	TArray<FGazeSample> Samples;
	TArray<FGazeFrame> FrameList;

	bool bSessionActive = false;
};
