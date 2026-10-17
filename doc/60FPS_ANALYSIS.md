# 60 FPS analysis

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

## Status

- Rate measurement: done (usage census).
- Main-loop wait: not yet traced. Next step is (1).
- Frame pacing at 30 fps: the frontend no longer skips cheap presents
  after a heavy blank (see [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md)),
  which matters for smooth 30 fps before any 60 fps work.
