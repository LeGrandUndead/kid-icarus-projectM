# PC presentation: 1080p profile and bottom-screen access

Run `Launch-KIU-1080p.cmd` for a 1920x1080 client window and top-screen view.
Press F11 for fullscreen on the current monitor, or to return to the window.
Fullscreen uses the monitor's existing resolution; it does not change Windows
resolution. Window borders may extend outside a 1080p desktop until fullscreen.

The profile starts with 5x internal rendering (2000x1200 top-screen geometry).
This is real high-resolution rasterization, then downsampling to the displayed
view. At 1920x1080 the unchanged 5:3 camera occupies 1800x1080, with 60-pixel
bars on each side. It is NOT a completed 16:9 camera/widescreen implementation.
Textures, videos and bitmap UI still have their original detail.

## Screen and menu access

- Tab opens the bottom screen at a readable size and exposes a clickable cursor.
- Click the game's menu controls normally. No manual F2 sequence is needed.
- Tab returns to the prior layout and restores mouse aim if it was captured.
- Escape or F2 also returns from this temporary bottom-screen view.
- F9 cycles normal layouts; F10 switches top-only and bottom-only views.

Tab changes the view; it does not open/close the game's own pause menu or pause
combat. Use the game's normal menu/Start controls when necessary. Internally,
mouse capture is suspended for clicking and restored automatically. The prior
aim anchor is preserved, old buttons/movement are cleared, and one touch-up
sample separates the last menu click from resumed aiming. Losing window focus
cancels automatic recapture; use F2 after returning if needed.

The screen switch is also available through the normal launcher. Flight/land
camera calculations, dash behavior, powers and jump mechanics are unchanged.

## Reversibility

Use `Launch-KIU.cmd` to return to the original presentation. The new profile has
its own settings and pipeline cache in `build/user-data/presentation-1080p`.
It initially copies existing bindings and defaults to 5x; subsequent profile
settings remain independent. Both launchers use the same normal saves. Never run
two live game instances against those saves simultaneously.

For a complete source/binary rollback of this pass, the pre-change files are in
`build/presentation-before-20261009`, preserving their project-relative paths.
Close the game before restoring binaries. The ROM, native game DLL and personal
saves were not patched. `--display original` also bypasses the new profile.

## Separate experimental build — October 10

Run `Launch-KIU-Experimental.cmd`. This selects `zakuro-experimental.exe`,
starts a physical 1920x1080 window, and defaults its own profile to 5x internal
rendering. F11 fills the current monitor; Tab visits the bottom screen and
returns to aiming. Keep the top-only layout for the widescreen experiment.
Other combined layouts still use the original display proportions.

The world is rasterized at 2000x1200 with an adjusted horizontal projection,
then presented at 1920x1080. This exposes 16/15 as much horizontal world with
unchanged vertical FOV in the recognized world shader; it is not simply a
stretched original camera image. It is also not yet an arbitrary-size native
render-target architecture. The bottom screen retains its original aspect.

Flight uses a guarded hook at the game's relative aiming consumer, keeping
its guided camera. Raw mouse deltas can continue at the touchscreen boundary.
The hook preserves visible touch coordinates for UI use. During a Tab visit,
it submits zero aiming motion while the pointer operates the bottom screen.
This does not mean simultaneous aiming and clicking: capture is temporarily
suspended. Menu transitions and subjective flight sensitivity need playtesting.
Land movement, dash and free-jump mechanics were not redesigned in this pass.

### Isolation and fallback

The experimental profile is `build/user-data/experimental-pc`. On first launch
it copies your normal saves into its own `kiu/user`, copies the shared font,
and copies settings and the existing compatible pipeline cache. Subsequent
launches retain experimental progress. **Progress does not automatically merge
back into the normal save.** Close the normal game before that initial copy.

Return to `Launch-KIU.cmd` for the normal executable and normal saves. The
stable executable is also backed up in `build/experimental-before-20261010`.
For comparison within the experimental build:

```powershell
./Launch-KIU-Experimental.cmd --original-aspect
./Launch-KIU-Experimental.cmd --original-flight-aim
./Launch-KIU-Experimental.cmd --original-aspect --original-flight-aim
```

### Verified and remaining work

