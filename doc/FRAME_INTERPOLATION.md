# 60 FPS: frame interpolation

> Set aside October 29 (`doc/ROLLBACK_2026-10-29.md`): in-between frames still
> looked like 30 for most of a session, and the 60 Hz logic mode is in use
> again with its white screens fixed ([WARP_WHITE_SCREEN.md](WARP_WHITE_SCREEN.md)).
> The code is in git history (`d1c8774` to `e697423`).

Kid Icarus: Uprising runs at 30 frames a second, so it draws a new picture
every other vertical blank. With **Settings > Graphics > 60 FPS** on, the
renderer shows a picture between each two the game draws, with everything
that moves halfway between them. The game itself is not changed: its logic,
its timers and its memory are exactly as on the console.

## Why not run the game at 60

The first 60 FPS mode (October 18–19, now in `doc/history/60FPS_ANALYSIS.md`)
made the game update every blank with its update step halved. That only works
for the systems that scale by the step. A RAM comparison found 50 counters
that count updates instead. One was corrected and 16 known ones were not, and
any other could fire twice. On October 28 the chapter 9 white screen was
traced to that mode: with it off, the white went away. The mode and its
recompiled override (`tools/recomp/overrides/kiu-60fps.c`) were removed. The
DLL built before then still contains the override. It does nothing at the
original step (it checks for step 1.0), and the next DLL rebuild drops it.

Recent recompilation ports do the same. Zelda64Recomp and the other N64 ports
interpolate in RT64. Wind Waker Recomp (September 2026) raises its 30 FPS base
by interpolation and keeps 60 Hz logic as an experimental trade-off.

## How it works

The work is all in `zakuro-gpu`.

1. **Which uniforms are matrices** (`shader/transforms.rs`). The vertex
   program is read from its entry point. A float uniform counts as a
   transform in these cases:
   - it is an operand of `dp3`, `dp4` or `dph`;
   - it is multiplied by one component of another value repeated
     (`mul r0, c4, v0.xxxx`, `mad r0, v0.yyyy, c5, r0`);
   - it lies in a range read through an address register (bone palettes);
   - it is added to columns applied that way (`add r0, c3, r0`): the
     translation, which compilers add rather than multiply by w = 1.

   A uniform used any other way anywhere in the program is excluded: for
   example an atlas cell offset that is added, an index for `mova`, or a
   colour multiplied component by component. Blending those would sample
   between animation cells or digits.
2. **Which draw is which** (`raster/hardware/interpolate.rs`). A draw is
   recognised by its program, vertex arrays, the addresses of its
   textures (not their contents, which animate) and target buffers.
   Copies of one model take the closest of the previous frame's matching
   draws. Its transform uniforms are blended halfway. These draws are drawn
   as in the new frame instead:
   - unmatched draws (something that just appeared);
   - draws where a matrix row turned more than 60° between the frames.

   A frame where more than a quarter of the matched draws jumped like that
   is a cut, and gets no in-between picture.
3. **The twin world** (`raster/hardware/twin.rs`). Every surface the game
   draws into gets a twin image that only the host uses:
   - **Draws:** each draw is recorded again into the twins, with the blended
     uniforms. Textures drawn this frame come from the twins too.
   - **Other writes:** fills clear both images, uploads are copied across,
     and display transfers run again twin to twin.
   - **Ordering:** the twin draws of a rendering are recorded when it ends,
     so each twin sees its writes in the same order as its surface.
   - **Isolation:** nothing in the twin world is written to guest memory or
     read by the CPU.
4. **Showing it** (`System::gpu_screen`). When a new top-screen picture
   arrives two or more blanks after the last, that blank shows its twin and
   the next blank shows the picture itself. A game drawing every blank
   gets no twin.

The frame boundary is the top screen's buffer swap (`Gpu::set_framebuffer`).

## Costs and limits

- **Latency:** each real picture is shown one blank (16.7 ms) later.
- **GPU work:** about double the work for draws, which is small for 3DS
  scenes.
- **CPU:** recording the second set of draws on the emulation thread.
- **CPU-generated vertices:** some particles and ribbons, whose vertex data
  the game writes each frame, are not blended. They still move at 30.
- **Teleports:** a teleport without rotation is not detected, so the
  in-between picture can show one object halfway for 16 ms.
- **Presenter:** only the direct presenter is supported (the PC interface,
  sharing the Vulkan device).

## Settings and diagnostics

- **Setting:** `%APPDATA%/zakuro/frame-interpolation.txt` holds `1` or `0`
  and defaults to on. `KIU_INTERPOLATION=1/0` overrides it for one run, as
  do `launch.py --sixty-fps / --thirty-fps`. Fast-forward turns it off while
  it runs.
- **Log:** every 600 frames the log sums up the last 600: draws with
  transforms per frame, how many of them were blended, how many jumped,
  how many frames were cuts, and how many twins were reloaded from guest
  memory per frame (a surface whose memory the CPU or another buffer
  changed; its in-between picture is the real one).
- **Refreshes:** every 600 refreshes the log also says how many brought
  a new picture with an in-between one before it, how many a new picture
  the very next refresh (nothing to show between), and how many the same
  picture again; and of the in-between pictures asked for, how many were
  shown, and why not the rest.
- **Report:** with 60 FPS on, three frames in a row are written every 15
  seconds (16 times a session) to `build/diagnostics/interpolation/`:
  every draw, what it was recognised by, whether it matched, jumped or
  blended, all its float uniforms, and the vertex programs. The layout is
  in `raster/hardware/report.rs`.
- **Tests:** `cargo test -p zakuro-gpu --features vulkan` covers the shader
  analysis, the matching, and a draw end to end:
  `the_in_between_frame_draws_a_moving_quad_halfway`. In that test the twin
  picture of a quad moved from -0.4 to +0.4 is identical to the quad drawn
  at 0.
