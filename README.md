# Kid Icarus: Uprising PC recompilation

Native PC version of Kid Icarus: Uprising: the game's ARM code compiled ahead
of time into a Windows library (`build/kiu-aot-o2`), run by our fork of the
Zakuro 3DS runtime (`tools/zakuro`) for platform services, graphics and audio.
Code the library does not cover falls back to the interpreter; the title bar
shows the interpreted share.

## Play

Double-click **`Launch-KIU.cmd`**. It starts the single-screen PC interface
build (`zakuro-pc-interface.exe`) at 1080p with PC controls:

- one view: the game's portraits above the subtitles, lower-screen pictures
  top center, special orbs / Power Palette under the health bar, intensity and
  heart counters under the score;
- Start opens the game's pause menu as a panel; Tab shows the lower screen,
  F9 the original two screens, F2 captures the mouse, F11 fullscreen;
- the HUD uses the game's own art rebuilt sharper from your ROM
  (`build/texture-work/hud-pc`, local only).

Options (Esc twice > Settings): Interface, Controls, Graphics. Launcher
extras, for example `Launch-KIU.cmd --hud-art original` or `--input-trace`:
see `python tools/recomp/launch.py --help`.

Saves: `build/user-data/gameplay-preview/kiu`. The save format is the game's
own and is never modified.

## Layout

| Path | What |
|---|---|
| `Launch-KIU.cmd` | the launcher |
| `build/kiu-aot-o2` | the compiled game library (local, from your ROM) |
| `build/native-ui`, `build/texture-work` | UI catalog and HUD art sources/pack (local) |
| `build/user-data` | saves and settings (local) |
| `tools/zakuro` | runtime source; `target/release/zakuro-pc-interface.exe` |
| `tools/3dsrecomp`, `recompiler` | ARM-to-C recompiler |
| `tools/recomp` | launcher, library build scripts, HUD pack and UI source tools |
| `doc` | documentation ([index](doc/README.md)) |
| `archive` | retired builds, launchers and experiments (recovery only, local) |

ROMs, generated game code and anything made from game assets stay local and
are ignored by git.

## Rebuild

- Game library: `tools/recomp/Build-KIU-Optimized.ps1` (uses `environment.ps1`).
- HUD pack: `python tools/recomp/build_hud_pc_pack.py build/texture-work/hud-sources`
  ([details](doc/PC_HUD_ASSET_RECONSTRUCTION.md)).
- UI sources: `python tools/recomp/prepare_native_ui_sources.py` and
  `tools/recomp/prepare_dialogue_sources.ps1`.
- Runtime: `cargo build --release -p zakuro --bin zakuro-pc-interface` in
  `tools/zakuro` (runtime changes are also kept as
  `tools/recomp/patches/kiu-pc-runtime.patch`).
- Recompile with the places still interpreted: `tools/recomp/Rebuild-KIU-With-Hints.ps1`
  ([details](doc/INTERPRETED.md)).

## Cleanup (October 16)

Only the PC interface build is kept. Older launchers, executables, research
and test tools and generated packs moved to `archive/2026-10-16-cleanup` on
the PC (`MOVED.txt` there lists them) and are in git history. Earlier
retirements: `archive/2026-10-12-texture-experiments`,
`archive/2026-10-09-retired-material`.

Status and known limits: [doc/PC_SINGLE_SCREEN_STATUS.md](doc/PC_SINGLE_SCREEN_STATUS.md).
Controls: [doc/PC_CONTROLS.md](doc/PC_CONTROLS.md).