- Paired 13,300-frame recorded runs completed at 5x through flight and land.
  `build/widescreen-comparison-20261010.png` shows the wider view at equal
  displayed height. The recognized HUD shader is adjusted to preserve its
  proportions, but not all HUD/effect passes have been identified.
- Paired 9,300-frame flight runs held touch at x=319 and reversed mouse motion.
  Experimental aiming responds to the reversal; the baseline remains bounded.
  Evidence: `build/air-edge-comparison-20261010.png`.
- The game still has its own reticle limits. This does not unlock free-look.
- CPU-side world culling is unchanged. Edge popping, unknown shaders, cutscenes,
  videos and unusual screen effects need chapter-by-chapter checks.
- Unit checks cover projection guards, layout, input-hook mode guards, and
  independent save/settings profiles. The automated replays do not exercise
  desktop Tab/F11 interaction or establish human control feel.
- These concurrent replay runs are correctness checks, not performance
  benchmarks. No overall speedup is claimed.

### HUD clarity

Captured score digits, icons and menu lettering occupy small original bitmap
atlases (often 256x256); sampled HUD draws already use linear filtering. The
high-resolution world fix cannot reconstruct missing artwork detail. The
existing shared-font correction remains available for font-backed text, but
this build does not include replacement HD HUD art or an HD texture pack.
See `build/hud-source-atlases-20261010.png`. Replacing selected assets or
rebuilding HUD elements remains separate work; no global blur filter is applied.

The reproducible runtime patch is
`tools/recomp/patches/kiu-pc-runtime.patch` (the older experimental patch was
retired in the October 16 cleanup; git history keeps it). It targets the runtime's recorded upstream HEAD, not an already
patched checkout. The launcher and documentation remain in the project root.

### Rebuild only the experimental executable

```powershell
. ./tools/recomp/environment.ps1
cargo build --release --locked --manifest-path tools/zakuro/Cargo.toml -p zakuro --bin zakuro-experimental
```

Use the explicit binary target above to leave the normal executable untouched.

## October 10 HUD aspect follow-up

The user reported changing HUD width between gameplay, scripted camera shots
and pause. Per-draw captures found three full shader-memory fingerprints with
**identical translated HUD code**: `19037D7C6A2EE397`, `D560F8C55DEA1D51`, and
`9634A5E2DC28AE2F`. Their translated source SHA-256 is
`9b52a1207ab289c669d7083dc920a186e20edf68ea38170db18358e090f112ed`.
The original widescreen allowlist recognized only the first fingerprint.

The experimental renderer now identifies this exact straight-line shader by
executed instruction words through END and the operand descriptors they use.
Unused program/descriptor memory no longer changes recognition. Branching or
unknown shaders are rejected, and the existing top-screen viewport and matrix
guards remain. Fullscreen scene-copy passes and bottom-screen draws remain
excluded. This corrects the verified HUD-width inconsistency; it does not
establish support for every cinematic camera or unknown world shader.

Evidence folders: `wide-cinematic-audit-20261010`,
`wide-hud-land-audit-20261010`, `wide-hud-key-20261010`, and
`wide-hud-fixed-5x-20261010` under `build/evaluation`.
The previous experimental executable and patch are preserved in
`build/widescreen-hud-before-20261010`. No input changes were made in this pass.
The original bitmap art remains unchanged; this is not an HD HUD asset pack.

## October 11: high-resolution HUD atlas sampling

The pause-button seams reproduce at 5x but disappear at native resolution.
The recorded Resume/Retreat quads meet exactly at y=83; both halves reference
an atlas edge at v=110/256. High-resolution linear samples approach that edge
more closely than native pixel centers and blend the neighboring atlas region.
The Options border uses similar adjacent atlas slices. Vertex evidence is in
`build/evaluation/hud-vertices-20261011/draws/vertices-0103.txt` through
`vertices-0110.txt`.

The experimental GPU path now carries each eligible quad's UV bounds to the
fragment shader and clamps sampling to that rectangle's outer texel centers.
Zero-width/height strips retain their original constant coordinate. Eligibility
requires the verified HUD shader and the observed independent-quad index order;
unknown geometry is left alone. The same bounds are available to translated
and generic GPU vertex shading. At native scale, with CPU vertex shading, or
outside the experimental launcher, this additional correction is disabled.
It does not replace the bitmap assets or apply a global texture blur/sharpen.

