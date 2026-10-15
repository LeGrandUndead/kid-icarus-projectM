# PC interface design direction — October 15, 2026

Design discussion for Codex, Claude and the user. This is a proposal, not an
implementation approval or a claim about completed runtime support. The mockup
PDFs in `mocks/` remain unchanged. Current runtime evidence belongs in
`PC_SINGLE_SCREEN_STATUS.md`.

## What the user has selected

- A's grouping beneath the game's original health/score HUD is the preferred
  starting point for air and land.
- The dialogue treatment is liked. Preserve original character artwork,
  expressions, voices, timing and visual jokes.
- The retro Medusa image is a **picture insert**, distinct from a character
  portrait. The concern applies to other dialogue pictures too: avoid the
  middle of the action view.
- B's bottom-corner arrangement is not the preferred direction.
- C's disappearing information is undecided, especially until power selection
  has been designed. Do not treat it as the selected default.
- Continue designing HUD, menus and pause before implementing another layout.
- Offline game features are in scope; online is excluded.
- Mouse wheel is the preferred gameplay power selector, replacing 1/3 as the
  primary PC interaction. Selection must not activate a power.
- Pause composition is only a placeholder. A more stylized, information-rich
  pause menu will be designed later.
- Main-menu navigation should preserve the entire animated scene and the
  original camera movements, with clickable directional arrows in the scene.
- Fusion needs a complete menu redesign while preserving the fusion system.
- Jump on Space, without selecting the Jump power and without a limited number
  of uses, is a desired gameplay experiment. Its equipment requirement is open.

## Proposed next version: A with a dedicated picture area

Keep health and score at their existing upper edges. Under health: air-special
orbs in flight; the equipped power palette on land. Under score: compact,
clearly distinguished chapter intensity, collected hearts and bank information
where the game makes them relevant. Do not silently merge counters with
different meanings. Artwork and ornamental shapes stay recognizably original.

Keep captions in a stable lower band. Preserve the liked portrait/subtitle
composition from A for the next comparison; do not move character portraits
solely because the user rejected centered *picture inserts*. Test original
two-character reactions and a crowded conversation before changing speaker
visibility. Neither missing lines nor a new portrait should shift text sideways.

Prototype a small left-side picture area below the health/power group and above
the dialogue band. It appears only while the original picture is active. Keep
the picture, arrows, labels and related layers together, preserve aspect ratio,
and retain their timing and internal animation. This relocates a complete visual
joke, not each sprite independently. Use a subtle original-style frame only if
needed for readability; do not bake a frame into the source artwork.

The position is a proposal to compare, not a settled placement. Test a regular
illustration, a retro image with text, a wide image and overlapping inserts.
Allow the picture area to grow within its assigned side region when text would
be unreadable. Never discard an insert to reduce clutter. The design must also
work at 1280x720, with larger captions, and during busy land combat.

Do not move powers or counters when dialogue starts. Stable positions are more
important than squeezing every conversation into a different arrangement.
Use temporary emphasis for changes; leave actionable information visible.

## Power selection proposal

Default: a persistent compact row beneath health, with the original icons,
selected-power highlight and readable remaining charges. Selection and use are
separate actions: mouse-wheel up/down cycles the equipped powers; E remains the
proposed activation button. 1/3 may remain optional rebindable alternatives,
but are not the primary design. Preserve mouse aiming while scrolling. Wheel
input over menus scrolls their contents rather than changing gameplay powers.
Accumulate high-resolution wheel deltas so a touchpad does not skip the whole
palette. Selection feedback should show the icon, name and charges immediately.
Show a power's name beside the row briefly on selection; never use an empty
name bubble as the final UI. All equipped entries must remain reachable,
including palettes larger than the four-icon mockup example.

An optional hold-to-browse palette can be explored after the compact row works.
It expands from the same location and hands pointer ownership to that UI only
while held. Releasing closes it and restores aiming without an accidental shot
or power use. Hovering or selecting does not spend a charge. This expanded
palette is optional exploration, not a replacement for the requested wheel.
Do not add time slowing, automatic pausing or mid-battle equipment changes.

C's active-power-only treatment may become a user preference later. It should
not be the default before selection, power names and charge visibility are
verified. Check existing wheel bindings and the complete equipped palette when
implementing the requested wheel interaction.

## Power loadouts and jumping — distinct gameplay work

The existing Power Board remains an acceptable presentation, but the user also
wants an easier way to choose desired powers and may want broader power-system
changes. Do not assume this authorizes removing the placement puzzle, its
capacity, unlock requirements or every power's charge limit. The distinction
between easier selection within existing constraints and a new loadout system
is still open; make both consequences explicit in later designs.

Space should trigger a jump directly, without selecting Jump in the palette.
Two user-proposed variants remain open:

1. Jump becomes part of the basic land moveset, independent of equipped powers.
2. Jump must be equipped, but Space invokes it directly with unlimited uses.

Suggested first experiment: variant 2 as an optional setting, using the game's
existing jump action. This is a proposal, not a chosen final rule or a claim
that the action is already callable. Unlimited uses do not mean unlimited
midair jumps, flight jumping or bypassing movement locks. Grounded eligibility,
landing/retrigger behavior, attack interactions, obstacles and scripted scenes
need investigation. Preserve normal behavior as a selectable fallback. The
user has not specified cooldown, jump height or broader power balance changes.

## Menu concepts

