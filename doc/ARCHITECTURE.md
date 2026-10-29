# Architecture: how the PC version is put together

Two programs make the PC version: the **game**, Kid Icarus: Uprising's own
code turned into a native library, and the **runtime**, a modified Zakuro
that plays the part of the 3DS around it and presents it as a PC game.
This page is the map of both and of where to change what. The game's
inside (its classes, managers and scripts) is mapped in
[GAME_ARCHITECTURE.md](GAME_ARCHITECTURE.md).

```text
ROM (user's own .3ds) ──► 3dsrecomp ──► generated C ──► compile_generated.py ──► 0004000000030100.dll
                                         ▲ overrides (tools/recomp/overrides/*.c)       (the game, 425 MB)
                                         ▲ hints (code found only while playing)              │
                                                                                               ▼
window, keyboard, mouse, pad ──► zakuro (frontend) ──► zakuro-core (3DS: CPU, kernel, services) ──► game code
                                      ▲                         │ GPU command lists
                                      │                         ▼
                              presenter ◄── screens ── zakuro-gpu (PICA200 on Vulkan) + kiu_ui (PC interface)
```

## The game library

- `tools/3dsrecomp` (external, `fearkov/3dsrecomp`) reads the ROM's code
  (`ExeFS/.code`, 12.4 MB of ARM) and writes one C function per game
  function found, about 448,000.
- `tools/recomp/compile_generated.py` compiles that C, six jobs at a time,
  into `build/kiu-aot-o2/0004000000030100.dll`. Rebuilding everything
  (`Rebuild-KIU-With-Hints.ps1`) takes about two hours.
- **Overrides** (`tools/recomp/overrides/*.c`, `RECOMP_OVERRIDE(addr)`)
  replace a game function when the library is generated, with or without
  calling the original. Permanent, code-level changes go here. No game code
  is copied into them, only addresses.
- **Hints**: code the runtime had to interpret because 3dsrecomp did not
  find it goes in `0004000000030100.hints` next to the library; the next
  rebuild covers it.
- `recompiler/arm32.py` is our own experimental translation backend,
  not used for the game library.

## The runtime, crate by crate (`tools/zakuro/crates`)

| Crate | Lines | What it is |
|---|---|---|
| `zakuro-common` | 0.6k | the 3DS address map, result codes, shared types |
| `zakuro-fs` | 1.7k | reading the ROM: NCSD, NCCH, ExeFS, RomFS, code decompression |
| `zakuro-cpu` | 5.1k | the ARM11 interpreter, used where the library has no code |
| `zakuro-core` | 17.7k | the console: memory, HLE kernel and services, the frame loop, the library glue, game-specific fixes |
| `zakuro-gpu` | 22.6k | the PICA200 GPU: command lists, shaders, the Vulkan renderer, the presenter, the PC interface layer (`kiu_ui`) |
| `zakuro` | 5.8k | the frontend: window, input, audio, menus, settings, and the PC presentation |

`zakuro` builds several programs (`[[bin]]` in its `Cargo.toml`), each a
one-line `main` choosing a mode. The game runs as
`zakuro-pc-interface.exe`, started by `Launch-KIU.cmd` through
`tools/recomp/launch.py`.

## One frame

The frontend runs one 3DS frame (a vertical blank, 1/59.83 s) per step,
then shows the screens.

1. **Input** (`zakuro/src/lib.rs`, `App::emulate`): keyboard and mouse
   (`input.rs`) and pads (`gamepad.rs`) become one 3DS input state: buttons,
   circle pad, touch. The KIU extras act here: Space jump (`kiu_jump.rs`)
   presses the D-pad like a player, clicks on top-screen menus become
   touches (`top_menus.rs`), the mouse camera's movement is queued for the
   game's camera code (`memory/kiu_mouse.rs`). A recording or replay
   (`replay.rs`) writes or supplies that input.
2. **Emulation** (`zakuro-core/src/lib.rs`, `System::run_frame`): the
   kernel schedules the game's threads (`kernel/`), and each runs in the
   library (`recompiled.rs`) until it makes a system call, its time is up,
   or it reaches code the library lacks (then the interpreter steps).
   System calls go to `kernel/svc.rs`; requests to 3DS services (files,
   GPU, sound, input...) to `services/`.
3. **GPU work**: the game queues command lists through `gsp::Gpu`
   (`services/gsp.rs`); `zakuro-gpu` decodes them
   (`Gpu::process_command_list`), runs the game's vertex shaders and draws
   on the host GPU (`raster.rs`, `raster/hardware.rs`), and turns finished
   frames into screen images (display transfers).
