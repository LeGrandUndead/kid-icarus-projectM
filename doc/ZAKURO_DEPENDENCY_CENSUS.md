# Zakuro dependency census

What Kid Icarus: Uprising actually needs from Zakuro, so that "Zakuro is a
giant dependency" becomes a list of concrete capabilities that can be
replaced one at a time.

## How it is measured

The runtime records what the game asks for and writes
`build/kiu-aot-o2/0004000000030100.usage.txt` next to the library (every
minute and on exit): every service request by service and command, every
kernel call (SVC) by number, every GPU (GX) command, buffer swaps, and host
frame times. Source: `tools/zakuro/crates/zakuro-core/src/usage.rs`.

Numbers below marked *startup sample* come from a 106-second run of boot,
the opening movie and the title screen (October 17). Gameplay numbers are
added from longer sessions as they are recorded.

## Summary

The game's *code* no longer depends on Zakuro (0% interpreted, see
[NATIVE_COVERAGE.md](NATIVE_COVERAGE.md)). What it depends on is the 3DS
around it:

1. **The PICA200 GPU** — by far the largest and hardest dependency. Every
   frame the game queues about five command lists, a memory fill and a
   display transfer per screen it draws.
2. **The kernel** — threads, events, mutexes and address arbiters. About 50
   `SleepThread`, 20 `ArbitrateAddress` and 8 `WaitSynchronizationN` calls
   a frame: the game is a multi-threaded program and Zakuro's scheduler
   runs those threads.
3. **The DSP (audio)** — HLE: voices, mixer and the AAC decoder.
4. **A handful of services** — GSP (GPU control), Y2R (video colour
   conversion), FS (RomFS and saves), HID (input), APT, CFG and a few
   online services that only need to answer "offline".

Most of the remaining service list is called a few times at boot and never
again.

## By area

Columns: what KIU uses · where it is implemented · importance · frequency ·
KIU-specific or generic · already ours? · easy to own? · notes.

### GRAPHICS (PICA200 GPU emulation)

- **Uses:** command lists (≈4.9 a frame), memory fills (≈1.5), display
  transfers (≈1.5), cache flushes; vertex and geometry shaders, including
  the geometry shader's fixed-size primitive (particle) mode; TEV combiners,
  fragment lighting, fog, procedural textures, shadow/depth reads; render to
  texture.
- **Where:** `zakuro-gpu` (renderer: `raster.rs`, `raster/hardware.rs` —
  Vulkan; shaders: `shader/`; texture decode: `texture.rs`).
- **Importance:** critical. **Frequency:** every frame.
- **Generic** emulation, with KIU-specific layers added: the PC interface
  (`kiu_ui/`), HUD replacements (`replacements.rs`), the experimental wide
  projection and HUD anchoring in `raster.rs` (`kiu_wide_shader`,
  `kiu_hud_*`).
- **Ours?** The KIU layers are; the PICA emulation is upstream Zakuro.
- **Easy to own?** No. This is the core of any future runtime and stays
  emulated (PICA command lists to Vulkan) for a long time; a native renderer
  would require reverse engineering the game's own render code.
- **Known gaps:** geometry shader mode 1 (variable-size primitives) is not
  implemented (never seen in KIU so far); mode 2 was missing until
  October 17 (about 3,200 particle draws a session were dropped).

### GPU SERVICES (gsp::Gpu)

- **Uses:** `TriggerCmdReqQueue` (0x000C, ≈12.9 a frame — every GX command
  goes through it), `FlushDataCache` (0x0008, ≈0.55), register writes at
  boot, `SetLcdForceBlack`, `RegisterInterruptRelayQueue`, `AcquireRight`.
  Buffer swaps come through shared memory (FrameBufferInfo), ≈0.5 a frame
  for each screen in the startup sample.
- **Where:** `zakuro-core/src/services/gsp.rs`.
- **Importance:** critical, but small: a dozen commands.
- **Easy to own?** Yes — it is a thin layer between the game and the GPU
  renderer, and the first candidate for a KIU runtime interface.

### VIDEO (y2r:u)

- **Uses:** a full YUV→RGB setup every movie frame (commands 0x0010-0x0012,
  0x0018, 0x0026-0x0028, about one set a frame while a movie plays).
- **Where:** `zakuro-core/src/services/y2r.rs` (CPU conversion).
- **Importance:** needed for every movie and cutscene video. The movie
  decoder itself is the game's own code (the hand-written block at
  `0x5F1000`, now native).
- **Easy to own?** Yes: a self-contained conversion.

### AUDIO / DSP (dsp::DSP)

- **Uses:** firmware load at boot (the HLE path replaces it), the pipe
  protocol, semaphore events, AAC decoding through the binary pipe, voices
  and the final mixer, every 4.9 ms of guest time.
- **Where:** `services/dsp.rs`, `dsp_voices.rs`, `dsp_mixer.rs`,
  `dsp_aac.rs`; output in `zakuro/src/audio.rs` (cpal).
- **Importance:** critical for sound; timing-sensitive (the opening froze
  until the audio frame ran every 4.9 ms).
- **Easy to own?** Medium: self-contained, but it emulates a protocol, not
  KIU's own sound system. A native sound path would mean hooking the game's
  sound library instead.

### INPUT / HID (hid:USER)

