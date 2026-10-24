# PC interface plan — October 24, 2026

The proposed direction for the single-screen PC interface, written before
implementation, as the user asked: "design the full interaction and transition
flow before implementing, work in reviewable stages". **Status: proposed, in
review with the user; nothing is implemented from it until it is agreed.** The
visual version is the design canvas "KIU PC interface plan" (three pages: Plan
& flow, Gameplay, Menus). This file is the text companion; once agreed it
replaces `history/PC_INTERFACE_DESIGN_DIRECTION.md` as the current direction.
Nothing here is built yet unless marked "exists".

## Principles

- **The game draws, we arrange.** Every screen keeps the game's own art,
  animation, sounds, timing and logic. The PC layout moves, scales and groups
  the game's pieces; no generic PC UI.
- **Edges inform, centre plays.** HUD, dialogue, pictures and notices live in
  fixed lanes at the edges; the middle belongs to Pit, enemies and the reticle.
  Nothing moves when dialogue starts.
- **Mouse-native, controller-first.** Hover previews, click selects, the wheel
  scrolls or cycles; every action on keyboard and controller too, hints in the
  game's button glyphs.
- **Game data is authoritative.** Stats, fusion results, power rules,
  intensity, hearts, unlocks and saves come from the game. Saves stay
  compatible; PC options are stored separately. Jump and the power-bar
  choice are the only deliberate gameplay changes, both optional.

## Three ways a screen is made

| Mark on the canvas | Technique | Used for |
|---|---|---|
| gold, solid | **Recompose**: the game draws as usual; the presenter lays pieces of either screen where the PC layout wants them (`backend::pieces`, `kiu_ui::compose`), clicks mapped back (`touch_at`) | HUD, portraits, captions, menu buttons, hub scenes |
| blue, dashed | **Live picture**: the game's 3D view or upper screen as rendered | gameplay, hub rooms, models |
| pink, double | **Rebuild from game art**: the runtime draws with ROM textures (menu/HUD packs) from values read in game memory; actions are sent as the game's own inputs | chapter strip, weapon list and comparison, fusion, pause board, power bar |
| grey, dotted | **PC only** | settings, key hints |

## Gameplay

- **HUD**: health and air orbs top-left, score/hearts/intensity top-right (as
  now). On land the power bar takes the orbs' place under health.
- **Dialogue under the HUD**: speaker portrait on the left directly under the
  health group, up to two listeners beside it (smaller), captions to the right.
  Same place in flight and on land (one row lower on land). Slots never move
  during a conversation; a new speaker glides to the front in 0.15 s. Options:
  portraits Full/Compact/Off, caption backing Off/Soft/Panel, dialogue place
  Under the HUD / Bottom (3DS-like).
- **Lanes**: banner top-centre (chapter title card, boss/rival cards, section
  names); picture lane right under the score (retro pictures with their arrows
  and labels, moved as one group); notices bottom-right (pickups, treasure,
  bonuses); item/vehicle slot bottom-right corner, only while one exists. The
  centre shows only the game's 3D cues.
- **Flight aim**: guided camera untouched. The reticle follows the mouse over
  the whole window: the pointer feeds the game's own aim instead of a
  simulated stylus clamped to 320x240. Controller right stick.
- **Camera distance**: separate Flight and Land sliders (PC settings),
  100% to about 130%, only if the game's own camera value can be changed so
  culling, aim and effects follow (the shader-only widening is retired; it
  caused pop-in, doc/CULLING_AND_POP_IN.md). Readability never depends on it.
- **Powers**: the bar shows only the powers chosen in **Bar setup** (from Gear
  and Pause; order and visibility only, the board/equipment/charges stay the
  game's). Wheel cycles the chosen ones (exists for all equipped), 1-9 select
  directly, E uses, hold Q opens all equipped in place. Name and uses show for
  two seconds after a change. Controller LB/RB, Y, hold LB+RB.
- **Jump on Space**: J1 (exists): uses an equipped Sky Jump without selecting
  it, and Sky Jump leaves the bar. J2: unlimited, uses restored after each
  Space jump. J3: a basic move, the game's jump without equipping. If J3 is not
  possible: J2 with Sky Jump kept on the palette automatically. Always ground
  only, no double jump, never in flight or scripted scenes, can be switched off.

## Menus

- **Main menu and Solo hall**: the game's live scene fills the window; arrows
  at the sides step to the neighbouring place with the game's own camera move
  (one move at a time, clicks during a move dropped); the current place's sign
  large in the centre; all places as the game's buttons in a bar along the
  bottom; heart bank top-right, Back bottom-left. The main menu uses the same
  pattern with its section scenes.
- **Chapter select**: the game's page backdrop; the title strip, painting and
  records (pieces of the upper picture) large at the top; every chapter as the
  game's thumbnails in a scrolling strip (27 `MenSselDynamic` textures),
  locked ones as the game shows them; hover previews through the game's own
  selection; Fiend's Cauldron and Gear buttons beside the records.
- **Fiend's Cauldron**: as agreed October 15 (cauldron centrepiece, drag,
  wheel/arrows by 0.1, only Move Out! spends hearts).