4. **End of frame** (`System::end_frame`): vertical-blank interrupts, the
   clock, timers, and the game-specific work that runs once a frame
   (`kiu_warp_fade.rs`).
5. **Sound**: the DSP is emulated at a high level (`services/dsp*.rs`);
   the frame's samples go to the host's output (`zakuro/src/audio.rs`).
6. **Showing**: `App::present` hands the screens to the presenter
   (`zakuro-gpu/src/backend/vulkan.rs`, sharing the renderer's device) with
   the overlay: the PC interface's HUD and portraits (`kiu_ui`) and the
   egui menus (`menus.rs`, `gui.rs`).

The 3DS draws both screens every frame. The PC version shows the top
screen; `kiu_ui` recognises the bottom screen's art by the identity of
its textures (`kiu_ui/scene.rs`) and redraws the parts worth keeping (HUD
islands, portraits) over the top screen, while `pc_presentation.rs`
decides what is shown when.

## Where the Kid Icarus changes are

Everything specific to the game, by where it acts.

| Where | File | What |
|---|---|---|
| game logic | `zakuro-core/src/kiu_frame_rate.rs` | 60 FPS mode: the display scheduler's interval and update step |
| game logic | `tools/recomp/overrides/kiu-60fps.c` | 60 FPS mode: per-object update counters at half rate |
| game logic | `zakuro-core/src/kiu_warp_fade.rs` | the white after warps: finishing a cut-off warp script's fade-in |
| game input | `zakuro-core/src/memory/kiu_mouse.rs` | mouse camera on land, flight aim |
| game input | `zakuro-core/src/services/hid.rs` | circle pad range (156) |
| frontend input | `zakuro/src/input.rs`, `kiu_jump.rs` | keyboard and mouse controls, Space jump |
| menus | `zakuro/src/top_menus.rs` | out-of-stage menus answered from the top screen |
| picture | `zakuro-gpu/src/kiu_ui/*` | HUD, portraits, scene recognition, bakes, layout |
| picture | `zakuro/src/pc_presentation.rs` | what is shown when |
| picture | `zakuro-gpu/src/replacements.rs` | HD texture replacements |
| code coverage | `tools/recomp/overrides/kiu-entry-points.c` | functions reached through jump tables |

Two ways to change the game's behaviour:

- **In the runtime** (like `kiu_warp_fade.rs`, `kiu_frame_rate.rs`):
  reading and writing the game's memory between frames or at chosen
  moments (system calls, write watches). Built in minutes, easy to switch
  off, limited to what memory shows.
- **In the game library** (overrides): replacing or wrapping a game
  function. As precise as editing the game's code, but each change costs a
  two-hour rebuild.

## Building and running

| Script | Does |
|---|---|
| `Build-And-Run.cmd` | closes the game, builds the runtime (`tools/recomp/Build-Runtime.ps1`, log `build/runtime-build.log`, about 4 minutes), starts it |
| `Launch-KIU.cmd` | starts the last build (`tools/recomp/launch.py`) |
| `Capture-Render.cmd` | builds and starts with F8 render captures |
| `tools/recomp/Rebuild-KIU-With-Hints.ps1` | regenerates and rebuilds the game library (about two hours) |
| `tools/recomp/Bench-KIU.ps1` | replays a recording headless, for comparisons |

## Data and settings

- Saves: `build/user-data/gameplay-preview/kiu/user/savedata`, never
  written by anything but the game.
- PC settings: `build/user-data/gameplay-preview/roaming/zakuro/*.txt`
  and `settings.toml`, separate from the saves.
- Log: `build/user-data/gameplay-preview/kiu/zakuro.log` (and
  `zakuro.previous.log`); usage report next to the library
  (`0004000000030100.usage.txt`).

## Investigating

| Tool | How |
|---|---|
| RAM snapshot | F7 or `KIU_RAM_SNAPSHOT`, `zakuro/src/ram_snapshot.rs`; offline comparison in Python |
| write watch | `Memory::watch_cpu_writes`: every write to a range, with the code address, registers and stack |
| replay | `launch.py --record-input`, `--replay` |
| render capture | `Capture-Render.cmd`, F8 |
| headless runs | `cargo run -p zakuro-core --example boot`, `trace`, `watch` |
| slow frames | `zakuro::slow_frame` in the log, usage report |
| game map | `tools/re/kiu_map.py`, see [GAME_ARCHITECTURE.md](GAME_ARCHITECTURE.md) |
