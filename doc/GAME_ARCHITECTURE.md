# The game's architecture: Kid Icarus: Uprising inside

What we know of how the game itself is built, where each part is, and how
to find and change things in it. The runtime around it is in
[ARCHITECTURE.md](ARCHITECTURE.md). Addresses are the USA release's
(`0004000000030100`).

Everything here comes from three sources, all on the user's own files:

- **the game map** (`tools/re/kiu_map.py`), built from the game's code in
  under two seconds: 38,857 functions, 209,676 calls, 4,284 method tables
  (763 named by the game), 4,340 fields read by name in 707 parameter
  readers, 112 singletons;
- **memory snapshots** taken while playing (F7, `ram_snapshot.rs`);
- **traces** of writes to chosen memory (`Memory::watch_cpu_writes`).

Names we gave things live in `tools/re/kiu_names.txt`; a `?` marks a name
not confirmed yet. Add to it whenever something is understood.

## Using the map

```text
python tools/re/kiu_map.py build ROM/gameFiles        (once; writes build/re/kiu-map.sqlite)
python tools/re/kiu_map.py find Warp                  classes, fields, names, our names
python tools/re/kiu_map.py fn 0x00AEAD80              what a function is: class and method, fields, names, callers
python tools/re/kiu_map.py class anime_command::StartFade
python tools/re/kiu_map.py flow 0x00102AB0            the calls a function makes, in order, labelled
python tools/re/kiu_map.py callers 0x00538B34
python tools/re/kiu_map.py singletons Manager
python tools/re/kiu_map.py dis 0x00AEAD80 40          (needs capstone)
```

It needs Python with numpy. The map holds addresses and the game's own
names only, and stays in `build/`.

## Memory

| Range | What |
|---|---|
| `0x00100000`-`0x00C950F0` | code, 11.6 MB of ARM |
| `0x00C96000`-`0x00D31990` | read-only data: names, method tables, constants |
| `0x00D32000`-`0x00D63C78` | data; the singletons' pointers are at `0x00D635xx`-`0x00D638xx` |
| to about `0x00F36000` | zeroed data (BSS): most singletons' objects themselves |
| `0x14000000` up | the heap: actors, scripts, stages, resources |

## One frame

```text
App.mainLoop 0x00102AB0
 └ each system in the app's list (+0x48), vfunc 0
    └ display scheduler (0x00D63824): waits +0x54 = 2 blanks a frame, hands the update the ticks that passed
       └ TaskManager.run 0x00BA9A50 (instance at 0x00D637AC): phases 0-14, each a list of tasks, vfunc +0x14
          phase 1   Phase1Manager?        0x00D636D4
          phase 2   InputManager          0x00D636E4    InputTaskUpdate
          phase 3   four sequence helpers 0x00D635C8, 0x00D635D8, 0x00D63648 (online, avatars), 0x00D63638 (enemy common)
          phase 4   ScreenFadeManager     0x00D635F0
          phase 6   StageManager          0x00D636F4    StageTaskPostUpdate
          phase 7   GameManager           0x00D635E0    the most used manager (588 places)
          phase 8   ActorManager          0x00D636CC    ActorTaskUpdate, ActorTaskEvCalc, ActorTaskPostUpdate
          phase 9   Phase9Manager?        0x00D636BC
          phase 12  GeneratorManager?     0x00D63608    GeneratorWork
       └ drawing: profiled as "Top", "Bottom", "GPU"; effects as "psl::effect::Manager"
```

The phases are as a chapter 9 snapshot had them; menus and other modes
may register other tasks. A task is a sub-object at `+0x20` of its
manager (multiple inheritance: its method table begins with the offset to
its owner, `-0x20`), so a manager can have several tasks in different
phases (the actor manager has three).

The game's profiler, `ProfileScope.begin` (`0x00916FAC`), names the
per-frame systems: `Top`, `Bottom`, `GPU`, `UpdateWorld` (a model's world
matrices), `psl::effect::Manager`, and the task updates above.

### Time

The update step is the float at `0x00828E30`: 2.0 at 30 FPS, in 60ths of
a second. Most systems scale by it (1,694 timers in the 30/60 comparison).
About 50 count updates instead; most are the per-object "updates alive"
counters at `+0xB0`, advanced by `0x00917618` once an update. The 60 FPS
mode (`kiu_frame_rate.rs`) sets the scheduler to every blank and the step
to 1.0, and `tools/recomp/overrides/kiu-60fps.c` runs `0x00917618` every
other update. See `doc/history/60FPS_ANALYSIS.md`.

## Classes and data

The game is C++ with its own reflection, which is why so much is named:

