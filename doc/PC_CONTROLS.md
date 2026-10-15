# Current PC controls

**October 10 experimental update:** `Launch-KIU-Experimental.cmd` provides a separate 1080p/wider-view build and relative flight aiming with the guided camera retained. It uses copied saves and independent settings. HUD asset detail, complete widescreen coverage and menu transitions remain under validation. See [experimental setup and limitations](PC_PRESENTATION.md).

Use `Launch-KIU.cmd`. There is one control scheme; F3 no longer changes it.

- Tab: temporarily show the bottom screen with a clickable cursor; press again to return and restore aim.
- F2: capture/release mouse. Escape also releases capture.
- Mouse: bounded held-touch aim in flight; a game-side relative camera hook on land. No automatic lift/recenter at edges or while idle.
- WASD: move/run; Alt: walk.
- Shift + direction: one directional dash request per press. Shift may precede the direction.
- Left click: attack while captured. X/Z: confirm/back, Enter: Start.
- E: air super attack / use the selected land power, while captured.
- 1 / 3: select previous/next land power, while captured.
- Mouse wheel (October 15, PC interface build): down = next land power, up = previous, while captured and only on land. Selecting never uses a power.

Controller merging is unchanged. The normal launcher uses the working O2 DLL.

## Equipped powers and air special

Keep F2 mouse capture enabled. On land, press 1 or 3 to highlight a power on the
bottom screen, then E to activate it. In flight, press E for the super attack.
The game still enforces available charges, cooldowns and eligible situations.
No F2/Z/click/F2 sequence is needed for equipped powers; aiming remains held.
These are D-pad aliases, so 1/3 also invoke the game's special attack in flight.
They do not add a game-mode detector. Existing arrows still work.

### Mouse wheel (October 15)

The wheel sends the same single D-pad presses as 1/3, one per notch, with a
release between presses so none merge. A fast flick queues at most four steps;
reversing direction cancels queued steps; touchpad deltas accumulate to whole
notches (about 40 px each). It works only while captured and only when land
gameplay was seen in the last 20 frames: the land camera hook consumed mouse
input, or the Power Palette is drawn in the relocated HUD. In flight the wheel
does nothing, because these presses would fire the air special. Settings >
Controls: "KIU: mouse wheel selects powers on land" and "Reverse wheel
direction". With `--original-land-camera` and no PC interface HUD there is no
land signal, so the wheel stays inactive.

Rebind the three `KIU:` entries in Settings > Controls. Avoid keys already used
for movement, attack or runtime shortcuts. Existing saved settings acquire the
new defaults without resetting other preferences. The aliases are inactive when
mouse capture is released, and in legacy-controls mode.

This covers equipped powers, not every contextual bottom-screen action. Vehicle
controls and other touch-only interactions still need an audit. Free jumping on
Space is deferred; using an equipped Sky Jump power still consumes its charges.

October 9 validation: three isolated 13,300-frame gameplay replays confirmed
D-pad down consumes one air-special charge and activates Sky Jump on land;
D-pad right selects Autoreticle, and down activates it (3 to 2 charges). Input
regression tests cover preserved aim/movement, brief taps, independent arrow
keys, capture/focus reset, rebinding and settings compatibility. Human gameplay
feel and the full set of powers remain to be checked.

## Land camera status

The normal launcher enables the relative land-camera hook. It replaces movement
at the game's actual camera calculation while preserving visible touch position.
Land-practice replays verify turning at a fixed touch border, reversal and
stopping at rest. Air-practice screenshots match the previous behavior exactly,
and the hook makes no camera writes there.

Use `Launch-KIU.cmd --original-land-camera` to disable just this hook. F3 remains
inactive. The current executable is the verified USA revision; a different
revision fails the signature check. This does not redesign the camera rig,
field of view or pitch limits. See [LAND_CAMERA.md](LAND_CAMERA.md).

## Diagnostics

`Launch-KIU.cmd --input-trace --record-input` records into `build/input-traces`,
including initial save state and runtime/library hashes. Normal saves remain
under `build/user-data/kiu`. Use isolated copies for replays.

`Launch-KIU.cmd --resolution 4` selects 1600x960 internal geometry rendering;
`--scale` changes window size only. This is not expanded FOV or native 1920x1080.

## Project layout and recovery

- `tools/zakuro`: active runtime source and executable.
- `tools/recomp`: launcher, build driver and runtime patches.
- `recompiler`: independent ARM compiler research.
- `ROM`: extracted game; supplied original stays at project root.
- `build`: native libraries, saves, traces, evaluation results and recovery binaries.
- `doc`: current notes; older evaluations and research are in `doc/history`.
- `archive`: retired experiments; manifests record original paths. Do not reapply old patch packs.

Before this controls pass, source files, runtime and patch were copied to
`build/controls-before-powers-20261009`. No ROM, personal save, working O2 build,
staged file or toolchain was deleted. Next steps are in [ROADMAP.md](ROADMAP.md).

See [PC presentation](PC_PRESENTATION.md) for the separate 1080p profile, screen switching and rollback. Tab changes the view without pausing combat or closing the game's own menus.

## Research aid: RAM snapshots

`python tools/recomp/launch.py --pc-interface --ram-snapshots` (add the usual
launcher options) makes F7 save the game memory to `build/ram-snapshots/<time>`
(local only, never committed). `tools/recomp/ram_diff.py` compares snapshots,
for example a power whose uses go 4 -> 3 -> 2:
`python tools/recomp/ram_diff.py a.bin b.bin c.bin --values 4 3 2`.
Used to locate the equipped-power state for the Space jump experiment.
