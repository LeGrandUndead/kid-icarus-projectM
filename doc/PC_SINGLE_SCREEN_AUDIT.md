# Single-screen function audit — October 12, 2026

## Scope and evidence

The live source and October 12 original-art baseline are authoritative. Older
documents describe superseded defaults (normal executable, cubic filtering,
and alleged stretching). No AI pack or gameplay redesign belongs in this task.
The October 14 priority is a separate adjustable wider gameplay view with the
original live dialogue portraits, followed by the offline menu integration.
Read together with PC_SINGLE_SCREEN_ARCHITECTURE.md.

This is a complete **inventory of the requested categories**, not a claim that
every chapter, expression, menu or peripheral has been exercised. Unknowns are
explicit; unknown states must remain accessible through the original screens.

Evidence:

- **R**: source inspection: `tools/zakuro/crates/zakuro/src/{lib,input,gamepad,settings,present}.rs`,
  core `memory/kiu_mouse.rs`, GPU `backend/mod.rs`, GL/Vulkan presenters.
- **C**: existing local recordings and screenshots: `build/input-traces/20261009-072852-462179`,
  `build/evaluation/wide-panels-fixed-5x-20261011`,
  `build/ai-hd-edition/validation-original-portraits` (historical captures only).
  User screenshots establish original portrait panels, chapter/intensity/hearts,
  special gauges, score, subtitles, Solo buttons and pause controls.
- **M**: [Nintendo electronic manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/nintendo_3ds_2/kid_icarus_uprising/ElectronicManual_Nintendo3DS_KidIcarusUprising_EN.pdf),
  sections 2–14. Read text; PDF screenshot retrieval was unreliable.
