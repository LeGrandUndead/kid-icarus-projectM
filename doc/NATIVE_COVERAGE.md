# Native coverage

How much of Kid Icarus: Uprising's ARM code runs as compiled native code,
and what (if anything) still goes through Zakuro's interpreter.

## How it is measured

The runtime counts every guest instruction by where it ran and writes
`build/kiu-aot-o2/0004000000030100.interpreted.txt` next to the library
(every minute and on exit). Three kinds of interpreted instructions are
counted separately:

| Kind | Meaning |
|---|---|
| missing code | the library has no code at that address (3dsrecomp never found it) |
| budget rests | the library has the code, but a block was cut short by the scheduler's instruction budget and the interpreter finished it |
| fallbacks | compiled code handed one instruction to the interpreter (an instruction the code generator does not translate) |

Source: `tools/zakuro/crates/zakuro-core/src/hints.rs` (`report`),
`recompiled.rs` (`fallback_sites`), `lib.rs` (step loop).

## Current result (library of October 17)

Session played right after the rebuild (October 17, 00:35-00:51):

```
# interpreted instructions by kind (of 31658384561 run)
missing code   0 (0.000%)
budget rests   0 (0.000%)
fallbacks      0 (0.000%)
```

**0 of 31.66 billion instructions were interpreted.** For everything that
session reached, the game ran entirely as native code.

Before the rebuild (library of October 6, 70.98 billion instructions over
several sessions): 0.913% interpreted, all of it "missing code" in one
hand-written decoder block at `0x005F1000`-`0x005F8000` reached through
computed jumps. See [INTERPRETED.md](INTERPRETED.md) for how that was fixed
(hints plus entry-point overrides in
`tools/recomp/overrides/kiu-entry-points.c`).

## What is left

| Item | Kind | Frequency | Status |
|---|---|---|---|
| Code paths no session has reached yet (other chapters, menus, cutscenes) | possibly missing code | unknown until played | the census and hints record them; `Rebuild-KIU-With-Hints.ps1` covers them |
| New entry points inside known functions (like the decoder's) | missing code | none seen since the rebuild | add the address to `kiu-entry-points.c`, then rebuild |
| Instructions the code generator hands to the interpreter | fallback | 0 measured | none known |

No startup-only, service-related or exception-path interpretation was
measured.

## What a genuinely standalone native build needs

Native coverage of the game code itself is no longer the obstacle. What
still ties the game to Zakuro is everything around the code: the kernel and
services it calls, the PICA200 GPU emulation and the DSP audio emulation.
That is the subject of [ZAKURO_DEPENDENCY_CENSUS.md](ZAKURO_DEPENDENCY_CENSUS.md).

Keeping the interpreter as a safety net costs nothing while it is unused, so
it should stay until every chapter has been played on a census-checked
build.

## Checking it again

1. Play with `Launch-KIU.cmd`.
2. Read `build/kiu-aot-o2/0004000000030100.interpreted.txt`.
3. If anything shows up under "missing code", run `Rebuild-KIU.cmd`
   (`tools/recomp/Rebuild-KIU-With-Hints.ps1`); run starts that sit inside
   known functions also need a line in `kiu-entry-points.c`.
