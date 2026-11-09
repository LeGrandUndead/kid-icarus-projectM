# Roadmap

The goal: Kid Icarus: Uprising as a native-feeling PC game, in the spirit
of Sonic Unleashed Recompiled. The player supplies their own ROM; the game
keeps its soul (its art, its jokes, Sakurai's team's look), and plays on one
screen with mouse and keyboard or a controller. Saves, high-resolution
rendering and the controls never regress.

Rules of work: find the root cause and change the game's own code where
needed; look at the whole architecture first ([ARCHITECTURE.md](ARCHITECTURE.md),
[GAME_ARCHITECTURE.md](GAME_ARCHITECTURE.md)); one change at a time,
measured before and after.

## Where it stands (November 9 2026)

| Area | State |
|---|---|
| Launcher | `Kid Icarus Uprising.exe`, by double-click, no Python or console (`kiu_launcher.rs`) |
| Frame rate | 60 FPS mode, with the chapter 9 white screen fixed (`WARP_WHITE_SCREEN.md`) |
| View | 16:9 and zoom made by the game's own camera: drawing, culling and aim agree (`WIDE_VIEW.md`) |
| Controls | keyboard and mouse on land and in flight, Space jump, rebindable; controller |
| Interface | portraits, specials, powers and counters over gameplay; pause menu as a panel |
| Loading | library and ROM read ahead in the background (`rom_prefetch.rs`) |

## 1. A clean product (now)

1. **Launch and first run.** Done: one program, ROM found or asked for
   once. Left: the first-run preparation still needs Python scripts (the
   interface catalog `build/native-ui/ui-sources.tsv`, the HUD pack); move
   it into the program. An icon. Saves and settings out of `build/`.
2. **Smoothness.** Cold-start hitches (prefetch, to be confirmed on the next
   cold start). Then the remaining slow frames by cause, from the session
   logs' `slow_frame` lines.
3. **Open bugs.** Pit feeling slower in flight on the keyboard (lead: the
   relative flight aim rewriting the touch state; test with
   `Launch-KIU.cmd --original-flight-aim`). Markers and captions 16/15 wide.
4. **Set-aside work, one at a time** (`ROLLBACK_2026-10-29.md`): the kernel
   wake-order fix, the presenter's frame skip.
5. **Code clean-up.** One program instead of five identical ones; the
   environment switches the launcher sets become settings; research
   switches kept apart.

## 2. One screen, from boot to credits

- Menus on one screen, never switching layouts, rebuilt from the game's own
  assets (the room kept, buttons in the same style).
- The HUD: an HD, PC-adapted version of the game's own, faithful to the
  original. No AI upscaling, no redesign; the portraits are not touched.
- Chapter 1 HUD bugs.

## 3. After that

Quality of life (skippable scripted sections), mod support, new content
(boss rush, missions), online. Fixes where players' feedback asks for them.
