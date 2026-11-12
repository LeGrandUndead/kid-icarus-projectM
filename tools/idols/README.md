# Idols and menu models: 3D art for the PC menus

Kid Icarus: Uprising ships a posed 3D figure, an *idol*, for almost every
character (`RomFS/us/doll/NNN/doll`: `fmdl.arc` model, skeleton and two
skeletal animations, `Wait` and `Action00`; `bind.arc` textures), and the
menus' own 3D models (`RomFS/us/menu/NNN/menu/mdl.arc`, e.g. the save
select's three books with eight animations each). The PC menus redesign
(doc/UI_DESIGN_RULES.md) uses them: each main-menu mode shows a character
playing its idol move, the save select shows the real books.

Nothing here contains game data; everything is read from the player's own
extracted ROM.

- `convert/`: a small .NET tool on top of SPICA (public domain,
  github.com/gdkchan/SPICA) that writes a CGFX model as plain data: posed
  triangles, texture slots, alpha test and blending per material, the
  textures, and, given an animation name, every frame of it skinned
  (`Animate.cs`, ported from SPICA's viewer; the inverse bind matrices are
  recomputed from the rest skeleton, the stored ones do not survive the
  CGFX conversion). Building SPICA offline needs its System.Drawing
  bitmap code fenced off (`#if DRAWING`) and `Formats/Generic` removed.
- `render/idol.py`: a numpy software rasteriser for those exports: the
  game's textures (three UV sets, layered eyes, alpha tests), soft two-tone
  light, a rim light in the menu's colour, an ink outline. `chars.py`
  renders the main menu's animations, `books.py` the save select's books.
- `mockups/`: the menu mock-ups and the animated main-menu video built from
  those renders (paths point at a scratch folder; adjust to run).

Idols used so far: 000 Pit, 009 Dark Pit, 002 Palutena, 012 Viridi
(also 001 winged Pit, 006 Medusa, 007 Magnus, 010 Poseidon, 011 Hades,
013 Phosphora?, 014 a girl character).

Every script reads and writes its working folder from `IDOLS_WORK`
(default `work/`): the extracted models (`idols/`), the renders
(`render/frames/`), the fonts (`mock/`).

- `catalog/`: every animation we can play, as a labelled, looping grid.
  `build.py` lists them (each idol's Wait and Action00, and Pit's ground
  and air moves from `player/g0`, `a0` played on his idol) and exports
  24 frames of each; `render.py` renders them; `compose.py` lays out the
  pages (`compose.py still` for one still sheet per page).
- `render/freeze.py`: one frame of a move (Pit's idol Action00, frame 18,
  mid-leap) at every angle from -55° to +20°, so the menu can hold the
  pose and turn it toward the pointer; then the rest of the move from that
  frame, turning back to face the camera.
- `mockups/solo_freeze.py`: the Solo mock-up made from them: frozen pose
  following the pointer, click, the move resumes, a 0.4 s zoom into the
  Solo hall.
