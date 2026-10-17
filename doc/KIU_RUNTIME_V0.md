# KIU Runtime v0: the boundary

The long-term goal is to run the recompiled game on a small runtime made
for Kid Icarus instead of on Zakuro. v0 is not a rewrite: it is a line drawn
through the current code, so that each side can change without the other.

```
recompiled KIU code (build/kiu-aot-o2, generated C)
        │  recomp ABI: Context, memory reads/writes, svc exits
        ▼
KIU Runtime v0   ← what we own and define
  ├─ execution     recompiled library, interpreter safety net, census
  ├─ kernel        threads, sync objects, timers, scheduling
  ├─ services      GSP, Y2R, FS/saves, HID, DSP, boot/offline stubs
  ├─ renderer      PICA command lists → Vulkan (Zakuro's GPU emulation)
  ├─ audio out     DSP mix → cpal
  ├─ input         keyboard, mouse, gamepad → HID + KIU hooks
  └─ presentation  PC interface, HUD, single screen (other workstream)
        ▼
PC (Windows, Vulkan, cpal, winit)
```

## Where the boundary sits today

| Layer | Today | Boundary |
|---|---|---|
| Game code ↔ runtime | the recomp ABI (`recomp-abi`, 3dsrecomp `17b8b6d`): a `Context`, memory callbacks, SVC exits | **stable**; it is the one interface the generated code knows. Never change it from our side. |
| Kernel calls | `zakuro-core/src/kernel/svc.rs` dispatch by number | the SVC numbers in the usage census are the contract (about 20 are used) |
| Services | `zakuro-core/src/services/mod.rs` dispatch by service name and command | the service/command pairs in the usage census are the contract (about 90 pairs, most at boot only) |
| GPU | GX commands and PICA registers into `zakuro-gpu` | the renderer interface: command lists, transfers, fills, swaps |
| Frontend | `zakuro/src/lib.rs` run loop, `present.rs`, `audio.rs`, `input.rs` | host services: a frame tick, a present, an audio sink, an input state |

## Rules for new work

1. **No title checks in generic code.** KIU behaviour goes in KIU modules
   (`kiu_ui/`, `kiu_jump.rs`, `memory/kiu_mouse.rs`, overrides in
   `tools/recomp/overrides/`), behind one switch, not `if title == KIU`
   spread through Zakuro.
2. **Prefer the recompiler's overrides to runtime hacks** for changing game
   behaviour: a C function replacing a game function is explicit, versioned
   and does not cost anything elsewhere.
3. **Measure before replacing.** The usage census says what a service is
   really used for; replace only what it shows.
4. **Keep the safety nets** (interpreter, census, hints) until every chapter
   has been played on a checked build.

## First steps (in order)

1. Census of real use — done (`usage.txt`, `interpreted.txt`).
2. Move the offline/boot stubs KIU needs into one `kiu` service profile, so
   the rest of Zakuro's service code can be ignored for this title.
3. Put the frontend's frame loop behind a small trait (tick, present, audio,
   input) so pacing experiments (see [60FPS_ANALYSIS.md](60FPS_ANALYSIS.md))
   do not touch the core.
4. Then filesystem/saves, input, Y2R and GSP, in the order of
   [ZAKURO_DEPENDENCY_CENSUS.md](ZAKURO_DEPENDENCY_CENSUS.md).