| Screen | Proposed PC composition | Interaction and preserved rules |
|---|---|---|
| Pause | Placeholder only: freeze/dim the scene with Resume, Options and Retreat plus a chapter/gear summary. Later design should be more stylized and information-rich. | Escape resumes. Keep Retreat confirmation and consequences. Read-only summaries do not imply equipment can change mid-mission. PC settings remain distinct from original game options. |
| Main menu / Solo | Show the full animated backdrop. Place readable clickable arrows in the scene/on the ground, preserving original banners, artwork and spatial personality. | Clicking an arrow requests the original navigation and camera movement. Synchronize hit targets with moving destinations; prevent repeated clicks from queuing unwanted transitions. Keyboard/controller focus follows the same routes. Back returns one level. |
| Chapters | Retain the current selection flow; modernize spacing, readability and information hierarchy, using original chapter artwork. The list/detail composition is a candidate. | Selecting previews; an explicit action proceeds to difficulty/preparation. Do not invent unavailable rewards or unlocks. |
| Fiend's Cauldron | Keep the original cauldron as the centerpiece; show intensity, heart stake and the game's resulting information alongside it. | Drag directly, or adjust with keyboard/controller. Confirm through the game's existing start flow; moving the pointer alone cannot spend hearts. |
| Gear / weapons | Modernize the framing while preserving personality. A large weapon view, clearly grouped stats/modifiers and selected/equipped comparison are the priorities. | Hover previews without equipping; selection pins details so they do not change while reading. Explore model rotation/zoom where the original assets support it. Explicit Equip commits; use actual stats and restrictions. |
| Power Board | Original placement grid large enough for precise mouse use, with available powers beside it and contextual help. | Drag/place/rotate according to the game's existing rules, with keyboard/controller equivalents and cancellation before commitment. Preserve shapes, limits and equipped state. |
| Arms Altar / Fusion | Complete menu overhaul. Candidate: searchable/sortable inventory list on the left, two chosen ingredients in the middle, actual resulting weapon and stat/modifier comparison on the right. A card/grid variant can be compared before choosing. | Pin the first ingredient, preview valid partners, then select the second. Hover never fuses or changes inventory. Show both consumed weapons and the actual result before explicit confirmation through the original fusion system. |
| Practice Range | A separate training HUD layout: damage/distance and weapon information have reserved positions. | Powers and dialogue must not overlap training panels. No assumption that the regular combat layout fits this scene. |
| Vault, Treasure Hunt, Idol Toss, rewards, failure/continue | Use the same focus, Back and typography conventions while retaining each screen's original visual identity. | Produce separate designs from observed states. Preserve unlock conditions, costs and the actual available choices. |

## Implementation approach, when design is settled

For the interface redesign, the game remains authoritative for selection, inventory, charges, difficulty,
costs, unlocks, dialogue and saves. Recompose known original draw groups where
possible; add host layout and pointer/focus behavior around verified game state.
Do not replace menus with static screenshots or recreate their rules from guesses.
The separately proposed jump/power experiments are explicit exceptions to be
designed and tested independently; a UI redesign must not silently introduce them.

Important existing gap: relocated power names and some lower-screen text come
from GPU render-target textures, not ordinary ROM textures. The renderer must
support those original text surfaces in the composed HUD. Designing a name label
does not mean its text is already available as a string.

A HUD layout must work at the normal camera view. Wider projection alone does
not fix the game's culling, aiming limits or screen effects; that is separate
game-side work. Never make zooming out a requirement for readable dialogue.

Keep the existing working build and compatibility access until every replaced
screen has a verified route in and out. Identify real pause and modal states;
drawing a pause panel must actually pause the game, not merely cover combat.

## Next design deliverable

Prepare a linked visual prototype, separate from the runtime, with these states:

1. Air HUD with ordinary dialogue, and again with a left-side picture insert.
2. Land HUD with wheel selection, selected-power name/charges and optional expanded palette.
3. Busy dialogue with multiple characters and an unusually wide picture.
4. Pause, Options and Retreat confirmation as functional placeholders, not final styling.
5. Animated Solo-scene arrows to Chapter to Cauldron to mission launch.
6. Gear inspection/comparison and a complete Fusion selection/preview/confirmation flow.
7. Power Board plus an explicitly labeled alternative loadout concept; jumping is a separate rules discussion.

Show mouse, keyboard/controller focus, Back behavior, disabled actions and the
transition between gameplay aim and pointer selection. Use original assets and
label sample values as illustrative. These mockups test layout and flow; they
are not evidence that the corresponding game-state hooks exist.

## User review of states 4-7 (October 15, 12:53)

Mockups: the "KIU PC HUD directions" design canvas (boards 4-7), composed from
captures of the user's build on October 15. All seven states now exist as
static frames; they are not yet linked as a clickable prototype.

- **Pause / Options / Retreat:** direction accepted, with tweaks still to come.
  Resume, Retreat and Pause should get more room, and the pause screen may
  carry more information. The on-screen key/controller hints were liked; a
  similar hint treatment could later extend to the HUD (it needs more
  textures). The loot display is fine.
- **Options:** fine as a start, but more menus are needed beyond the game's
  four bars, e.g. camera and display, alongside control configuration and
  volume. PC settings stay separate from the game's options.
- **Solo hall:** in-scene signposts accepted; the final version should be more
  interactive than the static frame.
- **Chapters:** list/detail is acceptable, but preferred alternatives are
  either keeping the original map layout or a simple menu selection.
  Undecided.
- **Fiend's Cauldron:** fine. The cauldron must remain the centerpiece and
  stay directly interactive.
- **Gear inspection:** liked as is.
- **Fusion:** make it more interactive and make it unmistakable which weapon
  is fused with which, what the player currently owns and what results.
- **Power Board:** no changes requested; the saved-loadouts concept is also
  considered a good idea (still a concept, not approved as a rules change).

Agreed order: user reviews/tweaks the canvas, then in-game gameplay fixes,
then implementation of the canvas design.
