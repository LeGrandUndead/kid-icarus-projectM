# PC single-screen architecture

## Authority and boundaries

The game remains authoritative for gameplay, UI state, animation, sound and
saves. Both guest screens continue rendering. This layer only composes host
views and routes input. The separate gameplay preview now experiments with
projection scaling and original portrait draw extraction, described below.
The existing original-art executable remains the fallback.

## Gameplay-first preview (October 14)

Start `Launch-KIU-Gameplay-Preview.cmd`. This has its own
`zakuro-gameplay-preview.exe` and `build/user-data/gameplay-preview` profile.
The normal and earlier single-screen executables are not replaced. F2 captures
the mouse and enables the gameplay portraits; Tab opens the original lower-screen
controls and temporarily hides the portraits; F9 restores the compatibility view.

The preview now defaults to a 0.85 lens scale on recognized world and screen-marker
projections. This exposes about 17.6% more extent on each axis around the center;
it is a wider projection, not a physical camera movement. The original guided
camera, game logic and controls are retained. To compare with the existing view,
run `Launch-KIU-Gameplay-Preview.cmd --camera-scale 1`. Allowed lens scales are
0.75–1. Camera changes are isolated
to this preview. In the runtime Settings > Graphics, **Gameplay view** adjusts
100–133% extent live. Release capture with Escape, then open the runtime menu
with Escape again to access Settings. The value is saved in this preview's
`roaming/zakuro/gameplay-camera.txt`; an explicit `--camera-scale` overrides it
for that launch. The reset button restores 100%.

Verified health and score batches opt out of the lens scaling and retain their
existing widescreen border anchors. Reticle and world markers still follow
the world scale. This classification uses the known shader, projection and
complete batch bounds, rather than treating all 2D draws as fixed HUD.

The portrait adapter recognizes original `FB_*` textures from the ROM's
`us/info` archives and reads their actual bottom-screen draw geometry, UVs,
vertex color and texture-combiner state. It reuses those original draws in small
left/right gameplay portrait regions. Expressions, fades and transforms follow
the game's emitted draws; no speech recognition, invented timing, framebuffer
crop, AI art, or texture replacement is involved. Decoded texture V coordinates
are converted to the host overlay's top-down convention. Original top-screen
subtitles remain in place. The original bottom screen still runs internally.

`prepare_dialogue_sources.ps1` and `prepare_dialogue_sources.py` prepare the local
source fingerprints: 1,809 source references, 139 distinct textures. Assets and
the fingerprint catalog stay under ignored `build/native-ui/dialogue-sources`.
The adapter requires the hardware-rendered game window. Its bounded texture
cache avoids recomputing an unchanged portrait every frame.

### Validation and limits

The isolated Chapter 1 replay completed 4,000 frames and captured both Pit and
Palutena with transparent backgrounds and the expected original transforms.
Evidence: `build/evaluation/native-dialogue-preview-20261014/result.json` and
its `draws/dialogue-*.png/json` files. That replay uses 1× resolution for debugging;
it is not a 1080p performance benchmark. A later V-coordinate correction fixes
host presentation orientation without changing the source captures.
This first recorded result used scale 0.92, before the stronger default and
fixed-HUD exemption were introduced; subsequent validation is recorded separately.

This is a gameplay prototype, not the completed PC interface. Live-window visual
verification could not run because the computer-use JavaScript runtime failed
to initialize (`failed to write kernel assets`). Unit tests and recorded guest
execution do not replace a visual playtest. In particular, review portrait size,
subtitle overlap, screen-edge visibility and aim/marker alignment at 1080p.
All chapters, land scenes, moving portraits crossing the center, three-speaker
sequences, gag artwork, unknown projection shaders and game-side culling still
need coverage. Only recognized portrait draw patterns are extracted; unmatched
draws remain available in the original lower screen. Game pause/menu detection
is not yet a verified semantic signal. Powers/items and native menus remain
future work; online features are excluded.

Pipeline:

```
guest gameplay/UI -> top + bottom GPU images -> PC layout -> host window
guest verified state -> optional read-only semantic snapshots -> future widgets
host events -> presentation/input context -> existing Keyboard + gamepad -> HID
```

## First foundation

