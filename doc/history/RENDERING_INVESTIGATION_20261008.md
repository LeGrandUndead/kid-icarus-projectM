> Historical investigation log. For the installed build, see [current rendering status](../RENDERING_STATUS.md).

# Rendering work â€” 8 October 2026

The user confirmed the current mouse/control revision works correctly. Preserve it.
The latest linked discussion defers widescreen until the end. Priority is now the
severe fingerprint-like pattern across Chapter 4 surfaces. The user confirmed it
appears in both Vulkan at 1x and the software renderer.

The projected-texture correction below removes the pattern in both saved affected
scenes. The normal launcher uses the rebuilt runtime; no diagnostic flags are
needed. Geometry mode 2 and the reported pause-time crash remain separate issues.

## Installed work

- Internal rendering scales 1â€“8 are available. 5x is 2000x1200, 6x is 2400x1440.
  These preserve 5:3 framing; they are not native 1920x1080 or widened projection.
- The separately installed mipmap/filter/LOD patch is preserved. Its trace records
  7 mip-requesting states out of 227 in the 12:06 session. Loading mipmaps did not
  resolve the reported artifact.
- `--render-capture` adds opt-in F8-triggered capture of fragment registers,
  encoded guest textures, decoded RGB previews, and decoded RGBA bytes.
  Normal launches do not capture anything. F8 does not change gameplay controls.

## Capture instructions for future issues

Double-click `Diagnose-Graphics.cmd`, enter the affected Chapter 4 location, press
F8 once, play briefly, and quit normally. This also records inputs and copies the
initial save so the scene can be replayed without using personal saves in tests.

