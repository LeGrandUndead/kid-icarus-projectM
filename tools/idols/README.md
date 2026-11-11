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
