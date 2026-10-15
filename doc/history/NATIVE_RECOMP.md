# Native recompilation audit and direction

Date: 2026-10-06. This records the initial audit. Subsequent builds and runtime
results are in [RECOMP_EVALUATION.md](RECOMP_EVALUATION.md), which supersedes
the unimplemented/unavailable statements below.

## Decision

Pursue static recompilation, with selective reverse engineering to support it.
A full source decompilation is not a prerequisite. We need a correct ARM-to-host
translation path and a runtime for 3DS memory, threads, services, GPU, audio and
input. Recovering names for every game class or converting every model is not
on the critical path.

The preferred initial compatibility boundary is the 3DS system interfaces:
preserve original game and linked middleware code, supply its memory and OS
environment, and handle graphics commands/shaders in the host runtime. Replacing
NintendoWare resource APIs is a possible later optimization, not an assumption
that every parser in the existing research must become a runtime component.

This boundary is a proposed engineering direction, not yet an implemented runtime.

## What was actually inspected

- The supplied handoff, both Markdown notes, all three Word documents, the
  local format scripts, CSV schemas and saved research summaries.
- The extracted executable, ExHeader and ExeFS table, and the newly supplied
  2 GiB NCSD ROM's executable partition at `0x4000`.
- Repository state: no commits; some previously staged files have been moved.
  Existing index/work was preserved. A Ghidra project exists but was not opened
  or analyzed during this audit, honoring the earlier request to postpone it.
- ROM assets were counted; cached PSLBs and current physical EFF files were
  revalidated. This was not a complete reinspection of every graphics/audio
  payload or a rerun of every historic heuristic scan.

## Corrected project status

The old `Doc.md` and progress Word document call PSLB unknown. That is stale.
The handoff's `build_resource_graph.py` was missing from disk. It has now been
implemented and run. The historical `effectID_` class `0x08B0A34A` has 96 local
matches among 417 reference groups (23%), not universal resolution. Only its
actual local matches enter the graph. Class/key selection remains heuristic.

Fresh validation:

| Check | Result |
|---|---:|
| Cached PSLB parse/serialize | 5,084 exact, 0 failures |
| Physical EFF parse/serialize | 700 exact, 0 failures |
| Raw EFF trigger target section/type/index | 43,806 valid |
| Packaged graph nodes | 94,885 |
| Packaged graph edges | 55,882 |
| Dangling graph endpoints | 0 |
| ExeFS code SHA-256 vs header | Match |
| ROM `.code`, ExHeader, ExeFS table vs extraction | Exact match |

Graph relations: 1,553 PSLB-to-CGFX, 3,441 EFF-record-to-CGFX, 7,082
PSLB-to-EFF-trigger, and 43,806 EFF-trigger-to-record. These are edge counts,
not unique effect counts or execution coverage. 2,364 other local-match rows
remain candidate-only. Internal EFF wiring is structural; cross-format links
are labelled `heuristic-high` rather than proven engine behavior.

The RomFS tree also contains 700 `.txt` files alongside 700 `.bin` files; earlier
tools could write reports beside assets. Do not assume the working extraction
is a pristine install source. Use the original ROM for future installation.
Do not delete the reports as part of this audit.

## Executable baseline

| Property | Verified value |
|---|---|
| Product | `CTR-P-AKDE` |
| Program ID | `0004000000030100` |
| Process name | `apollo` |
| Code file | `ROM/gameFiles/ExeFS/code.bin` |
| Code length | 12,992,512 bytes (`0xC64000`) |
| Code compression flag | Clear |
| Entry point | `0x00100000`, first instruction is ARM BL |
| First called routine | `0x00100024` |
| Stack size in ExHeader | `0x8000` |
| BSS | `[0x00D63C78, 0x00F35D28)` |

SHA-256:
`2718aa2077a29560208c4e499288e5fecc4446d7adec95efb91ebf1b19eda679`

| Segment | Guest address | File offset | Logical bytes | Page allocation |
|---|---:|---:|---:|---:|
| text | `0x00100000` | `0x00000000` | `0x00B950F0` | `0x00B96000` |
| rodata | `0x00C96000` | `0x00B96000` | `0x0009B990` | `0x0009C000` |
| data | `0x00D32000` | `0x00C32000` | `0x00031C78` | `0x00032000` |

File offsets use page allocations, not logical section sizes. BSS begins at
the logical data end, as independently confirmed by the startup literals.
The audit reads the service permission list, including `fs:USER`, `gsp::Gpu`,
`hid:USER`, and `dsp::DSP`; permissions do not prove the game calls a service.
No loose `.cro`, `.crr`, or `.crs` files were found by extension. This does not
rule out embedded, differently named or dynamically generated code.

### Native probe result

`tools/recomp/startup_probe.py` recognizes the first seven-instruction routine,
specializes it to C++, and rejects unsupported sequences. The compiled probe
cleared 1,908,912 bytes using 477,228 word stores, returned to `0x00100004`,
and passed checks for the live registers/carry and all other memory remaining
unchanged. BSS was deliberately poisoned before execution to make a skipped
clear fail. The probe is a local 32-bit Windows executable built with available
MinGW GCC 6.3; it establishes no 64-bit production-toolchain compatibility.

This is a narrow semantic experiment, not automatic whole-program translation,
not a complete ARM CPU model, not differential validation against hardware,
and not game startup. Do not grow its seven-opcode template into an ad hoc
full translator. Evaluate the existing backend first.

## Existing technology evaluation

