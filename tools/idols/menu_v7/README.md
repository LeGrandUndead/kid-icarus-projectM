# Main menu v6/v7 ("Dream" layout, cutscene light, game-menu focus)

After the work folder was lost (2026-11-12), the committed scripts were
recovered word for word; `ui_v4.py`, `still_v7.py`, `bg.py`,
`../stg/stack.py`, `solo_sky_v7.py` and the converter's textures-only mode
were rewritten. The game's caption font is drawn from Montserrat Regular
(the 3DS shared font's source, from the PC build's `font-source`), so the
old CFNU bitmap decoder is no longer needed.

Run from a work folder (`IDOLS_WORK`) laid out as: `x/` (RomFS archives
unpacked), `idols/`, `fx/` (effect textures), `mock/Montserrat-Regular.otf`,
`render/` (frames), `redraw/` (these scripts, `all/040/` menu art, `bg/`).

- `ui_v4.py`: heading flourish, ground band with laurels, caption,
  controls, soft glow, the game's particle images and their drift.
- `bg.py`: the three stage backgrounds (cameras per mode).
- `still_v7.py`: one still per mode.

- `grade.py`: cutscene light on a finished page: backlight rays, bloom,
  the four-point star flare, warm/cool grade with vignette.
- `stage_view.py`: a game stage rendered with a perspective camera (near
  clipping, perspective-correct interpolation) for the menus' backgrounds.
- `post_shade.py`: extra cutscene-style shading on the characters.
- `still_v3.py`, `still_v6.py`: one still per mode (v6 = Dream + cutscene light).
- `ui_v7.py`: clearer focus on the vine (others step back, the chosen one
  grows and leans out, a glint sweeps it).
- `cast_menu_v5.py` / `cast_menu_v7.py`: the 60 fps Together / Vault /
  Options videos (drifting stage, rays, particles, bloom, flares, click
  burst, the menu leaving, the three wipes).
