# Project documentation

Current build: `Launch-KIU.cmd` (PC interface). Documents that mention other
`Launch-KIU-*.cmd` launchers describe builds archived on October 16; they are
kept as the record of how the current build was reached.

- [HUD asset reconstruction](PC_HUD_ASSET_RECONSTRUCTION.md): the HUD rebuilt from the ROM, methods and checks.
- [Power state](POWER_STATE.md): where the equipped power lives in game memory.

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
`tools/recomp/patches/kiu-pc-runtime.patch`; the frozen controls patch is separate.
