# Next project milestone: complete PC gameplay

**October 10 experimental update:** `Launch-KIU-Experimental.cmd` provides a separate 1080p/wider-view build and relative flight aiming with the guided camera retained. It uses copied saves and independent settings. HUD asset detail, complete widescreen coverage and menu transitions remain under validation. See [experimental setup and limitations](PC_PRESENTATION.md).

The October 9 rendering build fixes the verified land-resolution fallback and
shared-font mismatch. Controls were deliberately left unchanged during that work.
The user wants to revisit controls and bottom-screen features before moving on.

## 1. Accept the rendering baseline

Check the corrected land scene and dialogue/menu lettering through Launch-KIU.
Keep the current executable and isolated recording as regression references.
Original low-resolution textures and bitmap UI remain original assets; sharp
geometry does not imply an HD texture pack. See [rendering status](RENDERING_STATUS.md).

## 2. Controls and bottom-screen functionality

The user identified these priorities on October 9:

1. Implemented October 9: E uses the equipped land power; 1/3 select powers,
   with mouse capture and aim maintained. No synthetic Z or pointer transition.
   Isolated gameplay replays verified Sky Jump and Autoreticle use/charge counts.
2. Implemented October 9: E triggers the air special, verified by a consumed
   charge in the recorded flight scene. All three aliases are rebindable.
   Because they send native D-pad actions, 1/3 also trigger the special in flight.
   Next: human gameplay check of convenience and remaining touch interactions.
3. Later, investigate adding free jump to Pit's basic land moveset, preferably
   Space. This is a gameplay modification requiring investigation of movement,
   animation, collision and level behavior, not just an existing-action remap.

Old reports about F3, inverted dashes or
mouse edges describe earlier revisions; do not assume all remain broken now or
reapply old patch packs. Test flight aiming/dodging, land movement/dashing/camera,
capture release/resume, menus and transitions separately. Preserve working behavior
with paired recorded tests and human feel checks.

Inventory bottom-screen interactions as working, awkward, missing or untested.
Separate combat actions, menu actions and display-only information. The exact
list starts with the reported item/power workflow above; other game features
should be audited rather than assumed missing.

Current implementation: uncaptured pointer clicks can reach the bottom screen;
captured mouse motion supplies aiming touch and left click attacks. There is no
complete dedicated PC replacement for the bottom-screen interface. Determine
which actions need bindings, a temporary pointer mode, or an overlay. Entering and
leaving UI interaction must not jump the camera, fire accidentally or leave input
held. Keep the original bottom screen available until replacements cover its
required functionality. Check controller behavior too.

## 3. Complete gameplay checks

Validate complete chapters, flight-to-land transitions, touch actions, menus,
pause/resume, death/retry and saving. Track remaining renderer issues such as
geometry mode 2 separately from control bugs. Use copied saves for automated tests.

## 4. PC presentation

User selected presentation over reticle/free-jump work for the next pass. A
reversible 1080p window profile and Tab bottom-screen interaction are implemented;
true 16:9 world-camera rendering remains open. See [PC presentation](PC_PRESENTATION.md).

After the actions and controls work, implement true widescreen projection and
audit culling/effects. Then combine the top/bottom information into a PC HUD with
clear interaction and scaling. Avoid designing away access to a required action.

## Performance throughout

Measure each candidate on the same scene, resolution, font and initial cache,
without simultaneous builds or game instances. Preserve the working path when
an experiment does not improve results. The October 9 CPU-copy and GPU-blit
experiments were both rejected; they are not shipped optimizations. Further work
should profile costly readbacks and frame-time spikes rather than blindly
increasing thread counts or memory use. Higher internal resolution is a workload
choice: 5x provides 2000x1200 while 8x provides 3200x1920; saved preferences remain
unchanged.

Independent recompiler research remains available in `recompiler`, but replacing
the working execution backend is not a prerequisite for these gameplay fixes.
