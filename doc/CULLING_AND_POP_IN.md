# Enemy pop-in and disappearing objects

Reported: enemies appear suddenly during air sections, and some disappear
when the camera points far enough away, up or down.

## Finding 1: the PC wide view widens drawing, not the game's culling

The PC interface has a camera scale (`kiu_ui/camera.rs`, saved in
`build/user-data/gameplay-preview/roaming/zakuro/pc-interface-camera.txt`).
**On this PC it is saved at 0.7518797, the widest view allowed ("Gameplay view" 133% in Settings).**

A scale below 1 widens the projection by rescaling the projection matrix
in the game's shader uniforms (`raster.rs`, `kiu_wide_shader`,
`scale_kiu_view`). The game itself is not told: it still culls objects,
aims and places screen effects for its original, narrower frustum. So:

- objects that enter the new outer band of the screen are not drawn until
  they cross into the original frustum: they **pop in at the edges**;
- objects leaving the original frustum vanish while still on screen in the
  wider view: they **disappear when the camera turns away**, up or down
  just as left or right.

This is runtime behaviour, not original game behaviour, and it matches both
reports. The code already says so in `camera.rs`; the PC interface starts
at 1.0 (original view) for that reason, but the saved value overrides it.

**Check:** set "Gameplay view" back to 100% (Settings, Graphics: "Reset
gameplay view to 100%", or delete `pc-interface-camera.txt`) and play the same air section. Pop-in that
remains is the game's own.

## Finding 2: particle effects were never drawn

Separate from enemies: until October 17 the renderer skipped every draw
made with the geometry shader's fixed-size primitive mode, which particle
systems use (about 3,200 draws a session). Effects that "appear" now were
missing before, not popping in. Fixed in `raster.rs` (`fixed_primitives`).

## What the original game does

To separate the original game's behaviour into its parts:

| | Question | How to find out |
|---|---|---|
| A | spawn/activation distance | RAM snapshots (`--ram-snapshots`, `ram_snapshot.rs`) of the enemy list as a wave approaches |
| B | simulation lifetime | whether enemies off camera keep updating (positions in the snapshots) |
| C | view-frustum rendering | which draws stop as an enemy leaves the frustum, at scale 1.0 |
| D | encounter scripting | air chapters are on rails: waves are triggered by path position |
| E | sector activation | land chapters: rooms and areas |
| F | despawn | enemy list entries freed |

At scale 1.0, C should match what the player sees exactly (it is the
3DS's own frustum). A, D and E are encounter design: changing them changes
the game, and is not what fixes pop-in at the screen edges.

## The proper fix for the wide view

Done October 29, needing a library rebuild: the game's own camera is
widened, see [WIDE_VIEW.md](WIDE_VIEW.md). The plan as first written:

Make the game's culling use the same wider frustum as the drawing:

1. Find the game's camera field of view (or its projection parameters) in
   memory: the projection matrix the shaders receive is built from it, so
   the value can be located by changing the camera scale and diffing RAM,
   or by tracing which function writes the projection uniforms.
2. Widen that value instead of the shader uniforms. Drawing, culling,
   aiming and screen effects then all follow the same frustum.
3. Only if culling uses a separate, stricter test, patch that test's
   margin through an override.

Until then the honest default is scale 1.0, with the wider view as an
option that says it can pop in.

## Cost

Culling with a wider frustum draws more objects. At 5x on an RTX 3060 the
GPU has a lot of headroom (see [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md));
the CPU side of extra draws is what to watch.
