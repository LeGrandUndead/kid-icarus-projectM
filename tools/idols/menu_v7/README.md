# Main menu v6/v7 ("Dream" layout, cutscene light, game-menu focus)

Recovered after the work folder was lost (2026-11-12): the scripts below are
exact copies; `ui_v3.py`, `ui_v4.py`, `still_v5.py`, `solo_sky_v5.py`, the
font decoder (`bcfnt.py`), the stage merger (`stack.py`) and SPICA's
textures-only reader were not committed and must be rewritten.

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
