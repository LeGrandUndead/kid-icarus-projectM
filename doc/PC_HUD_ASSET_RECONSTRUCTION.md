# PC HUD asset reconstruction (October 16)

Goal: the game's own HUD, from the user's ROM, clean at PC resolutions. No
redrawing, no "similar" art, no learned upscaler. Every shape and colour
comes from the source pixels; the generated images stay on the user's
machine and are never committed.

## Source assets

The relocated PC HUD and the game's top HUD draw from four 256x256 atlases
(runtime names `256x256-<fingerprint>.png`, exported from the ROM by
`export_texture_sources.py`; fingerprints in `tools/recomp/hud_asset_groups.json`):

| Atlas | Content | Format observed |
|---|---|---|
| gm_00 `D61A7866121DF76F` | health frame, score plate, 4 digit sets, plates, buttons, prompts | 16 opacity levels (4-bit), greys only, 156 colours |
| gm_02 `2303D42752AFD91E` | Power Palette tray and black flourish, bubbles, panels, arrows | 4-bit, greys only |
| gc_00 `1033DFD830565E9A` | wings, item icons, orb, medallions, arrows, gauges | 4-bit opacity, full colour |
| mr `260C607B8981C6F8` | power icons, an 8x8 grid of 32x32 cells | opacity 0/238/255 only (hard edges) |

Straight (not premultiplied) alpha. The game tints the grey pieces with its
texture combiner (the PC overlay bakes that tint), so greys stay grey here.
Many pieces are stacks of flat layers: the score plate is a 9/15-opacity
black plate, the letters' black outline and their white fill; digits are a
white fill in a black outline; the health frame is one 8/15-opacity layer.

## Method per piece (`tools/recomp/hud_reconstruct.py`)

Each atlas is cut into pieces (connected shapes; `mr` into its cells). Each
piece is measured, gets a first-choice method, and is checked.

- **flat** - hard-edged ornaments, plates, digits, glyphs (categories A, D).
  The piece is described as a stack of up to four flat layers (exact colour
  + opacity plateaus), ordered outside-in. Every source pixel is decomposed
  into the coverage of each layer. Opaque layers with hard edges: coverage
  enlarged, cut at half, outline traced with potrace into curves, drawn
  anti-aliased at 4x. Semi-transparent layers and layers with soft edges
  (health frame, score tendrils, faint strokes; measured, threshold 1.5
  partial pixels per edge pixel): coverage enlarged smoothly, not traced.
  Each layer is redrawn with the source's own colour and opacity, so line
  weight, holes and asymmetry stay the source's (layer areas match within
  about 1%).
- **paint** - flat-colour art (most power icons): the few exact colours of
  the piece are found, every pixel is split between the one or two colours
  it holds, each colour area is traced and painted with its exact colour.
  The symbols inside the icons get clean edges. Refused when more than 5%
  of the pixels are not a mix of two palette colours (glows, gradients).
- **ink** - cartoon art with a dark neutral outline (wings, skulls, item
  icons, some gm_02 pieces): the dark outline and lines are traced as one
  layer over the smoothly enlarged colours, the silhouette is traced too.
  Refused when the dark parts are coloured shading (the orb).
- **icon** - other coloured art with a hard alpha edge. Colours:
  Lanczos on colour bled under transparent pixels (no dark or white fringe).
  Alpha: traced like a flat layer. Inner detail is not invented.
- **soft** - shaded, glowing or soft-rimmed art (wings, item icons, orb,
  gradients) and anything that fails the checks (categories B, C). Colour
  and alpha enlarged separately (Lanczos, colour bled), nothing sharpened.

Checks per piece, at source size (result shrunk back by area averaging):
mean premultiplied difference, silhouette overlap (IoU) and the difference
away from edges (interior). A sharp method must stay within 1.25x the plain
enlargement's difference (or 0.01), keep IoU >= 0.85 (flat) / 0.9 (icon) and
not flatten interior detail; otherwise it falls back flat -> icon -> soft.
Fallback order: flat -> paint -> ink -> icon -> soft. Semi-transparent
layers (health frame, score tendrils) are traced, then given back their
measured soft falloff. Every decision and number is in the manifest.

Rejected along the way (comparison sheets): tracing everything (health frame
and score tendrils become black blobs, icons lose their transparent cell
corners), single-layer tracing of the score plate (letters lose their
outline), tracing soft-rimmed wings (hard dark contour appears).

Current result (USA ROM): gm_00 58 flat / 7 ink / 31 soft; gm_02 58 flat /
28 ink / 1 icon / 7 soft; gc_00 4 paint / 9 ink / 17 icon / 24 soft; mr 53
paint / 9 ink.

## Tools and outputs

- `python tools/recomp/build_hud_pc_pack.py <exported atlases>` -> 
  `build/texture-work/hud-pc/` (4x atlases, `hud_asset_manifest.json`,
  `validation.json`). Validation: size is 4x, empty source areas stay empty,
  not more opaque than the source, whole-atlas difference <= 0.05,
  deterministic (two runs, same hash). Nothing is installed if it fails.
  Needs `pip install potracer opencv-python pillow numpy`; about 8 s.
- `python tools/recomp/hud_compare.py <sources> <out> Label=<pack> ...` ->
  comparison sheets per group (health bar, score, digits, Power Palette
  ornaments, buttons, wings, orbs, power icons, item icons, UI ornaments):
  1:1 source and 1080p size on checkerboard, dark and light. Local only.
- Tests: `python -m unittest tests.test_hud_reconstruct` (synthetic shapes).

## Runtime

Same atlas layout and UVs at 4x (1024x1024, inside the runtime's 1-megapixel
limit), so no placement code changes. The PC launcher passes the pack as
`KIU_HUD_PACK`; it is used only by HUD draws (the relocated lower-screen HUD
and the game's 2D HUD program on the top screen), decoded in the background
at start-up, so the runtime cost is a normal texture load. One 4x master;
the GPU's linear filtering scales it to 720p..4K (at 4K the HUD is about
4.5x the 3DS size, so 4x masters are slightly magnified there).

Development comparison: `--hud-art pc` (default; falls back to `hud-hd`),
`--hud-art previous` (earlier plain HD pack), `--hud-art original` (also
`--original-hud-resolution`).

## Limits

- No detail is added: the wings, orb and item icons look like the source
  enlarged smoothly, because that is all the source holds.
- Traced edges move by a fraction of a source pixel; tiny glyphs lose a
  little silhouette overlap (IoU 0.85-0.95) while looking cleaner.
- Checked in Chapter 1 (October 16): health bar, wing, score, counters and
  orbs draw correctly with the pack. The orb stays soft (it is shading).
- An SDF/vector runtime path was not needed: 4x masters are visually
  identical at the sizes the HUD is shown.

## Display-size baking and crisper soft layers (October 16)

- The overlay has no mipmaps, so a 4x HUD atlas drawn at about 2.25x was
  minified with plain bilinear filtering (shimmer and slight softness).
  HD atlases are now baked down with area averaging to the density the HUD
  is shown at (window height and HUD size, quarter steps), off the
  emulation thread; resizing the window re-bakes.
- Semi-transparent layers whose soft edge is only the 3DS's anti-aliasing
  (health frame, score tendrils; edge softness up to 2.0) are traced and
  kept crisp; only real glows and shadows keep a soft falloff.
- Text drawn on a picture panel fades with that panel only (the power-name
  bubble no longer disappears with the Practice Range card).
