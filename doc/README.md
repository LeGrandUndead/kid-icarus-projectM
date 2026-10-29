# Project documentation

Start here:

- [Architecture](ARCHITECTURE.md): the runtime and the game library, one frame end to end, where every Kid Icarus change is.
- [Game architecture](GAME_ARCHITECTURE.md): the game inside: its frame, managers, classes and scripts, the map tool, and how to find and change things.
- [The white after warps](WARP_WHITE_SCREEN.md): the 60 FPS warp fix, the worked example of that method.
- [Rollback of October 29](ROLLBACK_2026-10-29.md): what was set aside, to bring back one piece at a time.

Current build: `Launch-KIU.cmd` (PC interface). Documents that mention other
`Launch-KIU-*.cmd` launchers describe builds archived on October 16; they are
kept as the record of how the current build was reached.

- [HUD asset reconstruction](PC_HUD_ASSET_RECONSTRUCTION.md): the HUD rebuilt from the ROM, methods and checks.
- [Power state](POWER_STATE.md): where the equipped power lives in game memory.
- Engine and runtime: [native coverage](NATIVE_COVERAGE.md), [performance baseline](PERFORMANCE_BASELINE.md), [60 FPS mode](history/60FPS_ANALYSIS.md), [frame interpolation (set aside)](FRAME_INTERPOLATION.md), [culling and pop-in](CULLING_AND_POP_IN.md), [wide view by the game's camera](WIDE_VIEW.md), [Zakuro dependency census](ZAKURO_DEPENDENCY_CENSUS.md), [KIU Runtime v0](KIU_RUNTIME_V0.md).
- [Interpreted code](INTERPRETED.md): what still runs in the interpreter and how the library is rebuilt to cover it.

- [Single-screen status](PC_SINGLE_SCREEN_STATUS.md): what currently works, what is still dual-screen, launchers and fallbacks.
- [Single-screen audit](PC_SINGLE_SCREEN_AUDIT.md): original UI inventory, evidence and unresolved game-state identification.
- [Single-screen architecture](PC_SINGLE_SCREEN_ARCHITECTURE.md): isolated prototype, overlay, input boundaries and validation limits.

- [Rendering status](RENDERING_STATUS.md): current fixes, evidence and unresolved renderer issues.
- [PC presentation](PC_PRESENTATION.md): reversible 1080p profile, Tab screen/menu access and widescreen limits.
- [PC controls](PC_CONTROLS.md): working bindings and current control behavior.
- [Land camera](LAND_CAMERA.md): implementation and regression evidence for the frozen controls.
- [Shared font](FONT_SOURCE.md): replacement font source, attribution and recovery.
- [Next milestone](ROADMAP.md): controls, bottom-screen functionality and complete gameplay checks.

`history/` contains the initial executable audit, recompiler evaluation, format notes,
the superseded texture-LOD experiment, the AI-HD and original-art texture
tests and the HUD design-direction boards. These explain earlier decisions; they are
not installation instructions for the current runtime. User-supplied Word research
documents remain in this directory unchanged.

Use the root launcher. Do not reapply patch packs from `archive` to the live source.
The combined current runtime changes are saved in
git history (the runtime patch file was retired on October 28); older patch packs and the Python tests were
retired on October 16 and stay in git history.
