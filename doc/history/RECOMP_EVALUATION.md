# 3dsrecomp evaluation and independent backend

Date: 2026-10-06. This continues `NATIVE_RECOMP.md`; it supersedes that document's
earlier statement that Rust and the upstream analyzer had not been installed/run.

## Reproducible environment

Everything is local to the project. Dot-source `tools/recomp/environment.ps1`.
No permanent PATH change or system-wide Rust installation was made.

- Rust stable 1.99.0, `x86_64-pc-windows-gnu`, installed with rustup's minimal profile.
- WinLibs GCC 16.2.0, x86_64 POSIX/SEH UCRT, MinGW-w64 14.0.0 r2.
  Download URL retained in `tools/toolchains/compiler-source.txt`.
- 3dsrecomp commit `17b8b6d2f5060ca86f25aed55e0d24eef46ec506`.
- Zakuro runtime commit `b21830f080ceb8607ca7ea25a39814aec5b32cb5` (0.2.15).
- The recompiler's locked verifier CPU dependency is an older Zakuro revision,
  `3e853d5a`; it must not be confused with the runtime revision above.

GCC's default-manifest linker spec mishandled the space in this workspace path.
A local compiler `specs` file omits the optional `default-manifest.o` insertion.
This changes only the downloaded project-local toolchain; it does not modify
the system MinGW installation. Original compiler archive is retained.

Upstream tests: 35 unit tests plus one documentation test passed before and
after the local verifier controls. `build/3dsrecomp-patched-tests.log` records
the latter. The frontend and headless runtime example both built successfully.

## Analysis findings

Same verified ROM/code identity as the initial audit:
`0004000000030100`, code SHA-256
`2718aa2077a29560208c4e499288e5fecc4446d7adec95efb91ebf1b19eda679`.

`build/kiu-analysis.log` reports:

- 50,896 candidate functions; 1,114 candidates classified as Thumb.
- 93.6% of the text region classified as code, 4.2% literals, 2.2% unreached.
- 29,761 indirect sites, 962 switches, 775 SVC sites, 1,022 dead ends.
- 4,705,715 decoded instructions, counting shared instructions per function.
- No discovered external CRO modules.

These are analyzer results, not proven function boundaries or execution coverage.
The pointer/scanning heuristics can misclassify data. Do not infer that 93.6%
of the game is correct or that the remaining 2.2% must all be missing code.

Generated output contains 925 MiB of C, 220 compilable translation units and
448,215 dispatcher entries. The initial default O2 build used 16 compiler jobs
and exhausted physical memory, causing heavy paging. It was stopped with its
generated files and completed objects preserved.

`tools/recomp/compile_generated.py` is our resumable build driver. It hashes
sources, headers, compiler and flags, verifies cached object hashes, compiles
with bounded concurrency, and links through a response file. The diagnostic
library uses O0 and six jobs after other large builds completed. This is our
build infrastructure; the game-wide C translation remains upstream's work.

## Built native game and observed limits

`build/kiu-aot-debug/0004000000030100.dll` is a completed 220-unit O0 build,
1,254,759,386 bytes. SHA-256:
`bf50e091e2d8455e3717d34be288c82854e9d5f53c1ad7ec3c9b487b6468ffe0`.
Its build manifest is next to the DLL. The frontend and headless example load it.

Recorded native runs under `build/evaluation`:

| Run | Evidence | Interpreted instructions |
| --- | --- | --- |
| `aot-60-20261006-065815` | Loading screen, completed 60 frames | 0.04% |
| `aot-1800-20261006-065837` | Demonstration playback, completed 1,800 frames | 1.31% |
| `aot-600-20261006-065851` | Vulkan rendering, extra-data prompt | 0.02% |
| `aot-controlled-1800` | File-selection screen | 0.09% |
| `aot-file1-3000` | Save creation, main menu, tutorial playback | 1.43% |
| `aot-chapter-4200` | Tutorial continues, no proven campaign entry | 1.92% |
| `aot-chapter-6000` | Completed 6,000 frames, tutorial continues | 1.87% |

Directory names containing `chapter` describe the test objective, not success.
Scripted Start presses did not leave the tutorial in these runs. Investigate
input sampling and compare the same sequence against the interpreter before
blaming translation. Headless input pulses currently last only six guest frames.
Tutorial/demo imagery must not be presented as proof of playable campaign.

The 2,400-frame campaign attempt also wrote stereo audio: 1,308,320 frames at
32,728 Hz, with nonzero samples and peak magnitude 19,227. This proves audio
output exists, not that it sounds correct. Saves were written in isolated test
directories; the normal launcher uses separate persistent data.

