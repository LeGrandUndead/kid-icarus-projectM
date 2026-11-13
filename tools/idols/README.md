# Idols: the 3D art and the main menu's scene pack

Kid Icarus: Uprising ships a posed 3D figure, an *idol*, for almost every
character (`RomFS/us/doll/NNN/doll`), cutscene models with higher detail
(`RomFS/us/demo/NNN/demo`), the stages (`RomFS/us/stage`) and the menus'
own art. These tools turn the player's own extracted ROM into the pictures
the PC version's main menu plays (tools/zakuro/crates/zakuro/src/pc_menus).

Nothing here contains game data, and nothing they make is committed: every
script reads and writes a work folder on the player's machine
(`IDOLS_WORK`, default `work/`).

## The pipeline

```text
ROM (extracted)
 ├─ convert/  (dump: SPICA-based)  models, skeletons, animations, textures ─┐
 ├─ stg/stack.py                    a stage as one model ──────────────────┤
 ├─ cutscenes/                      cutscene characters, heads on bodies ──┤
 │                                                                         ▼
 │                          render/  (idol.py + pica.py: the 3DS GPU's shading)
 │                            solo_loop.py      Pit's glide loop       ─┐
 │                            poster_frames.py  Pit and Dark Pit       │ frames with
 │                            promo.py + rig.py Palutena, Viridi       │ relighting buffers
 │                            stage_backgrounds.py  the stages         ─┤
 ├─ menu art (4x texture pack, ui-sources.tsv) ────────────────────────┤
 └─ effect files (particles) ──────────────────────────────────────────┤
                                                                        ▼
                         menu_pack/  python3 -m menu_pack <out>   the scene pack
                                                                        ▼
                     build/texture-work/menu-pc/scene-040 on the PC → the game
```

| Step | Script | Makes (in the work folder) | Used by |
|---|---|---|---|
| models | `convert/` (`dump <bcres> <out> [anim] [skin]`) | `idols/out<KEY>/` geometry, materials, animations; `idols/tex<KEY>/` textures | the renderer |
| stages | `stg/stack.py <stage> <KEY>` | a stage's sections stacked into one model | `render/stage_view.py` |
| cutscene characters | `cutscenes/cut.py`, `merge.py` | cutscene models with their heads | `render/cast.py`, `sky.py` |
| Pit | `render/solo_loop.py` (timeline from `sky.py`) | `render/frames/solo_loop_buf/` | menu_pack (Solo) |
| Pit's size reference | `render/pit_poster.py` | `render/frames/poster_solo/` | menu_pack (Solo's framing) |
| Pit and Dark Pit | `render/cast.py together` (timeline), then `render/poster_frames.py` | `render/frames/poster_tog_buf/` | menu_pack (Together) |
| Palutena, Viridi | `render/promo.py P02`, `promo.py V12` (with `rig.py`) | `render/frames/promo_P02_buf/`, `promo_V12_buf/` | menu_pack (Vault, Options) |
| stages | `render/stage_backgrounds.py` | `redraw/bg/<mode>.png` | menu_pack (stages) |
| the pack | `python3 -m menu_pack <out> [--modes 0123]` | every layer, the character frames, `char_M.pak`, `manifest.toml` | the game |

Frames are rendered with *relighting buffers* (`idol.BUFS`): the colour
before shading (`_base.png`) and the surface normals (`_nrm.png`), so
`menu_pack/relight.py` can light each character for its stage when the
pack is built.

## Folders

