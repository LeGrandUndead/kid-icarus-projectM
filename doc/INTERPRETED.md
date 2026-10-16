# What still runs in the interpreter

The game's ARM code is compiled ahead of time by 3dsrecomp into
`build/kiu-aot-o2/0004000000030100.dll`. Whatever the library has no code
for runs in Zakuro's interpreter instead. The title bar shows the share, and
the runtime writes two files next to the library while you play:

- `0004000000030100.interpreted.txt`: the census, how many instructions ran
  interpreted and from where;
- `0004000000030100.hints`: every place the interpreter had to take over,
  which the next build takes in as extra function starts.

## Before (library of October 6, census of October 16)

70.98 billion instructions measured over the play sessions since the hints
were added:

| Kind | Instructions | Share |
|---|---|---|
| missing code | 648 million | 0.913% |
| budget rests | 0 | 0% |
| fallbacks (instructions the library hands back) | 0 | 0% |

So the library already handles every instruction it has; the whole
remaining share is code 3dsrecomp's analysis never found.

99.99% of that is one 28 KB block of hand-written assembly at
`0x005F1000`-`0x005F8000` (by address: `0x5F3xxx` 0.43%, `0x5F6xxx` 0.16%,
`0x5F5xxx` 0.16%, `0x5F4xxx` 0.09%, `0x5F1xxx`/`0x5F2xxx` 0.06%). It is a
decoder-style routine that jumps through relative jump tables
(`ldr r7, [r6, r12, lsl #2]; add pc, r6, r7`), sets return addresses by hand
(`add lr, pc, #12`) and picks branches with computed `mov pc, r4`. A static
analysis cannot follow those jumps, so every piece reached through them was
missing. The rest (about 11,500 instructions) is a few small spots at
`0xC51xxx`, `0xB75xxx`-`0xB83xxx`, `0x950xxx` and `0x71Fxxx`.

All 185 places in the census are in the hints file (83,490 addresses).

## The rebuild

`tools/recomp/Rebuild-KIU-With-Hints.ps1` (started by `Rebuild-KIU.cmd`):

1. copies the hints to `%APPDATA%\3dsrecomp` (the project's
   `build/user-data/roaming`), where 3dsrecomp reads them;
2. regenerates the C with the same 3dsrecomp (`17b8b6d`, the revision the
   runtime's `recomp-abi` is pinned to, so the runtime needs no change);
3. compiles it with `compile_generated.py` (6 jobs, -O2, about two hours);
4. swaps the new library in, keeps the old one as
   `build/kiu-aot-o2-previous`, and runs a 300-frame headless smoke test,
   swapping back if it fails.

## What can't reach exactly 0%

- Code no play session has run yet (other chapters, menus or cutscenes that
  go through the same jump tables differently) is only found once it has
  run once; play adds it to the hints, and the next rebuild covers it.
- Nothing else is known to be interpreted: the census shows no fallbacks
  and no budget rests.

## After

See the results section below, filled in after the rebuild.
