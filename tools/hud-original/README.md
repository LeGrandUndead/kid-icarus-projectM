# Original PC HUD design (October 16)

New vector HUD art in the Kid Icarus style: nothing traced or copied from the
game. `ink.js` generates brush-ink strokes, spiral curls and thorn leaves
from parameters; `hud.html` draws the wing, health bar, score, counters,
orbs and Power Palette; `render.py` renders air/land mockups over local
captures with Playwright.

Local-only inputs (not committed): `*_clean.png` gameplay backgrounds and
`icon*.png` power icons from the ROM pack. Font: Lilita One (SIL OFL,
`npm i @fontsource/lilita-one`).