- **Q**: [Nintendo quick guide](https://www.nintendo.com/eu/media/downloads/games_8/quick_start_guide/QuickStartGuide_3DS_KidIcarusUprising_EN.pdf).
- **N**: [Nintendo developer interview: story](https://iwataasks.nintendo.com/interviews/3ds/kidicarus/0/5/)
  and [AR discussion](https://iwataasks.nintendo.com/interviews/3ds/kidicarus/0/6/).
- [Gameplay trailer reference](https://www.youtube.com/watch?v=rf1aplPQczM): located,
  not frame-verified. It is not evidence of complete lower-screen coverage.
- **B/U**: user brief defines the required inventory; exact original behavior
  is unverified. Do not treat proposed controls as existing game support.

Manual-confirmed controls: touch operates title/menu choices; save creation
asks for name, birthday and Mii. Land powers support D-pad selection/use as
well as touch. A carried item uses the attack button. Vehicles expose touch
actions and exit. Air gauges refill and can be touched when ready. Idol Toss
uses a pull/release gesture. Options includes subtitle positioning. The game
provides its own continue, gear and return choices after failure. These facts
inform the design; they do not prove a semantic hook exists in this runtime.

## Matrix conventions

Every row inherits the contracts below unless explicitly overridden:

- **F** = original dual-screen fallback required until that row passes parity.
- **Menu inputs (K/M/P)**: preserve current guest bindings initially (X/Z,
  arrows, Enter=Start); pointer click/drag maps to original touch; controller
  keeps original guest mapping. Proposed future menu-specific Enter-confirm /
  Escape-back cannot be applied globally: Enter is currently Start.
- **Play inputs**: current WASD/Shift/Alt, mouse relative aim and left attack,
  controller merge unchanged. E and 1/3 remain existing configurable D-pad aliases.
- **Assets/sounds**: original game owns art, animation, audio and timings in all
  rows. No new sounds, timers, charge counters or progression rules.
- **Status**: observed = screenshots/replay evidence; source = implementation
  confirmed; inventory-only = exact screens/alternatives still need capture.
- **Types**: I information, T interactive, G gameplay-critical, D dialogue,
  O optional, V decorative. A slash means multiple roles.

## Startup, system and primary navigation

| State / reproduction | Top screen | Bottom screen / type | Touch / original alternatives | Assets and details to retain | Proposed PC composition / K,M,P | F / evidence / status |
|---|---|---|---|---|---|---|
| Title / boot | Title presentation | Start interaction T/V | Tap; button parity unverified | Title animation, start sound | Full-window title with original touch access; Menu inputs | Yes M/R; inventory |
| Save select / after title | Associated presentation, exact layout U | File choices T/I | Tap; selection buttons U | Slots, confirmation, save indicator | One scene; Menu inputs | Yes M; inventory |
| New save / empty slot | Setup presentation U | Name/birthday/Mii T/I | Touch; software keyboard service | Original identity fields, dialogs | System keyboard as modal; pointer focus | Yes M/R; keyboard service exists |
| Save erase / file action | Confirmation context U | Destructive confirmation T | Original button sequence; do not synthesize | Original wording and warning sounds | Preserve full confirmation flow | Yes M; inventory, do not exercise on live saves |
| Loading / chapter transition | Scene/fade/possible art U | Hints/art/fades U V/I | Normally none; exact exceptions U | Both displays' fades and save feedback | Transition-aware composition; fallback | Yes B/U; chapter capture needed |
| Error / confirmation | Context U | Modal choice T/I | Original guest actions U | Original wording, icon, sound | Modal original surface; Menu inputs | Yes R/B; service and game dialogs distinct |
| Main menu / selected save | Original presentation U | Solo/Together/Vault/Options plus utility entries T/V | Touch; button coverage U | Entry artwork, hover/selection motion, cues | Full-window scene preserving top preview; Menu inputs | Yes M; inventory |
| How to Play / main menu | Tutorial footage U | Playback/navigation U T/I/D | Touch; transport alternatives U | Pit/Palutena teaching, timing | Video/tutorial scene with accessible controls | Yes M; inventory |
| AR entry / main or Vault | Camera/model view | Controls/stats U T/I | Touch; camera dependency | Original model and stat presentation | Preserve entry and honest unsupported-service feedback | Yes M/N; camera support unverified |

## Solo, equipment and progression

| State / reproduction | Top screen | Bottom screen / type | Touch / original alternatives | Assets and details to retain | Proposed PC composition / K,M,P | F / evidence / status |
|---|---|---|---|---|---|---|
| Solo hub / Solo | Preview/presentation U | Move Out, Gear, Arms Altar, Practice, Idol Toss, Treasure Hunt T/V | Tap; button navigation U | Illustrated moving buttons | Full-window original menu composition; Menu inputs | Yes C; bottom observed |
| Chapter select / Move Out | Chapter preview U | Chapter choices/info T/I | Tap; exact navigation U | Chapter art, unlock states, scores | Preview + selection scene; Menu inputs | Yes M/B; capture needed |
| Intensity / chapter selected | Cauldron presentation U | Adjustment and hearts T/I | Drag + original alternatives U | Cauldron ritual, cost feedback, sound | Preserve animated cauldron; future incremental K/P, drag M | Yes M; no value hook |
| Gear / hub or retry | Weapon preview/stats U | Equipment choices T/I | Touch; alternatives U | Model, attributes, selection sounds | Preview + equipment scene; Menu inputs | Yes M/B; capture needed |
| Weapon select / Gear | Model/stats U | Weapon list T/I | Touch/list; alternatives U | Modifiers, value, selection | Original list/model; scrolling only after parity | Yes B/U |
| Power Board / Gear | Board/help context U | Spatial pieces/grid T/G | Drag; rotation/Autofill exact controls U | Shapes, constraints, icons, feedback | Preserve puzzle grid; drag M, original K/P first | Yes B/U; never replace with list |
| Practice Range / Solo | Air/land gameplay | Dialogue/actions/settings T/D | Existing guest controls | Practice transitions and instruction cues | Gameplay composition with fallback | Yes C; existing replays |
| Arms Altar / Solo | Weapon presentation U | Buy/fuse/dismantle choices T/I | Touch; alternatives U | Ritual, weapon models, costs | Original scene then semantic list integration | Yes M/B; capture needed |
| Purchase / Altar | Preview U | Stock/prices/confirmation T/I | Touch; alternatives U | Costs, buy confirmation/audio | Menu inputs; no economy changes | Yes B/U |
| Fusion / Altar | Result preview U | Two inputs/result/confirmation T/I | Touch; alternatives U | Modifiers and result feedback | Keep game calculation and confirmation | Yes M/B; no result hook |
| Dismantle / Altar | Selected weapon U | Conversion/confirmation T/I | Touch; alternatives U | Heart feedback and consequences | Menu inputs; no automatic actions | Yes M/B; no semantic hook |
| Idol Toss / Solo | Toss/reward animation | Egg/tray interaction T/V | Pull and release; button alternative U | Arc, anticipation, reveal/audio | Original motion/gesture in single scene | Yes M; capture required |
| Treasure Hunt / Solo | Reward/help U | Challenge grid T/I/V | Tap; alternatives U | Tile reveal/completion cues | Full-window grid with original feedback | Yes M/B; capture required |
| Chapter rewards / completion | Results/presentation U | Loot/results choices U T/I/V | Confirm; exact actions U | Loot/heart counting, reveal timings | Results scene, preserve all stages | Yes B/U |
| Failure / defeat | Failure/cauldron feedback U | Continue/return/gear T/I | Original choice actions U | Consequences and availability restrictions | Original modal flow, no fake retry state | Yes M; capture required |

## Combat and pause

| State / reproduction | Top screen | Bottom screen / type | Touch / original alternatives | Assets and details to retain | Proposed PC composition / K,M,P | F / evidence / status |
|---|---|---|---|---|---|---|
| Air / Chapter 1 or practice | World, HP, score, reticle, enemy markers | Chapter/intensity/hearts, portraits, specials I/T/G/D | Aim drag; E/D-pad aliases already verified | Gauge fill, indicators, dialogue timing | Full gameplay; later original gauges/portrait layers; Play inputs | Yes C/R; actions exist, widgets pending |
| Land / Chapter 1 or practice | World, HP, reticle, guide/item markers | Power Palette, held item, dialogue I/T/G/D | Touch aim/powers; original D-pad; carried item via attack | Palette scroll/selection/charges, indicators | Full gameplay; semantic quickbar later; Play inputs | Yes C/R/M; power actions tested |
| Special / charged air gauges | Original attack effects | Two charge gauges T/G | Touch or existing E alias | Charge fill and original activation sound | Gauge widget from verified game state; E/P unchanged | Yes C; no gauge-state hook |
| Powers / equipped land loadout | Power effect | Selected icon, charges, other powers T/G | Slide/tap or D-pad; 1/3/E mapped | Disabled states, charge changes, selection cues | Quickbar; configurable aliases, eventual wheel | Yes C/R; read-only state hook needed |
| Carried item / collect stage item | Pickup marker/effect | Item icon I/G | Attack button per manual; contextual exceptions U | Original pickup/use cues | Item display; avoid duplicate Use Item logic | Yes M/B; distinct from equipped powers |
| Vehicle / chapter containing one | Vehicle world/camera | Special and exit controls T/G | Touch contextual icons; entry uses attack | Vehicle-specific icon and action effects | Context widget after verified vehicle identity | Yes M; no vehicle hook |
| Boss / chapter encounter | Boss/combat | Dialogue and contextual changes U D/G | Preserve gameplay | Introductions, boss-specific gags | Gameplay + scene-owned event presentation | Yes B/U; encounter regression needed |
| In-game pause / Start | Paused world/banner | Resume, retreat, options, loot/display controls T/I | Touch and original navigation | Original pause fades, sounds and state | Modal bottom fallback initially; native pause later | Yes C; distinct from F1/runtime pause |

## Dialogue and the small details

| Event / reproduction | Top | Bottom / type | Original input | Preservation requirement / proposed PC handling | Status / fallback |
|---|---|---|---|---|---|
| Ordinary banter / Chapter 1 | Gameplay and subtitles in supplied capture | Pit/Palutena portraits, chapter background D/V | Gameplay continues | Keep audio and guest frame timing; portrait layers need verified source bounds/alpha | C; fallback required |
| Expressions / ongoing lines | Gameplay | Expression changes D | None expected, confirm exceptions | No inferred emotion or AI redraw; retain original frame/asset selection | C/B; expression identity unexposed |
| Two or more speakers / later chapters | Gameplay/subtitles | Multiple portraits D | Gameplay | Preserve simultaneous reactions/entrances, not merely active speaker | C/B; full roster and timing unverified |
| Portrait entry/exit / line changes | Gameplay | Animated position/transition D/V | None expected | Follow original transforms; avoid static cropped heads | B/U; trace draw transforms |
| Visual gag / chapter-specific cue | Gameplay/reference | Retro sprite, image, fourth-wall reference D/V | Gameplay or context U | Preserve whole event and its trigger frame; never discard unknown bottom graphics | B/U; chapter+timestamp capture needed |
| Screen-reference joke / chapter-specific cue | Gameplay/reference | Referenced image D/I | Context U | Place original image visibly at original time; do not rewrite voice audio | B/U; event catalogue needed |
| Subtitle options / Options | Placement varies | Placement varies | Original option | Respect guest options; do not duplicate subtitles or assume top-only | M/B; capture all choices before extraction |
| Button/pickup/treasure feedback / each menu or pickup | Effects/counting | Motion, highlight, sound I/V | Original action | Keep animation/sound driven by original logic; no new confirmation timers | C/B; per-scene comparison |

Chapter 1 supplied screenshots show portraits occupying much of the bottom
screen over a colored chapter panel, not isolated transparent portrait images.
Cropping the full panel into a permanent combat rectangle would fail the brief.
No fixed region can yet be certified as portrait-only through all expressions,
power palettes, pause transitions and visual jokes. **Do not ship that shortcut.**

## Secondary and legacy systems

| State / reproduction | Top | Bottom / type | Touch / original alternative | Assets / proposed PC scene and inputs | F / status |
|---|---|---|---|---|---|
| Together / menu | Multiplayer presentation U | Mode/lobby/settings T/I | Touch; normal gamepad navigation U | Original lobby and rules; Menu inputs | Yes M/B; network services incomplete |
| Multiplayer match / connection required | Match, team/score UI U | Multiplayer-specific controls/info U G/T | Original guest controls | Keep original match UI until observed | Yes B/U; do not claim online support |
| Vault / menu | Preview U | Collection entries T/I | Touch; alternatives U | Original collection scene; Menu inputs | Yes M; inventory |
| Idols / collection | 3D model U | Selection/info/control U T/I | Drag/rotate alternatives U | Larger preview with original controls after capture | Yes B/U |
| Records / Vault | Statistics U | Categories/pages U T/I | Touch; alternatives U | Original typography/icons; full-window data scene | Yes B/U |
| Music / Vault | Artwork/track U | Tracks/playback U T/I | Touch; alternatives U | Preserve music and original player feedback | Yes B/U |
| Options / menu | Explanation/preview U | Settings T/I | Touch; alternatives U | Guest options retained; host options separate | Yes M/R; host settings already exist |
| AR / camera/card | Camera and idols | Stats/actions U T/I | Touch/button and physical cards | Preserve original entry; document camera limitation | Yes M/N; no verified host camera path |
| StreetPass / gems | Gem preview U | Create/bag/fuse choices T/I | Touch; alternatives U | Original gem mechanics; unsupported transport explicit | Yes M; cecd commands incomplete |
| SpotPass / options | Context U | Enable/notifications/gems U T/I | Original options | No simulated downloads or invented rewards | Yes M; unavailable service path |

## Current implementation map

Both guest framebuffers stay alive. GSP framebuffer updates feed GPU surfaces.
`System::gpu_screen` returns a shared-device image when possible; `shown` uses
that image or falls back to `System::screen`. `App::present` supplies both to
the presenter; GPU layout selects destination rectangles. Existing Vulkan
composition samples the shared GPU images; this work must not introduce a new
CPU pixel readback loop. Current CPU fallbacks remain a separate renderer concern.

Touch maps a displayed bottom rectangle into 320x240 guest coordinates.
Captured mouse uses `Keyboard::pc_mouse_motion`; it is not the same cursor.
`queue_kiu_mouse` supplies guarded relative movement at the actual game consumer.
Tab currently saves layout/aim, releases keys/touch, shows bottom-only, and
restores a one-sample touch release plus aim on return. Focus loss cancels
automatic recapture. Controllers merge guest buttons and left-stick input after
keyboard sampling. No complete native right-stick aim/menu-pointer path exists.

Existing hooks: USA executable signature; exported input at 0xEFD4D4; ring
consumers 0x610524/0x60A094; camera discovery 0x4DB974; land/air consumers
0x7DAB54/0x7DAB1C with camera mode byte +0x1C and active byte +0x34.
These are **input-consumer evidence**, not a universal game-state enum. Their
absence does not prove a menu or pause; do not repurpose them as such.

## Regression checklist and missing evidence

Capture paired top/bottom frames for title, save selection, main menu, chapter
selection, intensity, Gear, Power Board, practice, air, land, boss, dialogue-heavy
chapter, powers, carried item, vehicle, pause, failure/continue, rewards and Vault.
For every interactive scene test keyboard, mouse and controller separately.
Record game revision, initial copied save, controls, frame number and resolution.
Do not test destructive save or purchase operations on personal saves.

Needed for semantic widgets: read-only power ID/selection/charge snapshot;
special-gauge values; item/vehicle identity; portrait draw ownership, source
rectangles, alpha, transforms and event lifetime; reliable pause/menu transitions.
The ROM is already local. What is missing is verified runtime state and recordings
of those modes, not a different ROM or a high-resolution texture pack.

## Original lower-screen art map — October 15

Decoded locally from `RomFS/us/info/common/info/00.bcres` (not committed).
Names are the ROM's texture names. This tells which atlas a lower-screen draw
samples; the sampled rectangle tells which element.

| Atlas | Format | Contents seen | Lower-screen use |
|---|---|---|---|
| gc_00 | ETC1A4 256² | blue air-special orb, coloured wing/feather icons, heart and heart-bag counters icons, green crosshair, arrows, "OK" / "Reset" plates | gameplay HUD + some confirmations |
| gm_00 | LA4 256² | digits (three styles), A/B/X/Y glyphs, "SCORE", round buttons | counters, prompts |
| gm_01 | LA4 256² | Resume, Retreat, Paused, Remove Display, Display, option icons | **pause menu only** (menu role) |
| gm_02 | LA4 256² | frames, palette tab, L/R glyphs, arrows | palette and panels |
| gm_03 | LA4 128² | ornate ring frame | panels |
| mr | ETC1A4 256² | Power Palette power icons | land HUD |
| ie_00 | ETC1A4 256² | item icons | items/treasure |
| tgt | ETC1A4 256² | weapon icons, digits | gear/menus |
| imsg | LA4 256×128 | system icons, digits | messages |
| bg | L4 256² | background swirls | decoration |
| gc_01 | ETC1A4 256² | control diagrams | tutorials |

Per chapter (`a010`, `g010`, …): `FB_*` portraits, `CP_000` chapter title,
`CI_*` chapter art, `BL_/BR_` land-chapter art. `single`: results (`rc_*`,
`rm_00`) and loading (`ld_*`). `multi`: Together HUD (`vc_*`, `vm_*`).

The October 14 draw sequence (`build/native-ui/gameplay/dialogue-draws.png`)
shows the Chapter 1 air lower screen as: background, swirls, frame, chapter
title, counters, intensity, portraits, special orbs, then the stylus marker.
