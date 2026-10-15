# HUD art directions (October 15)

Hand-drawn vector HUD and pause-panel sketches (directions A, B, C) for the
new PC HUD. All shapes are drawn here; no game texture is used.

- `clean.py` paints the game's own HUD out of local captures (not committed).
- `hud.html?style=A|B|C&scene=air|land&mode=play|pause` draws one mockup.
- `render.py` renders all nine to `out/` with Playwright Chromium.

Fonts: Cinzel, Marcellus, M PLUS Rounded 1c, Rajdhani, Exo 2 (all SIL OFL),
installed with `npm i @fontsource/...` next to `hud.html`.