For an A/B comparison, run:

```powershell
./Launch-KIU-Experimental.cmd --original-hud-sampling
```

This disables only the atlas correction, preserving the HUD aspect fix, wider
world projection and flight controls. The normal launcher clears the experiment
flag. The corrected build retains the existing separate experimental saves.

Validation: the 13,030-frame 5x replay completed through practice, Chapter 1
flight, land and an inserted pause. The paired pause images show removal of
the horizontal Resume/Retreat seams and the Options border seams. Two shader/
quad guard tests and two launcher profile/fallback tests passed. Generic shader
SPIR-V compilation passed; the translated shader path ran in the replay.
The normal executable still matches its preserved hash. This concurrent run
is not a performance benchmark. See `build/hud-atlas-validation-20261011.json`
and `build/hud-atlas-pause-comparison-20261011.png`.


## October 11: original-art clarity, HUD anchors and more projection paths

Artwork preservation is the user's requirement: do not redraw menus, replace
fonts with a different design, or change the original HUD animations.
The local Azahar configuration and October 10 log show 4x rendering,
GameControlled texture sampling, NoFilter, and custom_textures=false. There
is no enabled HD pack to import from that profile. The user subsequently confirmed Azahar looks the same; an asset-quality
advantage there is no longer claimed. See ORIGINAL_ART_TEXTURES.md for the
separate non-AI reconstruction candidate.

The experimental candidate adds `--texture-filter cubic` (default). This is
Catmull-Rom reconstruction of the original pixels during magnification, with
nine bilinear samples. It does not create new artwork or recover lost detail.
Minification, guest mip rules, deliberate nearest-neighbor textures and live
render-target textures retain their existing sampling. HUD taps stay within
verified atlas regions. Use `--texture-filter original` for direct comparison.
Its performance and visual checks are recorded with the candidate validation.

The full replay identified additional perspective programs:
`FD02797C12EA5C7C` projects through rows 86..89; `67A1295922939A3A` and
`798D4FC813C0B966` use rows 0..3 and translate to identical program bodies.
These now share the 15/16 horizontal correction, guarded by their exact
identities, the top viewport and a finite perspective matrix near 5:3.
A recorded 1.6656 aspect transition is accepted (previous tolerance rejected
it). Orthographic screen-copy passes and bottom rendering are excluded.
Evidence: `build/evaluation/wide-projection-code-audit-20261011`.
This does not certify every chapter or cinematic shader.

Health/score corner pieces are anchored by verified complete draw bounds,
including the variable-width health fill, after recognizing the HUD shader
and corrected top-screen matrix. Their vertices receive a constant horizontal
translation; UVs, colors and the game's animation transforms are preserved.
Flight draw bounds were verified separately from the paused HUD, because the
game batches those two states differently.

Optional replacement PNG support is also present for future faithful HD packs:
`Launch-KIU-Experimental.cmd --texture-pack <folder>`. Files are named
`WIDTHxHEIGHT-HASH.png`, where HASH is the runtime fingerprint of decoded
base-level RGBA bytes, not a guest memory address. `export_texture_sources.py`
exports selected local captured assets with these names. PNGs must use matching
2x/4x/8x dimensions, with a one-megapixel upload limit; render-target textures are never replaced. Alpha-aware
mipmaps are generated during upload. Replacements are discovered at startup;
restart to change them. No actual HD artwork pack is installed by this pass.
The colored image in `build/texture-work/upload-test` is an isolated test
fixture only and must never be enabled in a normal game session.

The pre-pass executable and patch are in `build/panels-before-20261011`.
Normal saves and the normal executable are separate from these experiments.


Validation for this pass: the 13,030-frame 5x original-art replay completed,
covering practice, flight, land and pause. Screens were visually checked for
corner alignment, artwork preservation and atlas seams. Three targeted GPU
regressions and two launcher/profile tests passed. A 4x synthetic replacement
was verified in an isolated replay; it is not part of the installed artwork.
See `build/original-art-validation-20261011.json` and
`build/original-art-scenes-20261011.png`. Timings from runs concurrent with
compilation are not claimed as performance benchmarks. Some low-resolution
bitmap detail remains visible; this pass does not claim a fully remastered
HD asset library or coverage of every camera in every chapter.
