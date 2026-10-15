# Equipped powers in memory (research, October 15)

Found with `Launch-KIU-RAM-Research.cmd` (F7 snapshots) and
`tools/recomp/ram_diff.py`, Practice Range > Land Battle, USA executable.
Purpose: Space jump (doc/PC_INTERFACE_DESIGN_DIRECTION.md, variant 2) and a
proper PC power HUD. Addresses are heap allocations from one session; code
must find the structure, never hard-code them.

## Palette structure (one session: 0x14F3C968)

```
+0x00  u32  count of equipped powers           7
+0x04  u32  selected palette slot (0-based)    0,1,2 as selection moved
+0x0C  8-byte entries, one per slot:
         u32  (slot << 16) | power id          0x00000000, 0x00010006, ...
         u32  four small values (meaning open) 0x0004070a, 0x00220302, ...
+0x70  u32  count again, then u8 display order 7, 00 01 02 03 04 05 06
```

Snapshots (frames 6490-10934): selection 0,0,0,1,2,1 matched exactly one
address. The list stayed constant while selecting and using powers.

Equipped that session (palette order): Sky Jump (id 0x00, shows 4 uses),
Idol Transformation (0x06), then ids 0x0F, 0x11, 0x32, 0x33, 0x3B
(Autoreticle / Weak-Point Reticle / others; names not yet matched to ids).

## Not found yet

- **Remaining uses.** The Practice Range never spends uses (Sky Jump stayed
  at 4 after three jumps), so the counter must be found in a chapter. The
  byte 0x04 in Sky Jump's entry equals its shown uses but Idol's entry has
  0x22 where 10 is shown, so it is probably not the counter. The practice
  mode's own "uses are not spent" rule is a lead for unlimited Space jumps.
- **Which code reads the selection.** Hooking that reader (like the land
  camera hook in `kiu_mouse.rs`) is the robust way to locate the structure.

## Plan for Space jump (variant 2: Jump equipped, Space invokes it)

1. Locate the palette each land session (code hook, or a signature scan:
   count <= 12, selected < count, entry high halves 0..count-1).
2. Space on land with Sky Jump equipped: remember the selection, select the
   Sky Jump slot, send the existing use press (held 3 frames), restore the
   selection. Nothing happens if Jump is not equipped.
3. Unlimited uses: after the counter is found, restore it after a Space jump
   (optional setting), never touching other powers.
4. Verify: Practice Range, then a chapter's land section; grounded only,
   no repeated mid-air jumps, scripted scenes unaffected.