`pc_presentation.rs` owns compatibility state and the selection of a GPU layout.
Keep host presentation modes separate from **guest semantic modes**: initially
we know GameplayView (user-selected), BottomOverlay and LegacyDualScreen. Do
not label a guessed screen as Gear/Paused/Air. A future verified snapshot can
choose those policies; until then Tab is explicit and reliable.

Tab toggles the original interactive lower screen as a centered 4:3 panel over
the top view. It is a temporary compatibility tool, not a finished menu or HUD.
The top screen stays visible behind it, with its existing aspect policy. F9
switches between single-screen and legacy stacked presentation for comparison.
Escape/F2 close the panel using existing capture restoration. Focus loss cancels
recapture. Runtime menus/system keyboard remain a separate input owner.

Use one layout function for GPU composition AND pointer hit-testing. A resize,
fullscreen or DPI change must not desynchronize the clickable rectangle.
The overlay adds only a destination rectangle to the existing GPU composition;
no CPU image processing or new framebuffer copies are needed.

Input contexts: GameplayCapture, PointerMenu, LegacyPointer, RuntimeModal.
PointerMenu uses normal original menu keys, not PC movement aliases. Closing a
panel clears keyboard/touch/attack state and restores the existing touch-up
sample and original aim anchor. Key auto-repeat must not revive a key held
across a context change. Controller values still use the existing merge path;
no new controller bindings may steal currently mapped guest actions.

## Later semantic contract (not fabricated data)

Use optional, revision-validated snapshots, stamped with guest frame:

- Scene identity + evidence source (known transition/object, never color guess).
- Dialogue draw layers: original texture identity/UVs, transform, opacity, z-order,
  original event interval; support multiple layers and unknown gag art.
- Powers: original IDs, equipped order, selected index, charges and availability.
- Air special: actual gauge values and original eligibility.
- Carried item and vehicle: actual object/action identity and availability.

An unavailable or stale snapshot is **Unknown**, never zero charges or no
dialogue. Unknown critical UI falls back to the original panel. Native widgets
consume snapshots and submit existing guest actions; they do not own timers,
damage, power rules or inventory. Original touch actions require a verified
screen/state and mapped coordinates; no blind fixed-position taps.

Portrait widgets are first after the foundation, but are gated on draw ownership
and transitions. Full/Compact/Off and safe-area options belong in host settings,
not Nintendo save data. Subtitles require respecting the game's own placement
options and avoiding duplication. Audio stays wholly in the current game path.

## What can be implemented now

No translated-game edits needed for the GPU overlay, legacy fallback, centralized
context decisions, shared hit-testing, diagnostics or current E/1/3 aliases.
Keyboard-request service state already identifies one host modal reliably.

Semantic menu reflow, portrait isolation, power counts and vehicle detection
need further runtime observation. Existing guarded-read infrastructure can help
inspect them, but the working relative camera hook must not be changed merely
to obtain presentation state. No speculative menu detector will ship.

## Rollout and verification

Build a separate `zakuro-single-screen` binary from the same source, gated by
`KIU_SINGLE_SCREEN`. Copy settings/saves only once into a separate PC profile.
Keep `Launch-KIU.cmd` on the unchanged working executable until validation and
user testing establish parity. No texture pack is loaded.

Tests: aspect-preserving rectangles, touch boundaries at several window sizes,
legacy restoration, capture/menu/focus transition invariants, keyboard release
and controller merge regression. Build the explicit binary only. Use copied
saves for recorded gameplay tests. A headless gameplay replay checks renderer/
game behavior but cannot verify desktop cursor-grab feel or a physical gamepad;
report those checks separately rather than claiming them from a replay.

No automatic pause is added when Tab opens: original combat continues. A real
pause/menu presentation must follow verified guest pause state. F1 pauses the
runtime and Enter sends Start; neither alone is reliable proof of guest pause.

## Implemented foundation and validation — October 13, 2026

`Launch-KIU-Single-Screen.cmd` selects the separate `zakuro-single-screen.exe`
and `build/user-data/single-screen-pc` profile. Original textures are retained.
Tab opens/closes an interactive, aspect-preserving original bottom-screen panel
over the top image. F2 retains mouse capture control. F9 switches to the legacy
two-screen composition; its top image retains the existing wide aspect.
Both guest screens remain alive. Hidden bottom-screen host presentation is
skipped, but guest rendering and game logic are not disabled.

