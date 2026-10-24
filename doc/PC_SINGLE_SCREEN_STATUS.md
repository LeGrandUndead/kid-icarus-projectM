# PC single-screen status — October 24, 2026 (top-screen menus)

Current reality of the single-screen work. Read with
[PC_SINGLE_SCREEN_AUDIT.md](PC_SINGLE_SCREEN_AUDIT.md) (what the two screens
contain) and [PC_SINGLE_SCREEN_ARCHITECTURE.md](PC_SINGLE_SCREEN_ARCHITECTURE.md)
(how the layer works). This file is replaced, not appended, when the state
changes.

## Launcher (October 16 cleanup)

One launcher and one build remain:

| Launcher | Executable | Profile (saves/settings) | What it is |
|---|---|---|---|
| `Launch-KIU.cmd` | `zakuro-pc-interface.exe` | `build/user-data/gameplay-preview` (saves backed up once to `kiu/user-before-pc-interface`) | Single-screen PC interface: 1080p, PC controls, portraits, picture inserts, specials/Power Palette/counters, pause panel, HUD rebuilt from the ROM |

The earlier launchers and executables (normal 1080p/experimental, single-screen
prototype, gameplay preview, census, RAM research, capture/diagnostics) were
moved to `archive/2026-10-16-cleanup` on the PC (`MOVED.txt` lists them; move a
file back to restore it) and removed from git (still in history). Their save
profiles under `build/user-data` were not touched. `--ui-census` and
`--ram-snapshots` still work as launcher options.

No other executable, launcher or save was replaced. The game's save format is
untouched; PC options live in the profile's `roaming/zakuro/kiu-interface.txt`
and `pc-interface-camera.txt`.

## Menus answered from the top screen (October 24 experiment)

The user chose to go back to the build before the single-screen menu work
(menus show the upper screen alone; Tab shows the lower screen as a panel;
the in-game pause opens it by itself) and try menus driven from the top
screen instead of pieces of the lower one. The pieces work (save select
composition, `menu_layouts.toml`, menu art pack support in the runtime) is in
history and in the tag `archive/2026-10-24-menus-in-pieces`; the menu art
tools stay in `tools/recomp`.

- **How**: while the game shows one of its out-of-stage menus, PC buttons
  are drawn over the upper picture (`crates/zakuro/src/top_menus.rs`, egui).
  A click does what touching the 3DS lower screen did there: a touch at the
  game's own button, held five frames. The game keeps its selection, sounds,
  animation and rules; its keyboard and controller controls keep working.
- **Recognition**: a screen is known by the menu archive (`us/menu/NNN`)
  whose own art its lower screen draws. The UI catalog lists every archive
  holding each texture (`menus=010,011,030`); art found in one only counts
  (`BottomScene::shows_menu`).
- **So far**: save select (Book I / II / III in the books' colours, Back:
  the first click chooses a book, the second opens it) and the main menu
  (Solo, Together, Vault, Options, Back; StreetPass and AR left out).
  Checked on the PC: choosing and opening a book, Solo into the Solo hall.
- **Mouse**: let go while such a menu is up, taken back once the game's HUD
  is up.