- `convert/`: a small .NET tool on top of SPICA (public domain,
  github.com/gdkchan/SPICA) that writes a CGFX model as plain data: posed
  triangles, materials (`materials.json`, `luts.json`, `lights.json`),
  texture slots with their wrap modes, the textures, every frame of an
  animation skinned (`Animate.cs`), and with `skin` the skeleton and skin
  for posing (`skeleton.txt`, `skin.bin`; `LOCALS=1` writes each
  animation's per-bone local transforms).
- `stg/`: stages as one model.
- `cutscenes/`: cutscene characters (`cut.py` lists those used), heads
  joined onto bodies (`merge.py`), material re-exports (`matfix.py`),
  removing meshes (`dropmesh.py`).
- `catalog/`: every animation we can play, as labelled looping grids
  (`build.py`, `render.py`, `compose.py`).
- `render/`: the renderer (`idol.py`, `pica.py`, `post_shade.py`), the
  posing rig (`rig.py`), the scripts that render the menu's frames (above),
  `books.py` (the save select's 3D books), `sheet.py` (a pose sheet of a
  cutscene, to pick moments).
- `menu_pack/`: the scene pack builder (its `__init__.py` lists its parts).
- `archive/`: the menu mock-ups and their renders, kept for history.

## Rebuilding the pack

From `tools/idols`, with `IDOLS_WORK` set:

1. Render what changed, from the work folder's `render/` (it holds
   `frames/` and links to the scripts in `render/` here): for example
   `cd $IDOLS_WORK/render && python3 promo.py P02`. Each script skips frames
   that already exist: move the old ones aside after a model change.
2. `python3 -m menu_pack <out>`: frames already in `<out>` are kept, the
   rest are built, then the packs and the manifest are written.
3. Copy `<out>` (without the `.at` files) to the PC's
   `build/texture-work/menu-pc/scene-040`, after moving the old folder to
   `archive/`.

## Technical notes

### Game shading

The renderer shades each mesh as the 3DS GPU does, from the model's own
material (`render/pica.py`, after SPICA.Rendering's shader generator):
texture coordinates per unit (UV sets, sphere reflection maps), vertex
colour with the hemisphere light, fragment lighting with the material's
look-up tables (distribution, Fresnel, reflection; output scale; absolute
or signed input), the six combiner stages with the combiner buffer, alpha
test, and the mesh layers (opaque, translucent, additive) with their blend
modes.

- Pit's material uses the shared tables `CrvChr00` from `RomFS/us/0.arc`
  `resident/shared.arc` `00.bcres` (put as `common/shared_luts.json`).
  Materials name a table `sampler/table`, the file `table/sampler`.
- Re-dumping a model (for example with `skin`) rewrites its `luts.json`:
  copy the tables back from the model's first dump.
- Lights are the game's: each cutscene's `00.bcres` and each stage's
  `mdl 00.bcres` hold its light rig (`Chr_Light01`, `HemiSphereLight01`,
  `Natu_Light`...). `pica.ENV` (cutscene characters), `pica.CH1` (chapter 1
  stage, for Pit in the sky), `pica.NATU` (Viridi). The key light is kept
  where the cutscene cameras have it (front left), the hemisphere follows
  the world's up.
- The cutscene Pit (`demo/098` body 21 + head 22) plays Pit's gameplay
  moves (26/29 bones match); his head rides the body's `HeadN`
  (`outPitHF`, used by `render/sky.py`).

### Texture wrap modes and eye light

- Each texture unit's wrap mode (Repeat, Mirror, ClampToEdge, ClampToBorder
  per axis) and border colour are honoured by `pica.sample`. Without them,
  eyes tile (Pit's, Dark Pit's and Palutena's iris UVs run from -3 to 3 on
  a clamped texture), Viridi's eye highlight smears white, and Palutena's
  mirrored body texture comes out wrong.
- The `Wpn` mesh (material `ParmH00`) of the cutscene Pit and Dark Pit is
  their high-detail hands, not a weapon: keep it.
- Viridi's eye material multiplies its colour by 8; under a front key light
  it saturates to white. `pica.NATU['eye_dir']` lights her eye meshes only
  from her cutscene's own light direction; everything else keeps the front
  light. A known compromise.

### Idols

Idols used: 000 Pit, 009 Dark Pit, 002 Palutena (`P02`), 012 Viridi
(`V12`); also available: 001 winged Pit, 006 Medusa, 007 Magnus, 010
Poseidon, 011 Hades, 013, 014. Bone axes for posing (Palutena): `BustN` x
bends, y twists, z leans; `HeadN` y turns; hair and cloth chains swing on x.