Verified: 42 release frontend tests and 5 GPU layout tests passed on October 13.
Two launcher/profile isolation tests passed during the initial implementation.
The separate executable was built. An isolated copy with copied saves booted
and logged bottom-screen access. This is not a completed live click/capture
acceptance test: the test window was no longer open at the final check.
Physical gamepad behavior and chapter-length overlay use remain unverified.

Portrait extraction, semantic powers/items, automatic guest-menu detection and
full-window menu reflow are not implemented. The original panel is the current
compatibility path, not the intended final HUD. Next: establish reliable draw
ownership and dialogue transitions before relocating original portrait layers.

## Native interface direction — October 13 clarification

The user tested the foundation and confirmed that an overlay is insufficient.
Normal play must not require opening a second-screen rectangle. Tab/F9 remain
compatibility tools, not the primary interface. The acceptance target is a
coherent PC menu/gameplay flow with original animated components, sounds,
expressions and feedback. No new artwork or AI restoration is authorized here.

New source evidence: `tools/recomp/audit_native_ui.py` decoded all 65 menu
definitions under the local USA menu archives, covering 53 distinct menu IDs,
with zero parse failures. Output is local, ignored `build/native-ui/catalog`.
These are PSLB definitions inside DARC archives, with original named bodies,
navigation relationships, animation functions, sound references and some menu
dialogue/expression timings. Three synthetic parser/contract tests pass.
This is a menu-resource inventory, not proof of complete gameplay UI coverage.

The Solo hub, for example, explicitly names StartMission, TryMission, Alter,
StockRoom, Equip, Doll and Return. Its buttons have original appearance,
disappearance, focus and unfocused animation functions. These should be kept
as original game-driven components, not replaced by generic rectangular buttons.
Static definitions do not establish current selection, locks, affordability,
availability or live scene identity. Unresolved navigation links are retained
in the catalog for investigation; no input actions are enabled by the catalog.

First complete native slice: title/save selection -> main menu -> Solo hub ->
chapter selection -> return. It must use the whole window intentionally, offer
direct pointer hover/click and keyboard/controller navigation, retain original
transitions/audio, and need no screen-switch shortcut along that verified path.
The next blocking engineering step is correlating named bodies and menu IDs
with their live objects and draw submissions. A serializer's menu-ID conversion
routine is not an active-scene detector. Do not ship automatic switching based
only on loaded resources or framebuffer appearance.

Once those correlations are verified, adapt each body's layout and its matching
input region together while leaving original action/state/animation ownership
in the game. Portrait composition follows the same approach with the actual
dialogue layers; no frame cropping, guessed timers or recreated expressions.
No new playable native-menu build is claimed by this catalog work.

## PC interface layer — October 15

Start `Launch-KIU-PC-Interface.cmd` (`zakuro-pc-interface.exe`). It shares the
gameplay-preview profile; on first use the launcher copies that profile's saves
once to `kiu/user-before-pc-interface`. The October 14 preview executable and
launcher are unchanged. Current state: [PC_SINGLE_SCREEN_STATUS.md](PC_SINGLE_SCREEN_STATUS.md).

Code layout:

```
crates/zakuro-gpu/src/kiu_ui/   (replaces dialogue.rs)
    mod.rs     catalog, per-frame capture, frame commit, overlay meshes, census
    bake.rs    original combiner baked once; linear fades as vertex alpha
    layout.rs  islands, portrait placement, touch-marker exclusion (pure, tested)
    scene.rs   BottomScene evidence: portraits, relocated HUD, menu, pause label
    camera.rs  lens scale (moved unchanged)
    config.rs  host Interface options (kiu-interface.txt)
crates/zakuro-gpu/src/raster/hardware.rs  capture_ui(): the only GPU hook
crates/zakuro/src/pc_presentation.rs     PresentationMode, input contexts,
                                         observe() pause-panel state machine
crates/zakuro/src/lib.rs                 begin/end frame, touch point, follow_scene()
tools/formats/cgfx/cgfx_textures.py      CGFX texture dictionary reader
tools/recomp/prepare_native_ui_sources.py catalog → build/native-ui/ui-sources.tsv
```

