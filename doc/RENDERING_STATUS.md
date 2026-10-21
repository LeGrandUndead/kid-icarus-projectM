# Rendering status — 9 October 2026

**October 21:**

- *Geometry shader winding.* `setemit` bit 22 asks for the triangle it
  completes to be wound the other way; a shader emitting a strip as a list
  sets it on every other triangle. Both shader interpreters ignored it, so
  face culling dropped the wrong half of such strips. Seen on the grind
  rail (a four-sided tube made by the geometry shader in fixed-primitive
  mode): dark notches at every joint where back faces showed through.
  Fixed in `shader/mod.rs` and `shader/batch.rs` (`wound`).
- *Vertex colors.* The PICA200 takes the absolute value of each vertex
  color and saturates it before interpolation; the renderer clamped after.
  Both the GPU vertex shader and the CPU path now match the hardware.
- *Overlay textures.* The overlay's Vulkan descriptor pool held 256 sets and
  the end of a level showed more, which stopped the presenter
  (`ERROR_OUT_OF_POOL_MEMORY`, the "crash at the end of a level"). Pools are
  now added as needed.
- Diagnostics used for these are in [DIAGNOSTICS.md](DIAGNOSTICS.md).

**October 11:** the experimental build fixes inconsistent HUD width and verified high-resolution pause-menu atlas seams. Original bitmap detail remains unchanged. [Validation and fallback](PC_PRESENTATION.md).

**October 10 experimental update:** `Launch-KIU-Experimental.cmd` provides a separate 1080p/wider-view build and relative flight aiming with the guided camera retained. It uses copied saves and independent settings. HUD asset detail, complete widescreen coverage and menu transitions remain under validation. See [experimental setup and limitations](PC_PRESENTATION.md).

Use `Launch-KIU.cmd`. The current work fixes the land-resolution fallback and
replaces the crude dialogue/menu font. Controls and saved rendering preferences
are unchanged. The earlier projected-texture fix remains installed.

## Land resolution

The affected recording is `build/input-traces/20261009-072852-462179`:
16,068 frames through practice, Chapter 1 flight, the temple corridor and land
combat. Captured launch settings selected Vulkan hardware at 8x.

The main scene surface at `0x1F080000` is sometimes read as a 240x400 texture,
requiring a native-resolution readback of a 256-wide tiled surface. That readback
cleared the GPU surface's dirty flag. Later 256x512 texture reads consequently
decoded the native memory image, even though the high-resolution GPU image was
still valid. The fullscreen composition pass enlarged that native image.

The renderer now retains the scaled image for subsequent compatible texture reads.
It checks the memory shadow and overlapping GPU writes before reuse, so CPU changes
and newer rendering still take precedence. The incompatible 240-wide read itself
continues to require a readback; this does not implement arbitrary GPU retiling.

At the same 3x setting, the corridor character and geometry are visibly sharper.
The courtyard and bridge were also inspected. The flight frame at 10,000 was
byte-identical before/after the resolution correction (before the font change).
Both 16,068-frame replays completed with identical draw/transfer/fill counts and
2,029 relative-camera publications.

Evidence:

- `build/evaluation/land-oct9-baseline-3x`: old behavior.
- `build/evaluation/land-oct9-preserved-3x`: corrected behavior;
  `comparison.png` shows the corridor at the same scale.
- `build/evaluation/land-oct9-open-font-3x`: correction plus replacement font;
  completed 16,068 frames, menu at 1,000 and dialogue at 16,068 inspected.
- `build/evaluation/land-oct9-final-8x`: final renderer, 13,000 frames through
  the corridor at the saved 8x setting, with 3200x1920 top-screen output.
  `land-preview.png` is a downscaled preview. A concurrent release build makes
  this run a correctness check, not a performance benchmark.

## Fonts