- **Next**: the game's own art on the buttons, the keyboard/controller
  selection shown on them, the save's details on the books, then the Solo
  hall (arrows that turn the game's camera) and the other menus.

## HUD fixes from the October 21 trace

Found with the always-on `zakuro::hud_batch` log and a `--ui-census` run
(doc/DIAGNOSTICS.md):

- **Health bar shrinking when hit**: the bar and score were recognised by
  their exact rest rectangles. A hit shakes them a few pixels and a stage
  start slides them in, so they lost their wide-window anchoring and took
  the gameplay view's zoom (133% view: drawn at 0.75 toward the middle).
  They are now recognised by the atlas rectangle each piece draws and its
  width (`raster::kiu_hud_edge`), wherever the animation puts them.
- **Cut-up pieces beside the item**: islands took single quads by their own
  centre, so the left cap of a screen-wide pickup panel joined the action
  group alone (white bar). A lower-screen draw now joins an island whole or
  not at all (`layout::island_for` takes the draw's bounds).
- **Lines over the orbs**: relocated quads were baked from the whole atlas
  and filtered at PC size into the neighbouring sprite (the white panel
  above the orb tray). Each quad is now baked from its own rectangle
  (`bake::crop`), which also makes bakes smaller.

## HUD layout v2 (October 15 evening, design board "V2")

The user's choice from doc/PC_INTERFACE_DESIGN_DIRECTION.md, implemented in
`kiu_ui/layout.rs` (pure geometry, 18 tests):

- **Action group** (air special orbs / land Power Palette) directly under the
  game's own health bar, top left, indented past the wing.
- **Counters** (intensity, hearts, bank) directly under the score, top right.
- **Portraits** stand on the bottom edge in the corners, at most 27% of the
  view height and 14% of its width each, beside the subtitles instead of over
  them. Speakers from the left half of the original screen go left.
- **Picture inserts** get a picture area on the left (30%-71% of the height,
  up to 34% of the width), between the HUD and the left portrait, so they no
  longer cover the middle of the action.

Checked in play the same evening (Chapter 1 at 2.1, Practice Range): orbs
under the health bar, counters updating under the score, Medusa alone
bottom-left, Palutena and Pit together in both corners with captions
between them, Power Palette with its tray top-left on land. The Medusa NES
insert was not reached in that run; its placement is covered by tests only.
Reminder: these layers only show while the mouse is captured (F2).

## Verified in play (October 15, Chapter 1, intensity 2.0, no hearts bet)

The portrait and insert positions in this section are the earlier v1
layout, replaced by v2 above.

Three live sessions driven on the user's PC with screenshots and two censuses
(`build/native-ui/census/20261015-074420-*`, `-075436-*`):

- **Portraits** stand on the subtitle line (74% of the view height) at both
  sides, so they no longer cover captions (user report of Oct 15).
  Palutena, Pit and Medusa (`FB_110`) all appeared.
- **Picture inserts**: the Chapter 1 NES Medusa screenshot (`CI_000`) and
  its arrow + "Medusa" label (`CI_001`) appear top-center at the original
  moment, with the game's own position and motion.
- **Action island**: air special orbs (one full, one charging) and, on land,
  the Power Palette with its tab, selected-power highlight and charges.
- **Counters island**: intensity, hearts collected and heart bank on their
  original plate, right edge below the score. (First build showed only the
  plate: digits are multi-quad draws; fixed the same morning.)
- **Pause**: Start opens the game's own pause menu as the pointer panel with
  the mouse released; Options inside pause keeps it open (option-bar caps
  are menu evidence); back + Resume closes it and recaptures the mouse.
- **Air special**: E fires it through the game; one orb empties and refills.
- **Powers**: 3 expands the Power Palette and moves the selection; E uses
  the power (charges 10 → 9 seen). Original art, highlight and charges.
- **Stylus ripple** rings no longer leak into the action island.
- All layers are anchored to the game view rectangle, not the window.
- Original view (100%) is now the default for this launcher.

## Wider view, enemy pop-in, aim and damage effects

The October 14 preview's 0.85 lens only widened the projection. The game
still culls enemies, limits the reticle and draws damage/screen effects for
its original frustum, so enemies pop in at the new edges and aim/damage stay
inside the old frame (user report of Oct 15). The PC interface therefore
starts at 100%; Settings > Graphics > Gameplay view still allows up to 133%
with that caveat. A correct wider view needs the game's culling frustum and
touch-aim range widened in game code — the postponed widescreen task.

## Still dual-screen / compatibility path

| Area | Current PC path | Why |
|---|---|---|
| Retreat confirmation | Untraced; if it has no pause label or option bar the panel may close (Tab reopens) | Census needed |
| Failure/continue, rewards, Treasure Hunt, Idol Toss | Menus layout if they draw menu art, otherwise Tab panel | Not traced |
| Carried items, vehicle actions | Original screen | Not yet seen in a census |
| Inserts in other chapters (`CI_*` 71, `SP_*` 45, boss/rival cards `BL/BR` 59) | Catalogued, relocated by the same rule | Only Chapter 1's verified by eye |
| Tutorials (`gc_01` control diagrams) | Original screen | Classified decor |

## Known limitations

- **Lower-screen text is missing from relocated HUD** (e.g. the power-name
  bubble shows empty). The game renders its lower-screen text into a 512x128
  render-target texture on the GPU (census `lower-screen-rejected.csv`,
  "no source hash, drawn=true"); the overlay copies textures from guest
  memory, which never holds it. Fix: let the overlay sample renderer-owned
  GPU images (presenter work), not a per-frame readback.
- **Practice Range**: its own top-screen panels (damage, distance) sit in the
  bottom corners, so the action island overlaps the damage panel there. The
  weapon stats panel at the top also showed no text in that session; compare
  with `Launch-KIU.cmd` before assuming it is new.

- Captured draws must use the 2D layout pipeline (shader signature, one
  texture, normal blending); additive glows would be missing.
- Portrait/HUD layers are hidden while the mouse is released (F2).
- Desktop capture goes black after F11 fullscreen (capture tool limitation;
  the game keeps running). Maximized windows capture fine.
- Online/StreetPass/SpotPass/AR remain unsupported.

## Tests

44 frontend, 17 kiu_ui, 108 GPU (zakuro-gpu alone; 124+ with the frontend's
Vulkan feature) in the Rust crates; the Python tests were retired on October 16. Windows executable
cross-built from the same source (stripped, about 14.8 MB).

## Fallbacks

Tab (lower-screen panel), F9 (original two screens), `--no-native-hud`
(portraits/inserts only), Settings > Interface toggles, and the unchanged
October 14 preview launcher.

## HD HUD from the game's own art (October 15, late; superseded by the October 16 pack below)

User direction: no new art style; the HUD must stay the game's own, "an HD
and PC-ported version of the HUD we have". No redrawing, no AI.

- `build_hud_hd_pack.py` (archived October 16) enlarged the four HUD atlases 4x from
  the user's ROM exports (gm_00 frames/digits/plates, gm_02 ornaments/trays,
  gc_00 wings/orbs/medallions, mr power icons): premultiplied bicubic, then
  the soft edges of flat black/white/empty shapes are narrowed back to about
  one pixel. Shaded areas keep plain interpolation. The pack lives in
  `build/texture-work/hud-hd` (local, never committed).
- The PC launcher passes it as `KIU_HUD_PACK`; only the relocated HUD layers
  use it (`kiu_ui`). `--original-hud-resolution` compares with the original.
- Checked in the Practice Range: the pack loads (`HD texture: ... ->
  1024x1024` for gm_00, gc_00, mr) and the palette/bank draw correctly. A
  short audio hitch happens the first time each atlas is baked.
- Also the game's own top HUD (health bar, score and the other top-screen
  HUD pieces): the main renderer uses the HD atlas only for draws of the
  game's 2D HUD program, with a separate cache entry; every other use of the
  same atlas keeps the original texels. (Giving the atlas to every draw made
  the title demo go black; that path stays off.) Chapter 1 checked: health
  bar, score, orbs, counters, portraits and the Medusa insert all correct,
  no black screen in the title demo.