Differential verification initially completed 100 samples (58 returned, one SVC,
41 instruction-limit cases, zero mismatches). Expanding to 500 overflowed the
Windows main thread stack with this O0 DLL. An explicit 64 MiB verification
worker stack completes the same 500 samples: 303 returned, 15 SVC, 181 stuck,
one stopped otherwise, zero reported mismatches; 10,840,211 native instructions
and no native-side fallback. Limit-exhausted samples are not state-verified.
This isolates the verifier's stack-capacity problem; the game runtime stack has
not been changed, and deep native call chains remain a runtime risk to test.
`KIU_VERIFY_TRACE=1` records each sampled address. The checked-in patch includes
the worker, trace switch, instruction-limit control and mismatch failure status.

Next engineering gate: establish interactive chapter entry, aim/movement/attack,
pause and save/reload against the interpreter baseline. Then optimize the DLL
and extend our backend using measured instruction coverage and exact state tests.
More memory can enable additional compiler workers, but the initial 16-way O2
build already caused paging on this machine; six workers completed the O0 build.

## Interpreter baseline

Runs use a fixed guest clock (`4000000000000` milliseconds since 1900), separate
test directories, and the software rasterizer. The first exploratory 60-frame
run created `user/` at the project root; this local test data is ignored by Git.
Later runs keep all test saves and captures under `build/evaluation/`.

- 60 frames: completed; 14 threads; 42 draws; loading indicator rendered.
- 600 frames: completed; 15 live threads; 2,318 draws; "Created Extra Data" prompt.
- 1,800 frames with the upstream automated menu input: completed; 27,219 draws;
  captures show the Light vs. Dark demonstration and its explanatory lower screen.

The last run took 239.21 seconds while compilation was competing for resources;
it is not a fair performance benchmark. The demonstration capture is not proof
of playable campaign gameplay or working multiplayer.

Missing commands recorded in that run: `cecd:u` 0x0009/0x0012 and `frd:u` 0x001D.
The friend service reports offline status. Do not silently turn missing calls
into success just to advance boot.

## Our independent backend

`recompiler/arm32.py` performs independent A32 field decoding and C lowering
for a strict initial subset. Its output targets the shared ABI 4, with the
upstream header supplying memory access helpers. It is not a renamed copy of
3dsrecomp and it is not a whole-game translator. See `recompiler/README.md` for
supported instruction forms and unimplemented architectural behavior.

Evidence:

- 352 compiled native state checks passed, including independently calculated
  signed-overflow/carry cases, every ordinary condition code under all NZCV
  combinations, predicated memory writes, branches and SVC exit behavior.
- Unsupported instruction encodings are rejected during generation.
- KIU's complete BSS-clear routine returned after 1,431,691 native instructions,
  with no interpreted fallback and no reported register/flag/memory mismatch
  against the upstream interpreter.
- A deliberately corrupted translation was rejected for wrong r2 and BSS
  memory contents; the verifier returned failure as required.
- Loading just our startup library into the runtime and running 60 frames
  produced a byte-identical top-screen PPM to the interpreter's frame 60.
  That run still interpreted 98.47% of instructions: it demonstrates integration,
  not a fully recompiled game.

The upstream verifier stops after 200,000 instructions by default, and skips
state comparisons for limit-exhausted cases. We added a bounded
`KIU_VERIFY_LIMIT` override and failure exit codes for mismatches; patch saved
as `tools/recomp/patches/verification-controls.patch`. The full startup test used
2,000,000. Never count "stuck" samples as verified successes.

The verifier also treats NaN differences specially, including certain memory
and integer-register bit patterns. Its results are useful evidence, not a proof
of all ARM semantics or hardware equivalence. The independent integer tests
compare exact expected bits.

## Commands

```powershell
. ./tools/recomp/environment.ps1
# Resume native-library compilation without repeating discovery/generation:
python tools/recomp/compile_generated.py build/kiu-aot build/kiu-aot-debug --jobs 6 --optimization 0
# Our backend's synthetic compiled tests:
python -m unittest discover -s recompiler -p 'test_*.py' -v
# Separate runtime evaluation directories are created on each invocation:
./tools/recomp/run_evaluation.ps1 -Mode interpreter -Frames 600
./tools/recomp/run_evaluation.ps1 -Mode aot -Frames 600
./tools/recomp/run_evaluation.ps1 -Mode aot -Frames 1800 -MenuInput
```

`Launch-KIU.cmd` is the preferred local experimental launcher (Python 3.11+).
It avoids the machine's PowerShell script restriction without changing policy.
It uses the user ROM,
checks executable identity and the built library hash, then launches Zakuro
with the compiled library and separate persistent saves. Interpreter fallback
is still allowed. `--interpreter` selects the baseline explicitly;
`--software` selects software graphics. `--headless 60` passed a frontend smoke
test with 0.04% interpreted instructions. Persistent saves are isolated under
`build/user-data/kiu`.

Generated C, objects, DLLs, test saves, screenshots and ROMs stay in ignored
local directories. This is not a redistributable game package.
