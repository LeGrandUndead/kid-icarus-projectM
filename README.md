# Kid Icarus: Uprising PC recompilation

**October 15 — PC interface (play-tested):** `Launch-KIU-PC-Interface.cmd`.
Gameplay uses one view: the game's own portraits (above the subtitles), the
lower-screen pictures the dialogue refers to (gags, cutaways, boss cards, top
center), special orbs / Power Palette (bottom-left) and intensity/heart
counters (below the score). Start opens the game's pause menu as a panel;
Resume closes it. Original view by default. Options: Esc twice > Settings >
Interface. `Launch-KIU-PC-Interface-Census.cmd` records lower-screen draws for
tracing. [Current status](doc/PC_SINGLE_SCREEN_STATUS.md).

**October 14 — separate gameplay preview:** `Launch-KIU-Gameplay-Preview.cmd`
adds a modest wider view and original live dialogue portraits to the gameplay
screen. F2 enables captured gameplay, Tab retains lower-screen access. This is
an experimental build with separate saves; the normal launcher stays the
fallback. [Implementation, validation and limits](doc/PC_SINGLE_SCREEN_ARCHITECTURE.md).

**October 13 — separate single-screen prototype:** launch `Launch-KIU-Single-Screen.cmd`.
Tab opens the original bottom screen as an interactive overlay and returns to
gameplay; F2 controls mouse capture; F9 toggles the legacy two-screen view.
This uses a separate executable and save/settings profile. The normal launcher
is unchanged. This is the presentation foundation, not yet the integrated
portrait/power HUD. [Audit](doc/PC_SINGLE_SCREEN_AUDIT.md) and
[architecture and validation](doc/PC_SINGLE_SCREEN_ARCHITECTURE.md).

**October 12 — original-art baseline restored:** `Launch-KIU.cmd` now opens the
working 1080p widescreen build with original game textures, existing rendering
fixes and PC controls. Texture replacements and experimental cubic filtering
are off. AI and other texture-test launchers are retired under
`archive/2026-10-12-texture-experiments`; their generated files remain inactive
for recovery. No runtime binaries or save files were replaced.
This launcher uses `build/user-data/experimental-pc/kiu`. The separate AI-build
saves remain preserved under `build/ai-hd-edition/data` and are not merged.

**October 11:** the experimental build fixes inconsistent HUD width and verified high-resolution pause-menu atlas seams. Original bitmap detail remains unchanged. [Validation and fallback](doc/PC_PRESENTATION.md).

**October 10 experimental update:** `Launch-KIU-Experimental.cmd` provides a separate 1080p/wider-view build and relative flight aiming with the guided camera retained. It uses copied saves and independent settings. HUD asset detail, complete widescreen coverage and menu transitions remain under validation. See [experimental setup and limitations](doc/PC_PRESENTATION.md).

Start the game with **Launch-KIU.cmd**. The launcher selects the local O2 native library and validates it against the supplied game executable. It still uses Zakuro for platform services, graphics and audio, with interpreter fallback.

**Current controls and project status: [doc/PC_CONTROLS.md](doc/PC_CONTROLS.md).**

Rendering fixes, validation and remaining limitations: [doc/RENDERING_STATUS.md](doc/RENDERING_STATUS.md).
The latest build preserves high-resolution land rendering after framebuffer readback.
Dialogue and menus use Azahar's open-source replacement font; [font source and recovery](doc/FONT_SOURCE.md).

F2 captures/releases the mouse. WASD moves, Alt walks, Shift requests one directional dash and left click attacks. While captured, E uses the air special or selected land power; 1/3 select land powers. Rebind these in Settings > Controls. F3 has no control-mode function. The land camera now receives relative mouse movement past the touch-screen border; the tested flight mouse behavior is preserved.

Useful options:

```powershell
./Launch-KIU.cmd --input-trace --record-input
./Launch-KIU.cmd --resolution 4
./Launch-KIU.cmd --legacy-controls
./Launch-KIU.cmd --original-land-camera
```

Current widescreen saves: `build/user-data/experimental-pc/kiu`. Legacy saves and shared font: `build/user-data/kiu`. Old patch packs and launchers: `archive` (recovery only). Active runtime: `tools/zakuro`. Our independent ARM translator: `recompiler`. Build and evaluation tools: `tools/recomp`. ROMs and generated game code stay local and ignored by Git.

For a blurry-scene report, use `Capture-Land.cmd`, reach the affected scene, press F8 once, then quit normally. This retains your saved resolution; `Diagnose-Graphics.cmd` intentionally forces 1x. Capture can introduce stutters, so measure normal gameplay through `Launch-KIU.cmd`.

Essential documentation is indexed in [doc/README.md](doc/README.md). Early audits and superseded experiment reports are in `doc/history`; retired patch packs and loose experiments are in `archive/2026-10-09-retired-material`, with a restoration manifest. Current sources, saves, recordings and test evidence remain available.

For the reversible 1080p presentation profile, run `Launch-KIU-1080p.cmd`. Tab opens the bottom screen with a menu cursor and returns to aiming. This preserves the original camera aspect with side bars; true 16:9 remains unfinished. See [PC presentation](doc/PC_PRESENTATION.md).
