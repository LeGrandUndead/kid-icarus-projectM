# Relative mouse investigation

Executable: USA code SHA-256
`2718aa2077a29560208c4e499288e5fecc4446d7adec95efb91ebf1b19eda679`.

## Observed path

Native guarded-read traces in `build/evaluation/touch-reader/run.log` locate
the HID reader at `0x16572C`, called by `0x14D06C`. The shared touch ring starts
at `0x100000A8`. The input manager `0x12D150` requests the sample into its
object at `0x00F2F260 + 0x308`.

The manager's ARM instructions distinguish these fields:

| Object offset | Observed use |
| --- | --- |
| 0x308 / 0x30A | unsigned 16-bit touch coordinates |
| 0x30C | touch held flag |
| 0x310 / 0x314 | signed movement since the previous sample |
| 0x318 / 0x31C | absolute magnitudes of that movement |
| 0x360 / 0x364 | prior coordinates used for subtraction |
| 0x368 / 0x36C | internal signed movement |
| 0x370 / 0x374 | last nonzero movement used for one-unit reversal filtering |
| 0x378 | previous touch-held state |

Function `0x1317E8` copies 0x25C bytes starting at object+0x104 into a gameplay
snapshot through `0x425F00`. A second guarded-read test at `0xF2F570` confirms
this consumer at runtime (return address `0x13180C`). The synchronous context
PC identifies the native function boundary, not the precise load instruction.

`python tools/recomp/inspect_kiu_input.py` recreates the disassembly using the
project-local Capstone package. Derived game code/output remains under `build`.

## Rejected upstream hooks

Replacing SDK deltas, converted UI deltas, first gameplay velocity, or signed
gameplay positions did not change the fixed-edge land replay's final image.
Memory dumps confirmed writes reached those fields, but that was insufficient
evidence of a camera fix. Those implementations have been replaced, not stacked.
Their local evidence remains under `build/evaluation`.

The positive control, `camera-positive-control`, oscillates real touch coordinates
inside the screen and does move the land view. The fixed-edge replay holds guest
touch at (319,120), with raw mouse dx=4 for frames 1200..2199. This separates
camera motion from changes to the touchscreen position.

## Actual player camera path

`0xA41898` builds a second gameplay control state through `0x60FDA0`, then
`0xA275BC` exports it. In this executable its exported xy is `0xEFD4D4`.
`0x610524` / `0x60A094` append samples to the active player's touch ring.
Each 20-byte sample has press/held/release bytes, float xy, then float velocity.

`0x4DB974` reads that ring into a camera touch object. Observed offsets:

| Offset | Meaning observed in instructions |
| --- | --- |
| 0x1C | sensitivity branch selector; 1 in the land practice replay |
| 0x20..0x2C / 0x30 | two motion-history pairs and count |
| 0x34 / 0x35 | held / end-of-drag state |
| 0x38 | accumulated sample duration |
| 0x3C / 0x40 | current float xy |
| 0x44 / 0x48 | previous float xy |

At `0x7DABB0..0x7DABE4`, the camera subtracts previous from current, divides by
duration and applies sensitivity. The native synchronized context at this read
is `0x7DAB54` in the observed land branch. This is the first identified consumer
that directly calculates camera movement, rather than an earlier input copy.

## Current implementation

The normal launcher enables `--relative-camera`; `--original-land-camera` opts out.
The hook discovers the active ring and camera from those verified
native calls; heap addresses are not hardcoded. Immediately before the observed
land calculation, it keeps current xy intact and sets previous xy to current
minus raw mouse movement. It supplies the sampling duration and clears the
two-sample history so idle input cannot reuse an older nonzero swipe.

Other sensitivity branches, uncaptured input and unknown executable signatures
are excluded. Pending movement is bounded to three display samples while the
consumer is inactive. Capture loss clears discovery and queued motion. Full
chapter transitions and subjective feel still need gameplay validation; this
is not a redesigned camera rig, wider field of view or changed pitch limits.

Normal input replay does not encode this hook. Replay validation pairs the
original guest replay with its raw mouse CSV and initial save snapshot; the
headless runner uses `KIU_MOUSE_TRACE_REPLAY` for this purpose.

`tools/recomp/probe_kiu_camera.py` runs isolated replays with copied initial saves,
optional address watches and memory dumps. It refuses to overwrite an existing
evaluation directory and records executable/replay hashes and screen hashes.

## Validation, 2026-10-07

- `direct-camera-relative`: 2,200 frames, 752 camera updates; fixed touch xy
  (319,120), continued raw rightward motion changes the rendered land view.
- `direct-camera-reversal`: identical guest input with raw motion enabled only
  after frame 1200. Rightward motion until 1600, idle until 1800, leftward motion
  until 2200. 500 updates; captured views show turning, stable view during idle,
  and reversed turning. The visible cursor never wraps or releases.
- `flight-confirm-baseline` and `flight-confirm-relative`: 2,300 frames each,
  explicitly entering Air Battle practice. The relative run makes **zero**
  camera writes. Top and bottom framebuffers at 1700, 1900, 2100 and 2300 are
  byte-for-byte identical (`comparison.json`). This validates the tested air
  sequence, not all chapters or every possible control configuration.

These checks use copied saves, the O2 native library and hardware rendering.
They are behavioral checks, not a controlled performance benchmark.

The final source also passes 10 core memory tests (including camera guards,
fractional motion, capture loss, inactive backlog and GPU read/write coherence)
and 35 frontend tests, including directional Shift input and held-touch edges.
