# PC interface: design rules

How every screen of the PC version is laid out, so the menus read as one
designed game on one 16:9 screen, not two 3DS screens put together. Each
menu is redrawn one at a time against these rules (main menu first).

## Why

The 3DS game has two screens. Its lower-screen art was drawn to fill a
small 320x240 touch screen, its upper-screen art a 400x240 one. Moved onto
one picture as they are, the lower screen's buttons come out too large next
to the upper screen's art, and anything brought along with them (bands,
frames, backdrops) looks pasted on. So the PC draws each element itself,
from the game's own art, at sizes chosen for the PC screen.

## Rules

1. **One scale, sized by role.** All redrawn elements of a screen share one
   scale. Their size follows their job (primary choices, secondary choices,
   Back), never the screen they came from. The game's art keeps its own
   proportions, so its own hierarchy (Solo larger than Vault) stays.
2. **Readable, not oversized.** At 1080p, text is at least 26 px tall (the
   TV/console minimum of the Xbox Accessibility Guidelines, XAG 101; 18 px
   for PC). Button labels stay under the screen's heading: the heading is
   the largest thing on screen.
3. **Safe margins.** Nothing within about 5% of the window's edges (the
   title-safe area: 1720x1000 at 1080p): 12 units of the 240-unit-tall
   window.
4. **Grid and consistency.** A screen's choices form one aligned group with
   even gaps. Back is always bottom-left, same place, same size; primary
   actions are where the player looks for them on every screen.
5. **One selection.** Pointer hover and keyboard/controller selection light
   the same element; select then confirm with a controller, click with a
   mouse; visible hover, press and selected states.
6. **The art stays clear.** Headings, illustrations and captions of the
   game's upper picture are never covered.
7. **The game's soul.** Only the game's own art (the menu art pack rebuilt
   from the player's ROM), never stretched or recoloured; 3DS-only things
   (StreetPass, AR Cards, HOME, battery, wireless) are left out. Hover and
   press effects are light: a glow in the game's gold, a small lift.

## Units

The window is 240 units tall (a 16:9 window is 426.7 wide). The game's upper
picture, filling the height, is 1 unit per console pixel. Sheet art is
placed at `scale` units per sheet pixel.

## Main menu (MENUID_TOP, archive 040)

- Upper picture fills the height (heading, art, caption band).
- Solo, Together, Vault, Options: one column at x 14, from y 24, scale 0.34,
  10 units apart, ending above the caption's black ground (y 165).
- Back: bottom-left at (12, 210), scale 0.5.
- Hover: gold glow and 6% larger; press: 3% smaller; click touches the
  game's real button, so its sounds and transitions play.
- Not yet: the game's keyboard/controller selection is not shown on the PC
  buttons, and hovering does not move it (rule 5).

Sources: Xbox Accessibility Guidelines 101 (text display), Xbox screen
areas (title-safe), "Secretly console first" (Game Developer).
