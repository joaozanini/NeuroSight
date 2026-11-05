using UnrealBuildTool;

public class EyeTrackingQuestPro : ModuleRules
{
	public EyeTrackingQuestPro(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core", "CoreUObject", "Engine", "InputCore",
			"EyeTracker",          // UEyeTrackerFunctionLibrary, FEyeTrackerGazeData
			"HeadMountedDisplay",  // POV do HMD via PlayerCameraManager
			"RenderCore", "RHI",   // ReadPixels do render target
			"ImageWrapper",        // encode JPEG dos frames
			"Json",                // exportação do gaze.json
			"HTTP"                 // upload do gaze.json para a API
		});

		if (Target.Platform == UnrealTargetPlatform.Android)
		{
			// Permissão de eye tracking em runtime (o include no .cpp está sob #if PLATFORM_ANDROID).
			PrivateDependencyModuleNames.Add("AndroidPermission");
		}
	}
}