- `render/fly.py` + `mockups/solo_fly.py`: Solo at 60 fps with Pit's
  flight animation (Pit air AirGrideFlap1, catalog #131) looping; the model
  turns (yaw and pitch, on a soft spring) to head toward the pointer, the
  camera stays put; on click he turns to the camera and flies at it, and the
  Solo hall fades in behind him as he fills the screen.
- `render/sky.py` + `mockups/solo_sky.py`: Solo in chapter 1's sky
  (stage a0101 textures, unpacked into `stages/tex`: sky gradient, cloud
  wall as a scrolling sea of cloud, sun, cloud puffs shaped from the cloud
  layer textures, streaming opposite to Pit's heading). Pit's moves blend
  into each other: glide loop, banks (AirGrideL/R), glance back
  (AirGrideLookB), barrel roll on hover (AirRollingGrideLA); he leans into
  turns (`idol.render(bank=...)`, blended poses with `pose=`). On click he
  barrel-rolls past the lens (AirRollingGrideRA) with speed lines and a
  smear, and the next screen shows through the trail he cuts.

### Cutscene models (higher quality)

`RomFS/us/demo/NNN/demo/mdl.arc` holds each cutscene's characters, each a
separate model with its own cutscene-long animation: `c05_040_pith00` (Pit's
body), `c05_040_pith` (his high-detail head, facial bones), `bpith04` /
`bpith` (Dark Pit), `paluh` (Palutena), `natur` (Viridi), `magnh`, `hadeh`,
`meduh`, `chaph00`, `dinth`... The converter now also writes every bone's
world matrix per frame (`<anim>.bones`, `bones.txt`) and takes
`ANIM_START` / `ANIM_END` to export part of an animation.

- `cutscenes/merge.py`: joins models into one, dropping meshes by material
  (the body's own low face), and puts a head on its body: the head model's
  `HeadN` bone is moved onto the body's `HeadN` every frame.
- `cutscenes/cut.py`: the cutscenes used so far (`T05` chapter 5 fight,
  `T06`, `T21`, `T25`, `P20`/`P82` Palutena, `V11` Viridi, `H25` Hades) and
  `build(key, start, end, step, name)`.
- `render/sheet.py`: a 40-pose sheet of a cutscene, to pick moments.
- `render/cast.py` + `mockups/cast_menu.py`: Together (the chapter 5
  grapple in slow motion, then the fight; slash split), Vault (Palutena's
  idle, then the chapter 20 staff flourish; ring of light), Options (Viridi
  holds, then swings; sweep with leaves).

### Game shading (2026-11-12)

The renderer used to invent a look (two-tone light, ink outline, rim
light). It now shades each mesh the way the 3DS GPU does, from the model's
own material (`render/pica.py`, after SPICA.Rendering's shader generator):
texture coordinates per unit (UV sets, sphere reflection maps), vertex
colour with the hemisphere light, fragment lighting with the material's
look-up tables (distribution, Fresnel, reflection; output scale; absolute
or signed input), the six combiner stages with the combiner buffer, alpha
test, and the mesh layers (opaque, translucent, additive) with their blend
modes. No outline.

- The converter writes `materials.json` (per mesh), `luts.json` and, for
  files that have them, `lights.json` (`convert/Material.cs`).
- Pit's material uses the shared tables `CrvChr00` from `RomFS/us/0.arc`
  `resident/shared.arc` `00.bcres` (put as `common/shared_luts.json`).
  Note: materials name a table `sampler/table`, the file `table/sampler`.
- Lights are the game's: each cutscene's `00.bcres` and each stage's
  `mdl 00.bcres` hold its light rig (`Chr_Light01`, `HemiSphereLight01`,
  `Natu_Light`...). `pica.ENV` (cutscene characters), `pica.CH1` (chapter 1
  stage, for Pit in the sky), `pica.NATU` (Viridi). The key light is kept
  where the cutscene cameras have it (front left), the hemisphere follows
  the world's up.
- The cutscene Pit (`demo/098` body 21 + head 22) plays Pit's gameplay
  moves (26/29 bones match); his head rides the body's `HeadN`
  (`outPitHF`, used by `render/sky.py`).

### Texture wrap modes and eye light (2026-11-12)

- The converter also writes each texture unit's wrap mode (`wrap`: Repeat,
  Mirror, ClampToEdge, ClampToBorder per axis) and border colour
  (`border`); `pica.sample` honours them. Without them, eyes tile (Pit's,
  Dark Pit's and Palutena's iris UVs run from -3 to 3 on a clamped
  texture), Viridi's eye highlight smears white, and Palutena's mirrored
  body texture comes out wrong.
- `cutscenes/matfix.py`: re-exports only the materials of the parts in use
  after a converter change (the animation exports stay as they are).
- The `Wpn` mesh (material `ParmH00`) of the cutscene Pit and Dark Pit is
  their high-detail hands, not a weapon: keep it.
  `cutscenes/dropmesh.py` removes meshes by name from a converted model
  (geometry, materials, every `.frames`) if one ever has to go.
- Viridi's eye material multiplies its colour by 8; under the menu's front
  key light it saturates to white. `pica.NATU['eye_dir']` lights her eye
  meshes only from her cutscene's own light direction (above and behind);
  everything else keeps the front light. A known compromise.
- `render/cast.py` and `render/sky.py` skip frames that already exist:
  move the old frames aside before re-rendering after a model change.