- **Weapons**: type tabs and the game's weapon rows on the left; the model large
  in the middle; Compare (equipped vs pointed-at: stars with up/down marks,
  value) and modifiers lined up row by row; hover previews without equipping,
  click pins, Equip commits through the game.
- **Fusion** (complete redesign, same system): list on the left showing what
  each weapon makes with the pinned A; bench with A and B; result with the
  game's art, compared with your best of that type; "both are used up"; Fuse
  asks with the game's own question, focus on No. Results come only from the
  game.
- **Pause** (final): the game pauses first; the paused scene darkened with the
  game's swirl art; PAUSED plate, large Resume/Retreat/Options plates on the
  left; a read-only mission board in the game's ornate frame on the right
  (chapter card, intensity/hearts/bank/score, loot so far, equipped weapon and
  powers with uses, Bar setup link). Remove Display dropped. PC settings (F1)
  separate.
- **Practice Range**: training panels in reserved spots on the right; weapon
  card with its text in the banner lane. **Vault**: model large, list in a
  sidebar, drag to turn, wheel to zoom. **Treasure Hunt**: grid large left,
  condition/reward right. **Idol Toss**: mouse pull and release.
  **Options**: the game's bars unchanged, PC settings in a separate panel.

## Navigation and transitions

- Routes are the game's own (canvas board "Navigation and transitions").
- Esc/B one level back (the game's Back); Enter/A or click confirm; hover and
  keyboard focus share the game's highlight; wheel scrolls lists.
- Layout changes happen inside the game's fades; otherwise pieces glide in
  0.2 s, never during the game's camera moves or button animations. A layout
  holds 15 frames after its evidence ends.
- Pointer captured on the first gameplay frame after a load fade, released as
  soon as menu art appears; a click that changes capture is never passed on.

## Controls (proposed defaults, all rebindable)

Play: WASD/Alt/Shift move, walk, dash; mouse aim; left button fire; E power or
air special; wheel and 1-9 choose power; hold Q browse; Space jump; F item or
vehicle special, hold F get out; Esc pause; F1 PC settings. Controller: left
stick, right stick aim, RT fire, Y power, LB/RB choose, A jump, X item, Start
pause, View settings. Menus: hover/click, arrows/Enter, Esc or right click
back, wheel scroll, Q/E tabs; controller D-pad/stick, A, B, right stick, LB/RB.

## Stages

1. **Screen recipes**: one data table per screen (pieces, scale, click
   mapping), fade-aware transitions, input contexts, an outline overlay.
   Sign-off: title and save select (the composed save select, 14f79f5, is the
   first recipe).
2. **Gameplay HUD v3**: dialogue under the HUD, lanes, item/vehicle slot,
   flight aim over the window. Needs R3, R7.
3. **Powers and jump**: Bar setup, wheel over the chosen, 1-9, hold to browse;
   J1 to J2 (to J3). Needs R4.
4. **Camera distance**: only after R2 succeeds.
5. **Hubs and mission path**: main menu, Solo hall, chapter select, Cauldron,
   results, continue, game over. Needs R1, R6.
6. **Gear and Arms Altar**: weapon viewer, buying, fusion. Needs R5.
7. **Pause and Options**.
8. **Everything else**: Practice Range, Vault, Treasure Hunt, Idol Toss,
   loading and transitions, defeat screens.

Each stage replaces the layer it covers; the previous version stays behind a
switch until sign-off, then goes to `archive/`. Problems found in play are
fixed in their stage, not patched in between. The status document is
rewritten at each sign-off.

## Research spikes

| | Question | Unlocks |
|---|---|---|
| R1 | Which input makes each main menu / Solo hall camera move (input trace + census) | 5 |
| R2 | The game's camera distance or field of view in memory; do culling and aim use it | 4 |
| R3 | Where flight turns the touch point into the reticle (air consumer, cf. land hook in doc/LAND_CAMERA.md) | 2 |
| R4 | Remaining-uses counter; the call that starts a jump (doc/POWER_STATE.md) | 3 |
| R5 | Inventory, equipped weapon, stats, fusion results in memory | 6 |
| R6 | Selected chapter and unlock state | 5 |
| R7 | Caption draws on the upper screen, who is speaking, the game's own subtitle option | 2 |
