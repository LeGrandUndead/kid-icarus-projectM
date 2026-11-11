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