- **Uses:** shared-memory input (buttons, circle pad, touch), `GetIPCHandles`
  once. The PC controls feed this shared memory, plus the KIU mouse camera
  (`memory/kiu_mouse.rs`, writing the game's own camera input).
- **Where:** `services/hid.rs`; PC side `zakuro/src/input.rs`,
  `gamepad.rs`, `kiu_jump.rs`.
- **Importance:** critical. **KIU-specific** parts already ours.
- **Easy to own?** Yes. The PC input layer is already ours; HID is a small
  shared-memory format.
- **ir:USER** (Circle Pad Pro): probed at boot, always "nothing attached".

### FILESYSTEM (fs:USER, FSFile, FSDirectory)

- **Uses:** RomFS reads from the cartridge image (`FSFile` Read 0x0802 is
  the most frequent file call), the save archive, a few `OpenFile` /
  `OpenArchive` / `GetSize` calls.
- **Where:** `services/fs.rs`, `host_archive.rs`, `zakuro-fs` (NCSD, NCCH,
  RomFS parsing).
- **Importance:** critical. **Generic.**
- **Easy to own?** Yes. Reading RomFS from the user's dump and keeping saves
  in a folder is simple and well specified.

### SAVE DATA

- **Uses:** the game's own save archive, kept as a directory on the host
  (`build/user-data/gameplay-preview/kiu`). The save format is the game's
  and is never changed.
- **Where:** `host_archive.rs`.
- **Easy to own?** Yes, together with the filesystem.

### MEMORY

- **Uses:** `ControlMemory`, shared memory blocks (GSP, HID, APT font),
  64 MiB of application memory, linear memory for the GPU.
- **Where:** `zakuro-core/src/memory/`, `kernel/svc.rs`.
- **Importance:** critical; the recompiled code reads and writes guest
  addresses through it.
- **Easy to own?** Medium. The address space itself is simple, but the GPU
  synchronisation hooks (writes the GPU drew) live here.

### THREADING AND SYNCHRONISATION (kernel)

- **Uses:** ≈17 threads, `SleepThread` (≈50 a frame), `ArbitrateAddress`
  (≈20), `WaitSynchronizationN` (≈8), events (`SignalEvent` ≈3.4,
  `ClearEvent` ≈6.4), mutexes, timers.
- **Where:** `kernel/mod.rs`, `thread.rs`, `sync.rs`, `svc.rs`; scheduling in
  `lib.rs` (`step`, `PREEMPT_INTERVAL`).
- **Importance:** critical. The game's threads run one at a time on one host
  thread, scheduled by guest cycle counts.
- **Easy to own?** Hard. This decides frame pacing and determinism.
  Running the guest threads as real host threads would be a large design
  change; keep Zakuro's scheduler for now.

### TIMERS / CLOCK

- **Uses:** `GetSystemTick` (≈3 a frame), the shared page's date and time,
  kernel timers.
- **Where:** `kernel`, `memory/config.rs`.
- **Easy to own?** Yes, but tied to the scheduler's notion of time.

### SYSTEM SERVICES

- **APT:U** — boot sequence, a library applet started and closed twice at
  boot (0x406), the shared font. Small.
- **cfg:u** — language, region, user name: a handful of reads at boot.
- **srv:** — service lookups at boot.
- **ptm:u, ndm:u** — battery/network-daemon queries at boot.
- **err:f** — never called in the samples.

All of these are boot-time and simple: easy to own as fixed answers.

### OTHER 3DS SERVICES (online and console features)

- **boss:U (SpotPass)** — registers tasks (≈0.02 calls a frame).
- **cecd:u (StreetPass)** — probed at boot; two commands unimplemented and
  answered with a warning.
- **frd:u (friends)** — offline answers.
- **nfc, ldr:ro** — not used (no CRO modules).

These only need to keep answering "offline". StreetPass/SpotPass content
(weapon gems, idols) is a future feature question, not a runtime dependency.

### INTERPRETER / FALLBACK

- **Uses:** none in the October 17 gameplay session; new paths (opening
  movie, title) showed up at 0.02% in the startup sample and are now in the
  hints file for the next rebuild.
- **Where:** `zakuro-cpu` (ARM/Thumb/VFP interpreter), `recompiled.rs`.
- **Keep** as a safety net; it costs nothing while unused.

### DEBUG / EMULATOR-ONLY INFRASTRUCTURE

The library screen, game picker and recompile jobs (`library.rs`,
`recompile.rs`, `menus.rs` parts), the report generator (`report.rs`),
input traces and replays (`input_trace.rs`, `replay.rs`), RAM snapshots,
the render capture (`diagnostics.rs`), the software rasterizer path and
the OpenGL backend. None of this is needed by the game; most of it is
useful for development and should move behind a developer flag rather than
be deleted.

## Proposed migration order

Ownership first, replacement later: each step puts a KIU-owned interface in
front of a Zakuro implementation, so the implementation can be swapped
without touching the generated code.

1. **Online/console stubs** (boss, cecd, frd, nfc, ir, ptm, ndm, cfg, APT
   boot): fixed answers. Lowest risk.
2. **Filesystem and saves**: RomFS from the dump and a save folder.
3. **Input (HID)**: already mostly ours.
4. **Y2R**: self-contained.
5. **GSP**: a thin layer in front of the renderer.
6. **Audio (DSP HLE)**: self-contained but timing-sensitive.
7. **Kernel scheduling and timing**: only once frame pacing is understood
   (see [60FPS_ANALYSIS.md](60FPS_ANALYSIS.md)).
8. **The GPU emulation**: last. It stays the renderer of the KIU runtime
   for the foreseeable future.

See [KIU_RUNTIME_V0.md](KIU_RUNTIME_V0.md) for the boundary.
