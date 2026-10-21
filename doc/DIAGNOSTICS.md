# Diagnostics

Everything here is off in normal play except the usage report and the
slow-frame log, which cost a clock read per frame.

## Always on

### Usage report

`build/kiu-aot-o2/0004000000030100.usage.txt`, written every minute and on
exit: host time per frame (histograms), the renderer's host time by phase,
why GPU images came back to guest memory, GPU commands, service requests and
kernel calls. See [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md).

### Slow frames (`zakuro::slow_frame`)

Any emulated frame over 25 ms writes one line to the session log
(`build/user-data/gameplay-preview/kiu/zakuro.log`), at most 2,000 a session:

```
frame 41230 took 48.2 ms: renderer 31.0, title and kernel 17.2 | command lists: 30.1, draws: 27.9, hw pipeline lookup: 22.4, pipelines made: 6, pipeline: 22.0 ms
```

- **renderer**: the top-level renderer phases (command lists, display
  transfers, fills, texture copies) on the CPU.
- **title and kernel**: the rest, the game's own code and the emulated OS.
- after the bar, every renderer phase over 1 ms and every counter that moved:
  geometry-shader particle primitives, whole texture decodes (new or changed
  textures), pipelines made on the drawing thread (compiled, or taken from the
  driver's cache) and the time each took.

To find what makes a scene stutter, play it, then read those lines.

## Fast-forward (F3)

In game, or in the Escape menu: frames run back to back, sound off, the game
at its original 30 fps (half the drawing per game step). F3 again, or leaving
the game, restores normal speed and the 60 fps setting. For getting through
sections already beaten.

## Render capture

`launch.py --render-capture` (or `Capture-Grind-Rail.cmd`, which is
`Launch-KIU.cmd --render-capture`) writes to
`build/texture-traces/<date>/`:

- `texture-states.csv`: every texture state used (address, size, format,
  sampler and mip settings), from the start.
- **F8**: starts the capture proper.
  - `capture/draw-NNNN.bin` and `draw-states.csv`: the GPU registers of each
    distinct fragment state drawn from then on;
  - `capture/texture-NNNN.{bin,ppm,rgba}` and `textures.csv`: each texture as
    it is used (encoded bytes and decoded), 256 at most;
  - `capture/frame/`: half a second after F8, two frames draw by draw. For
    each draw, `vertices-NNNN-<texture0>.txt` with the full register file,
    the vertex shader inputs, the shaded vertices (clip position, color,
    texture coordinates) and the triangles. The CPU shades during those two
    frames so every draw can be written out (the game stutters briefly).
    Draws into a screen surface also leave a `draw-*.ppm` picture of it.
- **F5**: depth testing off, to see what hides what.
- **F6**: vertex shaders run on the CPU reference instead of the translated
  GPU shaders, to tell a shader translation fault from the rest.
  (Geometry-shader draws always run on the CPU.)

F5 and F6 are live switches, shown in the top-right corner while on.

Example: the grind rail's dark notches (October 21) were found from one
`vertices-*` file. The rail is a geometry-shader tube emitted as a strip;
the per-triangle winding of the shaded vertices showed every other triangle
reversed, which led to the `setemit` winding bit
([RENDERING_STATUS.md](RENDERING_STATUS.md)).

## Offline

- `KIU_DRAW_FRAME=<n>` with `KIU_DRAW_CAPTURE=<dir>`: the draw-by-draw dump
  for frame n of a replay (the boot example counts frames).
- `KIU_DIAGNOSTIC_IGNORE_DEPTH=1`: F5 from the start.
- `ZAKURO_CPU_SHADERS=1` / `ZAKURO_GPU_SHADERS=1`: F6 from the start, or
  the GPU shading even on an integrated GPU.
- `ZAKURO_NO_QUATERNION_FLIP`, `ZAKURO_SCALED_EFFECTS`, `ZAKURO_KEEP_ALIASED`,
  `ZAKURO_LEGACY_TEXTURE_SAMPLING`, `ZAKURO_STATIC_BLEND`: each turns one
  renderer fix or optimisation off, to compare.