- **Type information**: a class's method table slot 1 returns its type
  information, built from its name and size the first time
  (`anime_command::StartFade`, 0x30 bytes). The map names 763 tables
  this way.
- **Parameters by name**: a class's parameter reader (a method, slot 4
  for the script commands) registers each field with its name, offset and
  default (`anime_command::WarpControl`: `start_` +0x10, `warp_` +0x3C,
  `end_` +0x68, `warpPos_` +0x94, `isBlack_` +0xC0, `fadeTime_` +0xC4 =
  30, `waitTime_` +0xD0 = 30). The values come from the game's data files,
  so behaviour is largely data-driven.

| Namespace | Named classes | What |
|---|---|---|
| `actor_param` | 322 | parameters of characters, enemies, objects |
| `anime_command` | 353 | animation script commands (fades, warps, waits, sounds, effects, camera) |
| `psl` | 57 | Project Sora's engine library: actors, models, locators, effects, commands |
| `actor_condition` | 22 | conditions actors test |
| others | | `boss`, `item_actor`, `game_rule_def`, `game_flag`, network (`NetZ`, `StationManager`), Nintendo's SDK (`nn`) |

### Animation scripts

Much of what happens in a stage is a script of `anime_command`s run by an
actor's animation component: `AnimeScript.update` (`0x0048CA44`) and
`AnimeScript.runCommands` (`0x0048CB3C`) run the commands in order, each
asked `+0x20` then `+0x24` whether it is done, until one is not. Commands
are linked through `+8`. Chapter 9's warp pad, as read from memory:

```text
EventPlayerStop, PlaySE,
StartFade out to white 16 frames, WaitFrame 16, Warp, WaitFrame 4,
StartFade back in 16 frames, EventPlayerStop, ...
```

To find a script, look for its command objects in a snapshot by their
method table (`kiu_map.py class anime_command::<Name>` gives it); names
like `YAK_G09_Warp_G05_00` sit beside them.

## Systems mapped so far

| System | Where | Notes |
|---|---|---|
| frame timing | display scheduler `0x00D63824`, step `0x00828E30`, ages `0x00917618` | 60 FPS mode |
| screen fades | `ScreenFader` `0x00D63620` (faders per screen at `+0xB8`), `ScreenFade.start` `0x00538B34` | layout in `kiu_names.txt`, `WARP_WHITE_SCREEN.md` |
| warps | `WarpController` (player `+0x524`), `anime_command::Warp`, `WarpControl` | `WARP_WHITE_SCREEN.md` |
| land camera | found through its input readers | `LAND_CAMERA.md`, `memory/kiu_mouse.rs` |
| cameras and lens | camera: view updater `+0`, projection updater `+4` (fov `+0x10`, aspect `+0x14`), matrix `+0x6C` (`0x00B4F89C`), frustum (`0x00B4F948`), lens cache `+0x114` (`0x0090DC70`) | `WIDE_VIEW.md`, `kiu-wide-view.c` |
| stage parameters | `0x006F3058`: field of view, near/far, flight camera distance and movable area | `kiu_names.txt` |
| power palette | count, selection, entries | `POWER_STATE.md`, `kiu_jump.rs` |
| bottom-screen UI | recognised by its textures | `PC_PRESENTATION.md`, `kiu_ui` |

Not mapped yet: what phases 1 and 9 are, the actor model (player, enemies,
their parameters and states), the stage and area loading, the HUD's game
side, menus' game side, the data files' formats (RomFS archives), sound.

## Where to touch

| To change | Touch | Cost |
|---|---|---|
| a value the game reads from data (a speed, a time) | the parameter in memory once loaded, from the runtime; later the data file | minutes |
| what happens at one moment (a fade, a warp) | the runtime, reacting to a write or a frame (`kiu_warp_fade.rs`) | minutes to build, easy to switch off |
| a function's behaviour, permanently | an override (`tools/recomp/overrides`) | a 2-hour library rebuild |
| how the game is shown or controlled | the runtime: `kiu_ui`, `input.rs`, `kiu_mouse.rs` | minutes |

How to work on a problem, as the warp white was solved:

1. **Map**: `kiu_map.py find` the names involved; read the classes,
   fields and callers. Check `kiu_names.txt` and the docs above.
2. **Measure**: a snapshot of the bad moment, and a write watch on the
   memory involved, logging who writes it (registers and stack give the
   caller). Never guess from symptoms.
3. **Read**: the few functions the trace names, with `flow` and `dis`.
4. **Fix the smallest thing at the cause**, in the game's own terms
   (its scripts, its fields, its functions), off when not needed.
5. **Test** in the game, then **name** what was learned in
   `kiu_names.txt` and write it down here or in its own doc.
