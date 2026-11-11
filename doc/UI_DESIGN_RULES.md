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

8. **Hover selects, click confirms.** Pointing at a choice selects it in
   the game (its heading, art, caption and sound follow at once); clicking
   confirms. Every input is acknowledged, as Sakurai asks of menus: a
   choice reacts when pointed at, when pressed, when grabbed.
9. **A menu you can play with.** Kid Icarus' own menus wobble and react to
   touch; the PC menus keep that: buttons hang on a vine in the art's own
   black silhouette style, sway, can be dragged and pushed into each other,
   and spring back, never leaving their place (a "toy-like" interface:
   playful, but every interactive thing still looks interactive).
10. **Full bleed.** The art fills the whole window: no bars, borders or
   page colour around it.

From Sakurai's menu columns (Famitsu vol. 138, *Masahiro Sakurai on
Creating Games*): pictures and colours with words, so choices read at a
glance; size follows importance; acknowledge every input; fewer choices
per screen; plain words over jargon; style (fonts, colours) shapes how the
whole game feels, so menus carry the game's own look.

## Units

The window is 240 units tall (a 16:9 window is 426.7 wide). The game's upper
picture, filling the height, is 1 unit per console pixel. Sheet art is
placed at `scale` units per sheet pixel.

## Main menu (MENUID_TOP, archive 040)

- Upper picture covers the window, held at its top.
- Solo, Together, Vault, Options hang from a vine on the left, alternating
  x 22 / 28, from y 22, scale 0.34, 10 units apart, tilted -2..2 degrees,
  ending above the caption's black ground (y 165).
- Hover: 5% larger, and the game's cursor is walked there with the D-pad
  along its own navigation map, so the game's selection (gold glow,
  heading, caption) follows. Click: touches the game's real button.
  Drag: the button follows within 22 units of home, pushes the others,
  springs back on release.
- Back: bottom-left at (12, 210), scale 0.5.

Sources: Sakurai, "Rethinking your menus" (Famitsu vol. 138, Source
Gaming translation) and his videos on menus and fonts; "Building context:
toy-like interfaces in games" (Game Developer); Xbox Accessibility
Guidelines 101 (text sizes); Xbox screen areas (title-safe); "Secretly
console first" (Game Developer).