Frame contract: `begin_frame` clears the pending set; `capture_ui` counts every
2D draw on the guest lower screen (viewport 240x320) and keeps catalogued ones;
`end_frame` publishes the pending set only if the game drew its lower screen in
that frame, otherwise the previous set stays for up to six frames. This fixes
portrait/HUD flicker when the lower screen is updated less often than the top.

Catalog roles (`ui-sources.tsv`, fingerprint of the encoded ROM bytes, the same
function the renderer uses for `source_hash`; verified against all 29 `FB_*`
identities of chapters a010/g010 in the existing portrait catalog):

| Role | Atlases | Use |
|---|---|---|
| portrait | `FB_*` per chapter | relocated beside the view |
| hud | `common` gc_00, gm_00, gm_02, gm_03, ie_00, mr, tgt, imsg; `multi` all | relocated when inside an island |
| menu | `common` gm_01 | evidence only: pause label |
| decor | `bg`, `gc_01`, chapter `CP_/CI_/BL_/BR_`, `single` results/loading | never relocated |

Islands are original lower-screen regions moved as one unit (layout.rs):
action `[0,150]-[170,240]` → window bottom-left; counters `[196,0]-[320,48]` →
right edge at 19% height, below the game's score. Elements larger than
200x150 (panels, backgrounds) never join an island; the chapter title's center
lies outside both. A HUD draw centered within 3 px of this frame's touch point
and at most 64 px is the stylus marker and is dropped. Island scale is
`0.5 × window height / 240 × HUD size` (2.25 at 1080p).

Pause evidence: a `gm_01` draw whose sampled rectangle is the "Resume" label
(pixels 3–80 × 214–246 of the 256×256 atlas, either V convention, word-sized).
Opening needs that label; closing needs 20 fresh frames with relocated HUD and
no `gm_01` draw at all, so a sub-panel without HUD keeps the panel open. A
panel opened with Tab is never closed automatically. A runtime menu, the
system keyboard, or the option being off prevent automatic opening.

Texture cost: each distinct (texture, combiner, colour) is baked once on the
CPU (≤256×256) and cached (96 entries, textures still on screen are never
freed). Alpha-only fades are detected per combiner on 64 real texels and share
one texture. No framebuffer copies or readbacks were added.

### Validation and open questions (October 15)

Unit tests cover island membership, placement at five window sizes and three
HUD sizes, portrait/island separation, touch-marker exclusion, pause-label
recognition in both V conventions (and rejection of "Retreat", single glyphs
and other atlases), the panel state machine, the fade test with real TEV
register encodings, catalog parsing, and launcher profile isolation.

Not yet observed in a live session: the exact draws of the wing/flight
indicator and carried-item slot, whether the stylus marker samples a HUD atlas,
and pause sub-panel art. Run `Launch-KIU-PC-Interface.cmd --ui-census`, play
Chapter 1 air, land, pause → Options → back, and an item pickup; the CSV answers
each question by atlas, rectangle and island.

### October 15 play-test corrections

Verified live in Chapter 1 (screenshots + censuses `build/native-ui/census/`):

- **Inserts** (`Role::Insert`): `CI_*` gag/cutaway art, `SP_*` special
  pictures and `BL_/BR_*` boss/rival title cards from every `us/info/<stage>`
  (190 identities). Placed on a top-center surface: the whole original lower
  screen mapped to 50% of the view height (`layout::place_insert`), so the
  game's own position and motion are kept. Settings > Interface toggles it.
- **Portraits** stand on `SUBTITLE_TOP` (74% of the view height) at 30% height.
- **Multi-quad draws**: digits and text are batches of quads in one draw; the
  capture now accepts any `kiu_quad_indices` batch up to 64 quads and keeps
  each quad as a layer. Without this the counters showed only their plate.
- **Pause evidence**: `gm_01` also holds the ornate corners of the ordinary
  gameplay frame (census frame 5022), so the atlas alone is not a menu. Only
  the Resume (0–0.3125 × 0.027–0.168), Retreat (0.3125–0.625 × same) and
  Remove Display (0–0.375 × 0.305–0.430) labels count (PICA V; both V
  conventions accepted). Remove Display is the first pause art to appear.
- **View anchoring**: `kiu_ui::overlay_in` places everything relative to the
  top-screen viewport from `zakuro_gpu::layout`, not the window.
- **Camera**: the PC interface stores its own lens value
  (`pc-interface-camera.txt`) and defaults to 1.0; see the status file for why.