Find the new session under `build/texture-traces`, with a `capture` subdirectory.
It contains `draw-states.csv`, `draw-NNNN.bin` (512 little-endian GPU registers),
`textures.csv`, `texture-NNNN.bin` (encoded mip chain), `texture-NNNN.ppm`
(base-level RGB), and `texture-NNNN.rgba` (base-level RGBA, top-to-bottom in the
decoder's own row order). Each texture row gives its address, format and dimensions.
`build/input-traces` contains the matching replay and raw mouse trace.

Capture is bounded to 2048 distinct fragment-state keys, 256 texture versions,
and 128 MiB of texture output. It deliberately waits for F8 so boot/menu assets
do not consume the budget. Captured images exclude render-target-backed textures.
Procedural enabled state alone does not prove Texture3 contributes to output;
the saved combiner registers must be inspected too. Texture captures are local
game data and are not intended for public distribution.

Run `python tools/recomp/analyze_render_capture.py <capture-directory>` to make
indexed texture contact sheets and a JSON summary. This does not change the game.

## Investigation boundary

Both renderers showing the artifact points toward shared decoding, shader state,
procedural texturing, or game output; it does not identify a cause by itself.
The ETC tile ordering, channel bit fields, sign and alpha indexing were compared
with Azahar's implementation; no obvious valid-block layout discrepancy was found.
This is a source review, not yet a complete independent decoder comparison.

References inspected:
- https://github.com/azahar-emu/azahar/blob/master/src/video_core/texture/texture_decode.cpp
- https://github.com/azahar-emu/azahar/blob/master/src/video_core/texture/etc1.cpp

Next evidence needed is a capture of the actual affected Chapter 4 scene. Existing
saved replays cover weapons practice, not that location. Inspect whether the raw
decoded textures already contain the pattern before changing renderer behavior.
No artifact fix is claimed by this diagnostic revision.

## Verification of this revision

The rebuilt frontend and replay runner compiled successfully. Two isolated
2200-frame land-practice runs (capture enabled/disabled) completed, with identical
top/bottom PPM hashes and 500 relative-camera publications each. All 172 captured
RGBA files matched their dimensions and RGB previews; all raw register dumps were
2048 bytes. The 273 captured fragment-state keys had procedural texturing disabled.
This observation applies to the practice replay only, not the reported Chapter 4
location. Practice floor/sky decoded textures looked coherent in the contact sheet.

Capture writes large files and can stutter: the test took 54.80 seconds with capture
versus 6.96 seconds without it. Those figures are diagnostic replay times, not a
gameplay FPS benchmark. Normal launches do not enable capture. Input and camera
source fingerprints were unchanged. The combined recoverable source patch is
`tools/recomp/patches/kiu-pc-runtime.patch`; its reverse-apply check passed. The
original controls-only patch remains intact.

Validation record: `build/evaluation/renderer-capture-verified/validation.json`.

Later work: independent host render dimensions, profiling/optimization, PC item
selection, and finally widescreen with projection, culling and HUD validation.

## Chapter 4 recording recovered

The user session `20261007-210723-881238` recorded 15676 input frames. Its
paired F8 capture was empty, but replaying the frozen input/save copy completed
all frames and reproduced the fingerprint artifact across the sky at frame
12000. Evidence is in `build/evaluation/chapter4-recovered`, including
`artifact-reproduced.png`. No repeat user run is needed for this scene.
The recovery capture began at boot and saved 242 texture versions under its output limits; absence of
a Chapter 4 texture in that bounded set must not be interpreted as evidence.
Use a later-start capture when isolating this scene.

## October 8: fingerprint artifact isolated to projected texturing

The new F8 capture `build/texture-traces/20261008-081927-413712` and input
session `20261008-081928-440284` show Chapter 3, Heads of the Hewdraw.
Both recordings reproduce the reported pattern. The user clarified that their
recent lag coincided with a download; the earlier resolution benchmark does not
establish the cause of that reported lag.

Isolation runs retained the pattern with CPU vertex shading, depth rejection
disabled, and before pausing. None of these diagnostic bypasses is a fix.
The new capture's 226 fragment-state keys had procedural texturing disabled.

The decisive evidence is `build/evaluation/artifact-draw-stages-sequenced`:
199 individual draws captured at replay frame 3549, with the final screen
byte-identical to the uncaptured frame 3550. Draw 53 is clean; draw 54 introduces
the fingerprint pattern. Its unit-0 parameter register is `0x30003326`, selecting
projected 2D texturing. The bound ETC1 texture at translated address `0x1F402B00`
is a smooth radial gradient (F8 texture 26), not corrupted cloud artwork.

The renderer discarded output semantic 16 (TEXCOORD0_W) and sampled projected
textures as ordinary 2D textures. The correction carries that value through
output mapping, clipping, perspective interpolation, CPU vertex uploads,
generic GPU shading, and translated GPU shading. Unit 0 in projection mode
divides U and V by the interpolated value before sampling, in both software and
Vulkan. Existing mipmap/LOD work and input/camera code are preserved.

Register/behavior references, used to verify hardware semantics:
- https://github.com/azahar-emu/azahar/blob/master/src/video_core/pica/regs_rasterizer.h
- https://github.com/azahar-emu/azahar/blob/master/src/video_core/renderer_software/sw_rasterizer.cpp

Two new regression tests cover semantic mapping/clipping and sampling with a
varying projective divisor (software and Vulkan). Both pass. The translated
straight-program shader compilation test also passes.

Shader sources and checked-in SPIR-V must be updated together. Use
`tools/recomp/build_gpu_shaders.ps1` before the Rust build when changing these
shaders. It uses the project-local official glslang 16.6.0 Windows x86_64 release:
https://github.com/KhronosGroup/glslang/releases/download/16.6.0/glslang-16.6.0-windows-x86_64-release.zip
Archive SHA-256: `82bf434e69b9bb4829de7e2b4bc2c5e7a7861e53d66cf75e5cc70f5f694a8d9b`.

Geometry-shader mode 2 remains unimplemented and drops those draws; this is a
separate remaining renderer limitation. Audio underrun messages alone do not
prove a pause-time crash cause. No fix for either is claimed by this change.

### Gameplay verification

- `artifact-projection-fixed`: new recording, 3550 frames, Vulkan at 1x; the
  fingerprint pattern is absent. `comparison.png` shows the same frame before
  and after the correction.
- `artifact-projection-cpu-vertices`: same recording and frame with CPU vertex
  shading; the pattern is also absent. CPU/GPU images differ at 369 of 96000
  pixels, so exact equality is not claimed across those paths.
- `artifact-projection-old-scene-3x`: older recording, 12000 frames at 3x,
  1200x720 top-screen output. The paused sky is clean as well.

All three runs completed with isolated save copies and the existing O2 DLL.
Concurrent builds/replays make their timings unsuitable for performance claims.
Input, camera-hook source, and the frozen controls patch match
`build/render-controls-fingerprints.json`. The previous playable executable is
preserved under `build/rendering-before-projection-fix-20261008`.

## October 9: land clarity and optimization follow-up

The user confirms the fingerprint correction looks good. Initial stutters settled
after the first launch, but optimization remains requested. The new land screenshot
was taken through Launch-KIU; saved settings currently select Vulkan hardware
rasterization at 8x. Do not overwrite these preferences. The existing 8x land-practice
replay has sharp geometry, so the screenshot alone does not establish a general
land-resolution problem. Chapter-specific effects, copies, or native-resolution
presentation fallback need an actual affected-scene replay before a correction.

`Capture-Land.cmd` retains the saved resolution (unlike Diagnose-Graphics's 1x
override), records inputs and raw mouse data, and arms F8 texture capture. It also
saves runtime frame/pipeline diagnostics and launch settings with the capture.
The user should enter the blurry land area, press F8, play briefly, then quit
normally. Diagnostic capture overhead is not a normal gameplay benchmark.

A persistent Vulkan pipeline cache already exists and is actively written under
`build/user-data/local/zakuro/pipelines.bin`. This is consistent with startup
stutters settling but does not by itself establish their exact cause. Profile
the affected replay cold/warm and at several scales before changing compilation
or rendering policies. No new optimization or land-quality fix is claimed yet.

The user may continue playing during inspection. CPU/GPU-heavy replay tests and
builds can interfere with gameplay measurements; executable replacement requires
closing the game first. This follow-up changes only capture tooling, not the
working executable, controls, or saved settings.