- No hitch: the HD atlases are decoded in the background at start-up and
  each tinted version is baked off the emulation thread; the original
  resolution is shown for the few frames until it is ready.
- Power names and other lower-screen text: the game writes this text into a
  small buffer first (512x128). When that buffer changes, the renderer copies
  it to the host once (no stall: read when its batch is done), at twice the
  3DS resolution, and kiu_ui shows it like the other layers. Text goes with
  the topmost layer under it: power names in their bubble above the Power
  Palette, the Practice Range weapon card with its own text.

Census findings used for the next step (per-element PC layout): the counters
plate is two gm_00 white scroll blobs tinted pale, with the small digit row
and gc_00 heart/bank medallions plus the purple intensity pill; the land
palette is a gm_00 dark tray, 9-slice white highlight pieces, gc_00 gold
arrows and the small digit row for uses.

## HUD asset quality (October 16)

The HUD packs above are replaced by a hybrid reconstruction per piece
(flat-layer tracing for ornaments, plates and digits; soft enlargement for
shaded, glowing and semi-transparent art; traced outlines with smooth
colours for power icons). Details, checks and tools:
doc/PC_HUD_ASSET_RECONSTRUCTION.md. Output `build/texture-work/hud-pc`,
selected automatically by the PC launcher (`--hud-art original`
to compare). Checked in game in Chapter 1 and the Practice Range.
