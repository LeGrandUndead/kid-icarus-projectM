# KIU renderer texture sampling / LOD phase

Status: experimental renderer-correctness patch. Widescreen is intentionally out of scope.

## Why this phase exists

The current KIU runtime renders the game, but highly minified / oblique surfaces can show strong moire / fingerprint-like aliasing. Before this patch Zakuro's ordinary PICA texture path:

- used PARAM bit 1 (magnification) as the single filter for both magnification and minification;
- ignored PARAM bit 2 (minification filter);
- ignored PARAM bit 24 (mipmap filter);
- ignored the texture LOD bias / min / max range;
- decoded and uploaded only mip level 0;
- created Vulkan images with one mip level and samplers clamped to LOD 0.

That is not faithful to the PICA200 texture-unit state. 3dbrew documents separate magnification, minification and mipmap filtering in `GPUREG_TEXUNITi_PARAM`, plus a signed fixed1.4.8 bias and min/max levels in `GPUREG_TEXUNITi_LOD`. It also documents mipmap data immediately following the base texture. citro3d's texture implementation likewise allocates consecutive levels and halves dimensions/level size for successive mip levels.

References:
- https://3dbrew.org/wiki/GPU/Internal_Registers#Texturing_registers
- https://github.com/devkitPro/citro3d/blob/master/source/texture.c

## What this patch changes

The Vulkan hardware-rasterizer path now:

1. Decodes PICA magnification, minification and mip filters independently.
2. Decodes the signed LOD bias and requested min/max level.
3. Reads consecutive guest mip levels down to the last complete 8x8 tiled level that the existing decoder can safely represent.
4. Caches all decoded levels together.
5. Uploads those levels to a real multi-level Vulkan image.
6. Creates Vulkan samplers using the guest min/mag/mipmap filters and LOD range.
7. Includes mip bytes in the guest-memory read range so GPU-held writes are synchronized before sampling.

It does **not** change controls, camera hooks, internal-resolution scaling, UI, or widescreen.

### Deliberate limits in this first pass

- The software rasterizer still samples level 0 because it does not currently carry texture-coordinate derivatives. The gameplay build uses the Vulkan hardware rasterizer; software LOD can be implemented separately if needed.
- Render-target-backed textures remain single-level because Zakuro only has the rendered base image on the host.
- No resolution-scale LOD compensation is enabled yet. At 3x/4x internal resolution Vulkan's implicit derivatives differ from native 3DS resolution. We first test raw PICA state at 1x and the normal scale, then decide from evidence whether a scale-aware LOD correction is necessary.
- The patch conservatively stops the decoded mip chain at the last complete 8x8 tiled level supported by the current texture decoder.

## Instrumentation and A/B switch

Two launcher options are added:

```powershell
.\Launch-KIU.cmd --texture-trace
.\Launch-KIU.cmd --legacy-texture-sampling --texture-trace
```

`--texture-trace` writes a session under:

```text
build\texture-traces\YYYYMMDD-HHMMSS-ffffff\
    session.json
    texture-states.csv
```

The CSV records unique texture states including PARAM, LOD, separate filter bits, requested and loaded mip ranges, bias, dimensions, format and byte count.

`--legacy-texture-sampling` uses the old base-level behavior from the **same patched runtime**. That gives an A/B comparison without swapping DLLs or source trees.

## Test protocol

Use the same save, scene, camera position and internal resolution for each pair.

### A. Existing behavior

```powershell
cd "D:\Games\Kid icarus"
.\Launch-KIU.cmd --resolution 3 --legacy-texture-sampling --texture-trace
```

Capture one of the Chapter 4 views where floors / stairs / distant walls show the fingerprint pattern.

### B. Corrected PICA sampling

```powershell
.\Launch-KIU.cmd --resolution 3 --texture-trace
```

Return to the same view and capture it again.

### C. Native-resolution control

```powershell
.\Launch-KIU.cmd --resolution 1 --texture-trace
```

This separates PICA mip/LOD correctness from effects caused by supersampling the 3DS framebuffer.

## What to inspect after a run

In `texture-states.csv`, useful rows have any of:

- `requested_max > 0` / `loaded_max > 0`;
- `mip_linear = 1`;
- `min_linear` differing from `mag_linear`;
- a non-zero `lod_bias`.

If the corrected 1x image removes the moire but 3x still looks too sharp/aliased, the next controlled experiment is a host LOD adjustment tied to internal render scale (approximately the log2 of the scale), **not** another texture or post-process blur.

If the corrected build does not materially change the bad surfaces, keep the trace and screenshots: the next investigation moves to shader/post-process/render-target behavior rather than guessing another sampling patch.

## Optional trace summary helper

After a run you can summarize a trace without opening the CSV manually:

```powershell
python .\tools\recomp\analyze_texture_trace.py ".\build\texture-traces\<session>\texture-states.csv"
```

For an A/B comparison, pass both CSV paths in one command. The helper only reads the files.
