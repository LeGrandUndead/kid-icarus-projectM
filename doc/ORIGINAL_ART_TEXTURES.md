# Original artwork: non-AI texture experiment

The user clarified on October 11 that the supplied screenshots are from this
project and that Azahar has the same graphical quality. There is no longer an
observed Azahar asset-quality advantage to reproduce. Preserve the original
artwork, fonts, colors, layout and animations. Do not use AI upscaling.

## Candidate available for comparison

Run `Launch-KIU-Original-Art-Test.cmd`. This uses the existing experimental
runtime and its experimental saves, with a separate opt-in texture pack.
Use `Launch-KIU-Experimental.cmd` to return to the previous rendering.
The normal launcher, ROM, AOT library and executable are unchanged.

The pack contains **31 reviewed captured textures**, reconstructed at 4x each
dimension with conventional Lanczos filtering in premultiplied alpha. It has
no trained model, generated artwork, downloaded assets or font substitutions.
The source pixels and replacement identities are validated before processing.
Transparency is processed with the color to avoid dark or colored fringes.
Runtime cubic filtering is disabled for this comparison to avoid combining
two different reconstruction methods. Unmatched textures stay original.

This is **not a complete HD remaster**: enlargement modestly improves edge
definition but cannot recover missing illustration detail. It does not cover
all chapters or assets. Do not advertise it as new high-resolution source art.
The original assets remain in `build/texture-work/sources-20261011`; processed
copies and their provenance/checksums are in
`build/texture-work/original-art-4x-20261011/pack.json`.

Rebuild into a NEW output directory (the tool refuses to overwrite one):

```
python tools/recomp/build_original_art_pack.py build/texture-work/sources-20261011 build/texture-work/original-art-4x-new
```

Do not feed unreviewed framebuffer captures into this tool. A frame image is
not a static texture. The existing exporter requires explicit reviewed IDs.

## Still unresolved

- Truly detailed HD portraits/HUD require higher-resolution original assets
  or faithful manual restoration. None has been verified in this pass.
- The supplied cropped image shows cut-off heart pickups. This is a separate
  suspected rendering defect, not evidence that texture resolution is low.
  Do not claim it is repaired by this pack.
- Remaining intermittent camera stretching needs a reproducible affected
  frame and projection/pass analysis. This texture-only pass changes no camera
  logic and makes no claim to fix it.

The source-level transparency tests cover hidden-color contamination and
constant color/opacity preservation. Replay and visual validation are recorded
in `build/original-art-pack-validation-20261011.json` when complete.