[XenonRecomp](https://github.com/hedge-dev/XenonRecomp) illustrates translation
to C++ with a separate runtime, but targets Xbox 360 PowerPC, not this ARM binary.
Its analysis also needs help with indirect control flow; copying its platform
assumptions would be inappropriate.

[3dsrecomp](https://github.com/fearkov/3dsrecomp) is a much closer experimental
candidate. Local checkout: `tools/3dsrecomp`, inspected commit
`17b8b6d2f5060ca86f25aed55e0d24eef46ec506`. It accepts NCSD/NCCH input,
discovers ARM/Thumb code, emits C, and integrates with Zakuro. Its optional
verification path compares compiled functions with the interpreter.

Its [standalone port mode](https://github.com/fearkov/3dsrecomp/blob/main/docs/port.md)
links generated code with Zakuro's kernel/services/GPU/audio runtime. That is
a useful bootstrap candidate. Interpreter fallback means success must be
measured as recompiled instruction coverage and correctness, not merely whether
a standalone executable launches. Uprising compatibility has NOT been established
here. The upstream README's compatibility claims are not local test results.

No upstream source has been modified or incorporated into the project's own
implementation. The manifests declare MIT for the recompiler; review runtime
and dependency licenses before integration/distribution.

Toolchain observations: Python 3.11 is available. The existing old MinGW compiler
works outside the sandbox (inside it fails with a DLL-relocation error). Neither
Cargo nor rustc was found on PATH or in the usual user Cargo bin directory.
The upstream project requires Rust 1.88+ and a suitable matching C toolchain.
Consequently its analyzer/build/runtime have not been run yet. No Rust or
system-wide compiler was installed in this audit.

## Next work, in order

1. Provision a current, matching Windows Rust/C toolchain, preferably isolated.
   Build the pinned `3dsrecomp` checkout and run its tests, then `analyze` on
   the verified ROM. Record discovered code, ARM/Thumb modes, literals, unresolved
   branches and unsupported instructions. Analysis coverage is not execution coverage.
2. Generate and compile its C into ignored `build/kiu-aot`. Use its differential
   verification mode on startup and representative integer/VFP/memory/control-flow
   cases. Fix divergences before trying to solve them with resource substitutions.
3. Evaluate Zakuro with this exact ROM and a separate test-save directory. Log
   startup, SVC/IPC calls, first unsupported operation and interpreted fallbacks.
   Then compare baseline runtime execution against AOT execution. Any unsupported
   feature should stop with a trace rather than fake a success result.
4. Reach progressively: startup past memory initialization, first meaningful
   filesystem/service operation, first graphics submission, first rendered frame,
   title screen, then a playable chapter with audio/input. Keep explicit pass
   criteria and traces for each.
5. Reduce fallback coverage and add game-specific patches with hash/version guards.
   Build a user-ROM preparation/launch workflow. Package only project sources,
   translation rules, metadata and runtime code eligible for redistribution;
   generate game-derived C and binaries locally.

If the existing backend proves unsuitable, use its evaluation results to select
or implement an ARMv6/Thumb/VFP translation backend. Preserve 32-bit guest
addresses, ARM PC semantics, CPSR, interworking, guest memory permissions,
atomic operations and indirect branches. Do not presume a linear instruction
sweep can distinguish code from literal pools.

The immediate next milestone is **a tested upstream analyzer/translation build
on this ROM**, not another asset-format investigation. No playable-port ETA is
supported by the current evidence.

## Reproduction and evidence

The root README contains executable-audit and native-probe commands. Reports:

- `doc/stuff/EXECUTABLE_AUDIT/executable.json`
- `doc/stuff/EXECUTABLE_AUDIT/pslb_roundtrip.txt`
- `doc/stuff/EXECUTABLE_AUDIT/eff_roundtrip.txt`
- `doc/stuff/KIU_RESOURCE_GRAPH/resource_graph_summary.txt`
- `build/startup-probe/probe.json`

Graph packaging:

```powershell
python tools/formats/pslb/build_resource_graph.py doc/stuff/RESOURCE_GRAPH_REFINED/direct_graphics_edges_ranked.csv doc/stuff/EFF_GRAPH_REFINED/strong_local_eff_to_cgfx_edges.csv doc/stuff/PSLB_EFF_CLASS_CONTEXT/pslb_eff_class_context_detail.csv --romfs ROM/gameFiles/RomFS --output doc/stuff/KIU_RESOURCE_GRAPH
```

After installing compatible toolchains, upstream evaluation commands are:

```powershell
cargo test --manifest-path tools/3dsrecomp/Cargo.toml
cargo build --release --manifest-path tools/3dsrecomp/Cargo.toml
./tools/3dsrecomp/target/release/3dsrecomp.exe analyze "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds"
./tools/3dsrecomp/target/release/3dsrecomp.exe build "Kid Icarus - Uprising (USA) (En,Fr,Es).3ds" build/kiu-aot
```

These upstream commands are a next-step recipe, not commands already validated
on this machine.

Header/layout cross-checks used the public
[Azahar NCCH structures](https://github.com/azahar-emu/azahar/blob/master/src/core/file_sys/ncch_container.h)
and [loader implementation](https://github.com/Lime3DS/Lime3DS/blob/master/src/core/loader/ncch.cpp),
alongside [3dbrew's ExHeader documentation](https://www.3dbrew.org/wiki/Exheader).
The new audit is independently written; those sources were consulted for format
layout, not copied into it.