Missing shared-font data previously selected a generated ASCII font made from
enlarged 8x8 glyphs. The local runtime now loads the open-source replacement used
by Azahar. See [font source, attribution and recovery](FONT_SOURCE.md).
The font affects dialogue on the main screen as well as bottom-screen menu text.
Game-provided bitmap lettering remains at the resolution of its original assets.

## Performance

A CPU readback-copy experiment produced identical images but no reliable speed
gain (127.45 s baseline, 162.82 s first experimental run, 133.19 s repeat). That
experiment was reverted; its source and replay evidence are retained locally.
The direct RGBA8 GPU-blit candidate also produced identical captured images but
was slower: 160.30 s total, 121.8 s in the GPU subsystem versus the baseline's
127.45 s / 97.9 s. It was also reverted. These are individual runs rather than a
statistical benchmark; neither experiment demonstrated a gain worth shipping.
The tested original copy paths are retained. CPU-write preservation has regression
tests. Both experiment sources are under the October 9 recovery archive.

Performance comparisons use the same recorded inputs, isolated save copy, font,
3x resolution and an identical initial pipeline cache. No live saves are used.
The CPU-copy and GPU-blit captures at frames 1,000, 10,000, 13,000, 15,000 and
16,068 (plus the final screens) exactly match the baseline's hashes. Their
timing and source/runtime fingerprints are in `build/evaluation/land-oct9-copy-*`
and `land-oct9-blit-*`. No general speedup or stutter elimination is claimed.

The correctness fix performs real high-resolution work that the old land path
skipped. It is not itself an FPS optimization. Earlier concurrent-build replay
timings are unsuitable for performance claims. Pipeline caching already exists;
the cache in `build/user-data/local/zakuro/pipelines.bin` is preserved.

## Resolution and remaining limits

Internal scales 1–8 are available: 3x is 1200x720, 5x is 2000x1200,
6x is 2400x1440 and 8x is 3200x1920 for the top screen. These preserve the
original 5:3 camera framing. True widescreen and HUD reconstruction remain future
work. Higher render resolution sharpens geometry; it cannot add detail absent
from the original textures, videos or bitmap UI.

The projected-texture correction removes the earlier fingerprint-like pattern
in the tested scenes. Geometry shader mode 2 is still unimplemented and drops
those draws. The reported pause-time crash has not been reproduced or fixed;
an audio-underrun warning alone did not establish its cause.

## Capturing another affected scene

Use `Capture-Land.cmd`, reach the problem area, press F8 once, play briefly, then
quit normally. This retains the saved resolution and records inputs, the initial
save snapshot, GPU state and launch settings. `Diagnose-Graphics.cmd` instead
forces 1x and is for separating scaling problems from other rendering problems.
Capture overhead can cause stutters; evaluate normal play through `Launch-KIU`.

Current source is in `tools/zakuro`, with the combined changes preserved in
`tools/recomp/patches/kiu-pc-runtime.patch`. The executable from before this land
fix is kept in `build/rendering-before-land-fix-20261009`. Earlier investigation
details are in [the historical log](history/RENDERING_INVESTIGATION_20261008.md).
The next milestone is [controls and bottom-screen functionality](ROADMAP.md).

## Later October 9 presentation pass

`Launch-KIU-1080p.cmd` adds a separate 5x profile and 1920x1080 window.
Tab exposes the bottom-screen cursor and restores the prior view/aim afterward.
The renderer and world-camera projection are unchanged: 1800x1080 active view
with side bars at 1080p. See [PC presentation](PC_PRESENTATION.md).


October 11 original-art pass: experimental launcher now defaults to cubic
magnification reconstruction (revert with `--texture-filter original`). Original
art and HUD animations are retained. Verified additional perspective programs
and the 1.6656 transition aspect now receive the wider-camera correction.
Health/score components are aligned to screen corners, including variable
health fills. Full 13,030-frame 5x replay passed. Details, evidence, optional
texture-pack support and limitations are in PC_PRESENTATION.md.
