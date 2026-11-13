# Archive: the menu mock-ups

Kept for their history, not used by anything any more. These scripts made
the main menu's design mock-ups (stills and videos, versions 3 to 11) before
the menu was drawn live by the game (tools/zakuro/crates/zakuro/src/pc_menus).
What the game needs from them now lives in `../menu_pack` (the scene pack
builder), `../render/stage_backgrounds.py` and `../render/stage_view.py`.

- `menu_mockups/`: the first mock-ups and their helpers (mk.py, vine.py,
  menu_anim.py).
- `menu_mockups_v7/`: the "Dream" layout and the v8-v11 "Ink & Paper"
  videos (menu_v11.py is the design the game now plays), the old pack
  builder (scene_pack.py) and the measuring scripts (motion_stats.py,
  colour_stats.py). They ran from a work folder laid out by hand (see their
  README) and exec'd one another; they are not maintained.
