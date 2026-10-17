# Performance baseline

## Setup the numbers come from

- **PC:** NVIDIA GeForce RTX 3060, Windows, Vulkan, presenting in mailbox
  mode (from the runtime log).
- **Build:** `Launch-KIU.cmd` (PC interface, `zakuro-pc-interface.exe`),
  internal resolution 5x, hardware rasterizer, recompiled library of
  October 17 (0% interpreted).
- **Camera:** the PC interface camera scale saved at 0.75 (the widest view,
  see [CULLING_AND_POP_IN.md](CULLING_AND_POP_IN.md)).

## How to record a baseline

1. `Launch-KIU.cmd --diagnostics` turns on, in
   `build/user-data/gameplay-preview/kiu/zakuro.log`:
   - `zakuro::fps` every 0.5 s: frames emulated and shown a second, mean and
     longest time emulating and showing;
   - `zakuro_gpu::times` every 600 GPU batches: GPU time by kind of work
     (draw, upload, clear, transfer, capture, copy, download, barrier),
     barriers, render passes, draws, shaded vertices and fragments, and how
     long the host waited for the GPU;
   - `zakuro_gpu::pipelines`: every pipeline compiled or taken from the
     cache on a draw, with the time it took.
2. Every run, diagnostics or not, writes
   `build/kiu-aot-o2/0004000000030100.usage.txt` on exit and every minute:
   host frame-time histograms (emulating, showing, the GPU commands' CPU
   side), frames skipped to catch up, GPU commands and buffer swaps per
   frame, service requests, kernel calls, and particle-shader cost.
3. Play the scenario, close the game normally, keep both files.

The interpreted-code report written beside it is described in
[NATIVE_COVERAGE.md](NATIVE_COVERAGE.md).

## Baseline, October 17

### Menus, opening movie, title (106 s, `--diagnostics`)

| Metric | Value |
|---|---|
| frames emulated / shown a second | 59.8 / 59.8 |
| emulating a frame | 4.3-7.3 ms mean per half second, at most ~13 ms |
| showing a frame | 0.0-0.4 ms |
| GPU time | ~255 ms per 600 batches (≈0.43 ms a batch): draw 135, capture 43, transfer 36, other 10, barrier 11, upload 10, clear 9 |
| draws | 6,000 per 600 batches, 1,200 render passes, 3,600 barriers |
| host waited for GPU work | ~110-140 ms per 600 batches, ~450 times |
| buffer swaps | 0.5 a frame on each screen (30 fps) |

The GPU itself is nowhere near busy at 5x (under 0.5 ms of GPU work per
batch). In menus the host has plenty of headroom.

### Gameplay (304 s, normal launch)

| Metric | Value |
|---|---|
| emulating a frame | mean 8.68 ms, p50 < 4 ms, p95 < 21 ms, p99 < 28 ms, longest 106.5 ms |
| frames whose emulation took over 16.7 ms | 6,066 of 18,195 (33%) |
| frames not shown to catch up | 6,520 (36%) |
| showing a frame | mean 0.30 ms, p99 < 2 ms |
| buffer swaps | 0.50 a frame on each screen: the game draws at 30 fps |
| GPU commands | 4.88 command lists, 1.50 display transfers, 1.11 memory fills a frame |
| sound underruns | 3 in 5 minutes |
| interpreted | 0.013% (new code paths, now in the hints) |

## What the baseline says

1. **The game renders at 30 fps, so emulated frames alternate between heavy
   and light.** One vertical blank does all of a frame's rendering work,
   the next one almost nothing: p50 under 4 ms, but a third of frames over
   16.7 ms. Over the two-blank period the average (≈17 ms per 33.4 ms) fits,
   but the frame loop reacted to every heavy blank by skipping the next
   present.
2. **Skipping presents bought nothing.** Showing a frame costs 0.3 ms on
   average, yet 36% of frames went unshown, which can drop exactly the
   frames that carry a new picture and causes visible judder. *Change
   (October 17, `zakuro/src/lib.rs`):* a present is only skipped when the
   previous one cost at least 4 ms (`SKIP_WORTH`). To confirm: frames
   skipped should fall to near zero with no rise in sound underruns.
3. **The CPU side is the cost, not the GPU.** GPU work is well under 1 ms a
   batch. What is not yet split out is how the heavy blank's ~17-21 ms
   divides between the game's own code, the renderer's command processing
   on the CPU (shader setup, texture decode, the CPU geometry shader) and
   kernel scheduling. *Change (October 17):* `usage.txt` now records the
   GPU commands' CPU time per frame and the particle shader's total cost.
   That decides the next optimisation.
4. **Particle effects now cost CPU time.** The geometry shader's particle
   mode (fixed-size primitives) was skipped until October 17. It runs on the
   CPU. The gameplay session above ran the first version, which ran every
   primitive alone on one thread; it is now spread over threads with a
   scalar shader run per primitive. Its cost is in the `particles` line of
   `usage.txt`, and the comparison with the previous executable (which did
   not draw particles at all) tells how much of the heavy blank it is.

## Next measurements

Run the same chapter twice, with this build and with the previous one
(`archive/2026-10-17-runtime-before/zakuro-pc-interface.exe`), with
`--diagnostics`, covering: startup, menu, air battle, land battle, heavy
combat, a boss, a dialogue-heavy section. Record the `usage.txt` lines
"emulating", "gpu cmds", "particles" and "skipped" for each.
