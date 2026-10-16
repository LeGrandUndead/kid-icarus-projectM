# Isolated AI-HD edition

**Retired on October 12 at the user's request.** AI and other texture rework
are disabled. Use `Launch-KIU.cmd` for the original-art 1080p widescreen build.
The 956-texture candidate was generated but never replay-validated or installed.
The 127-texture AI edition is also disabled; its files and saves are retained
for recovery only. The instructions and results below are historical.

Launch with `Launch-KIU-AI-HD.cmd`. Everything used by this edition is under
`build/ai-hd-edition`: its executable, AOT DLL, ROM copy, texture pack,
settings, shader cache, fonts, and copied saves. It shares no writable profile
with the normal or experimental versions. Progress diverges after copying.
The executable is a frozen copy of the experimental runtime, not a different
renderer implementation. Controls, HUD animations and camera logic are retained.

## Artwork method and coverage

The user explicitly approved local pretrained AI upscaling. The pack currently
contains 127 distinct 4x replacements from existing local gameplay captures.
Character drawings are ORIGINAL: eight portrait textures were removed from the
active pack after the user rejected AI character artwork. Their previous AI
versions are stored under `excluded-character-art/` and cannot be loaded.
HUD sources use Real-ESRGAN's anime model; additional environment/model sources
use its general model. Normalized sprite layout and transparency are preserved.
This is reconstruction, not recovered original HD source art. Fine details may
be smoothed or inferred; compare the in-game result before preferring it.

No whole-screen framebuffer images are included. Unmatched textures retain
their originals, and this is NOT complete coverage of the game. Movies,
uncaptured character expressions, other chapters and larger textures are not
automatically remastered. The user reports that stretching is no longer present;
clipped pickups are unconfirmed. Neither is an active reproducible defect in
this texture pass.

The generative-image HUD attempt changed lettering/shapes and is stored only
under `rejected/`. It is not in the playable pack. Portrait image generation
failed. The subsequently upscaled portraits have now also been excluded at
the user's request. The original-art non-AI edition remains unchanged.

## Reproduction and validation

- `tools/recomp/prepare_ai_hd.py`: creates copies and selects local sources.
- `tools/recomp/build_ai_hd_pack.py`: performs local neural inference, validates
  log errors/dimensions/transparency, and writes `textures/pack.json` provenance.
- Tiny textures are edge-padded to at least 32 pixels for NCNN inference and
  cropped to the exact original 4x dimensions afterward. Without that padding,
  the 8-pixel-wide input triggered a Vulkan device-loss error. Final logs must
  contain no errors; an earlier file-existence-only result was not accepted.
- `tools/recomp/validate_ai_hd.py`: isolated 13,030-frame graphics replay.
- `tools/recomp/tests/test_ai_hd_isolation.py`: checks launcher paths and removes
  inherited diagnostic/texture overrides.

AI processing happens offline. No neural model runs during gameplay. Larger
textures still increase upload/VRAM costs; no speedup claim is made.
Sources, models and logs all stay within the isolated folder. Do not run the
pack builder while this edition is running. The two other editions can continue
using their own unchanged files.

To collect additional sources, run `Launch-KIU-AI-HD.cmd --capture`, then press
F8 in an uncovered scene. Captures stay under this edition's `captures/` folder
and require classification before inclusion; never treat a dynamic framebuffer
as a static texture.

## References

- Official upscaler and models: https://github.com/xinntao/Real-ESRGAN
- Official portable release: https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0
- Original artwork reference catalog: https://www.kidicaruswiki.org/wiki/File:Pit_Uprising.png

The web search did not establish a verified ready-to-use full-game HD pack.
No third-party game art was downloaded or substituted. The local source
textures are the visual references for all installed replacements.

## Current artwork policy and completed checks

`art-policy.json` records eight original-only portraits and 127 explicitly
reviewed AI-eligible textures. The launcher rejects excluded portraits and
unreviewed replacement PNGs even if the pack manifest omits them. Rebuilding
filters stale inference inputs too. New captures require art review before
inclusion. The ordinary experimental launcher now loads packs only when an
explicit `--texture-pack` is provided; a leftover `textures/hd` folder cannot
silently replace art.

The revised pack completed 13,030 frames through flight, land and pause with
original character portraits. The bottom-screen portrait at frame 10000 was
visually checked. See `validation-original-portraits/result.json` and
`original-portrait-hd-hud.png` inside the isolated edition. Three isolation/art
policy tests and two launcher profile tests passed. The latter required a
sandbox-free rerun because the sandbox denied renaming the temporary test save.

The earlier 135-texture replay/report describe the superseded all-AI trial.
No stretching or clipped-pickup fix is claimed by this pass. Reopen those issues
only if a new reproducible failure is reported. The shader audit found additional
orthographic passes, but those cannot safely receive a world-camera adjustment
without inspecting the affected draw. No speculative renderer changes were
installed in this pass.

## Stage expansion workflow

`extract_stage_containers.py` and `decode_stage_textures.ps1` read local ROM
stage resources using the installed SPICA decoder. Its vertically flipped
RGBA output is corrected before hashing; ETC1, ETC1A4 and LA4 samples matched
the runtime's captured pixels byte-for-byte. The extraction found 3,018 unique
containers and 4,468 unique encoded textures; 182 containers could not be read
by SPICA and remain original.

`expand_ai_hd.py` uses a hash-locked, visually reviewed candidate list. Of 901
candidates, 45 images were excluded, including normal/data/ambiguous images
and an illustrated enemy card; deduplication leaves 829 additional material textures. Output goes
to `textures-stage-candidate`, without modifying the active pack. Larger
sources use a 2x final scale, keeping every replacement within the runtime's
one-megapixel limit. This trades some sharpness for bounded upload/memory cost.

`validate_ai_hd.py --pack textures-stage-candidate --name validation-stage-expansion`
replays the candidate using disposable saves. `promote_stage_pack.py` verifies
the successful replay, asset hashes and art policy before installation. It
retains the previous textures, source manifest and policy together under
`rollback-before-stage-expansion`. Character drawings remain original.
After promotion, `Launch-KIU-AI-HD.cmd --previous-textures` selects the previous
127-texture pack while retaining this edition's own saves and settings.
