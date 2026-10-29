# 60 FPS analysis

> October 29: this is the 60 FPS mode in use again (`kiu_frame_rate.rs`).
> The chapter 9 white screens it caused are fixed in
> [WARP_WHITE_SCREEN.md](../WARP_WHITE_SCREEN.md); frame interpolation,
> tried in its place on October 28, is set aside
> ([FRAME_INTERPOLATION.md](../FRAME_INTERPOLATION.md)).

## What controls the rates today

**Simulation and presentation are both tied to the 3DS vertical blank.**

- The runtime advances the guest by exactly one 3DS frame per host step:
  `CYCLES_PER_FRAME = 4,481,136` cycles at 268 MHz, ≈16.71 ms
  (`zakuro-core/src/lib.rs`, `run_frame`). At the end of each it signals
  the vertical-blank interrupts (`Pdc0`, `Pdc1`), picks up buffer swaps the
  game queued in GSP shared memory, and runs the DSP every 4.9 ms of guest
  time.
- The frontend paces that to wall-clock time, one step every
  `FRAME_TIME` ≈ 16.71 ms (59.83 Hz), sleeping when ahead and catching up
  (up to 200 ms) when behind (`zakuro/src/lib.rs`, `step`). It presents the
  current screens after each step, in Vulkan mailbox mode.
- So the PC shows at most one new game picture per 3DS vertical blank, and
  the game's whole world advances by its own internal timing per blank.

## What the game does

Measured with the usage census (October 17): **0.50 buffer swaps per
vertical blank on each screen**, over 304 seconds of gameplay and over the
menus and movie. Kid Icarus: Uprising draws a new picture every other
vertical blank: it is a **30 fps game** in everything recorded so far.

Consequences:

- "60 FPS" is not a runtime setting. The runtime already runs the guest at
  the 3DS's full 59.83 Hz; the game itself chooses to render every second
  blank.
- Raising the host refresh rate alone (144 Hz monitor, uncapped present)
  would only show the same 30 game frames more often.

## Ways to get 60 fps, from least to most invasive

1. **Find the game's frame-rate switch.** Many 3DS titles keep a
   "vblanks per frame" value (1 or 2) that their main loop waits on
   (`gspWaitForVBlank` called once or twice, or a frame-skip counter), with
   game logic stepped once per rendered frame. If KIU's logic uses a fixed
   1/30 s step per rendered frame, halving the wait doubles game speed;
   if it scales by a measured or configured delta time, it would run
   correctly at 60.
   - *How to find it:* the usage census shows ≈50 `SleepThread` and ≈8
     `WaitSynchronizationN` per blank; trace which wait the render thread
     makes on the vertical-blank event (`Pdc0`) and how many times per
     rendered frame, then find the constant or variable that decides it.
     The interpreted-code hints and the recompiled library give exact
     function addresses to look at.
   - *Test:* patch the value through an override
     (`tools/recomp/overrides/`) or a RAM write, and compare a timed
     section (an air chapter's fixed-length flight) against the original:
     same duration means logic follows delta time; half duration means it
     is frame-locked.
2. **If logic is frame-locked: separate simulation and presentation.** Run
   the game's update at 30 Hz as now, but render twice per update with
   interpolated transforms. This needs the game's object/camera transforms
   (found via the renderer's matrix uniforms) and is a large piece of work;
   it is the standard approach of high-frame-rate PC ports.
3. **If only parts are frame-locked** (animation timers, particle
   lifetimes, projectile speeds, AI timers, UI tweens), patch those
   individually with overrides. Only worth doing after (1) shows the main
   loop can run at 60.

Things to check for frame dependence once (1) is possible: projectile
speed and lifetime, enemy AI and script timers, particle lifetimes,
animation playback, camera smoothing, UI animations, the special attack
gauge, and dialogue timing (dialogue is voiced, so it must stay in sync
with audio, which runs on the DSP clock and is not affected).

## Not to do

- Do not shorten `FRAME_TIME` or run two guest frames per host frame: the
  whole game, audio included, would run at double speed.
- Do not change the PICA/GSP swap handling to present more often: there
  is no new picture to present.

## Status (October 21): playable 60 fps mode

**Settings > Graphics > "60 FPS (experimental)"**, applied immediately and
kept in `%APPDATA%/zakuro/kiu-60fps.txt` (`launch.py --sixty-fps` /
`--thirty-fps` for one run). Code: `zakuro-core/src/kiu_frame_rate.rs`.

### What it does

The game's display scheduler (singleton at `0x00D63824`) waits `+0x54` =
2 vertical blanks per frame. Its update step, the float 2.0 at
`0x00828E30` (read by `0x00828D68`, turned into per-system deltas by
`0x00607A4C`), is in 60ths of a second. Found by the October 18-19
research (`codex/60fps-research`), the mode sets, at the scheduler's
GetSystemTick calls (`0x00991164` before its callback, `0x009911CC` after):

- interval 1 and the even-tick carry (`+0xA8/+0xAC`) cleared: a frame every
  blank;
- the update step 1.0: everything the game scales by its step keeps its
  speed;
- elapsed ticks (`+0xB0`) 1, before and after the callback.

Turning it off puts 2 and 2.0 back at the next frame.

### How correct it is

Same recording, 30 vs 60 from vblank 6000 (`Bench-KIU.ps1 -Fps60`):

- **Flight path, scripted events and captions** match the original at
  every 2.5 s checkpoint from 6000 to 9000 (21 screenshots each). Score and
  hits differ: the replayed aim lands at different moments.
- **RAM comparison** (`KIU_RAM_SNAPSHOT_AT`, snapshots 2, 4, 8 and 16
  blanks after the switch, `tools`-side analysis): 1,694 changing integers
  advance at the same rate in both modes; **50 advance twice as fast**, no
  floats do. The 50 are update counters: per-object "updates alive"
  counters (`+0xB0`, incremented by `0x00917618` for every object in its
  manager's lists), a few scene/scheduler counters and two message-id
  counters.
- `tools/recomp/overrides/kiu-60fps.c` runs `0x00917618` every other
  update in 60 fps mode. In the library rebuilt on October 21 the same
  comparison finds 16 update-rate counters left (from 50), none of them
  per-object; flight path and captions still match at 7500, 8250 and 9000.
- Remaining counters run at update rate; their readers are not known yet.
  Write watches (`KIU_WATCH_WRITES`) give each counter's writer:
  `0x00A408A8` (sample counts next to time-scaled sums), `0x006F78BC`,
  `0x00929F08`, `0x001B30F4`, `0x0072C1F4`, `0x009100D4`.

### Performance

The renderer's aliasing write-backs were the cost of a rendered frame (see
[PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md)). After removing them, a
60 fps headless run spends 2.2 ms a blank on GPU commands (was 9.5), and
the windowed 1080p/5x replay held 59.8 frames a second, emulating 4-12 ms a
frame, from boot through land gameplay.

### Not verified yet

Sound timing by ear, land combat feel, bosses, menus with animations,
cutscene video playback at 60 (the replay went through the menus at 60
without desynchronising, which suggests they are step-based too).
