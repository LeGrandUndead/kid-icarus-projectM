# Kid Icarus: Uprising Reverse Engineering Notes

> Historical notes: PSLB status and next steps below are outdated. See
> [the current native recompilation audit](NATIVE_RECOMP.md) (2026-10-06).

## Goal

Understand the file formats and game code of Kid Icarus: Uprising
well enough to eventually investigate a PC recompilation/reimplementation.

---

## 1. ROM structure

Known major areas:

- ExeFS
  - `.code` — ARM game executable
- RomFS
  - game assets/data
  - ZRC archives
  - audio
  - models/textures
  - movies
  - etc.

---

## 2. ZRC format — SOLVED (outer container)

### Structure

`.zrc` files are:

    LZ11 compressed data
        ↓
    DARC archive

The compressed file may contain 0–31 bytes of padding after the LZ11
stream so that the file is aligned to 0x20 bytes.

### Evidence

Tested:

- 240/240 stage ZRCs successfully extracted
- 412/412 additional ZRCs successfully extracted
- 0 failures

Total tested so far: 652 ZRCs.

Example:

`stage/a0100.zrc`

Compressed:
- 2,026,400 bytes

Decompressed:
- 2,952,264 bytes

Decompressed header:

    64 61 72 63
    d  a  r  c

Valid little-endian DARC.

---

## 3. DARC archives

ZRC decompression produces a DARC.

Some files contained inside are themselves DARC archives despite
using the `.arc` extension.

Example:

    a0100.zrc
        ↓
    DARC
        ├── bin.arc
        ├── bind00.arc
        ├── emdl.arc
        ├── fmdl00.arc
        ├── json.arc
        ├── mdl.arc
        └── sound.snd

Therefore the current observed packaging hierarchy is:

    ZRC
     └── LZ11
          └── DARC
               └── ARC / resources
                    └── sometimes another DARC

---

## 4. Graphics

Known formats:

### BCRES / CGFX

BCRES files use the `CGFX` format.

Observed contents include:
- models
- materials
- textures
- skeleton/model-related data
- animations
- effects/particle-related data

Example:

    fmdl.arc
        ↓ DARC
    00.bcres
        ↓
    CGFX / CMDL model

EveryFileExplorer can recognize some of these resources but crashes
on some KIU files.

Example error:

    CMDLViewer.UploadTex()
    IndexOutOfRangeException

Therefore an EFE failure does NOT currently imply that an extracted
file is corrupt.

### effect.bcres

Observed:
- CGFX
- CMDL
- PEMT
- TXOB
- IMAG
- emitter/effect names

Appears to contain particle/effect resources.

---

## 5. Audio

### `.snd`

At least one examined `sound.snd` begins with:

    CSAR

and contains multiple:

    CWAV

So the `.snd` extension can contain Nintendo CTR sound archive data.

### `.bcstm`

Streamed 3DS audio.

### `.bcwav`

3DS wave/sample audio.

---

## 6. PSLB — UNKNOWN / IMPORTANT

Some files extracted from archives named `json*.arc` are NOT JSON.

They begin with:

    PSLB

They contain embedded strings including:

- objectList
- OBJECT_CHARACTER
- Pit
- CHID_PIT_COMMON
- motionName
- c01_000_pit
- OBJECT_MAP
- StageModel
- motifModelName
- anmChrChannel
- demo
- funcs
- DefaultMain
- StartDemo
- cameraChangeSec
- demoID

Current hypothesis:

PSLB is structured game/demo/script data connecting things such as:
- objects
- characters
- models
- animations
- functions
- cameras
- effects
- parameters

Binary format is NOT understood yet.

Status: TODO.

---

## 7. Tools

### zrc_extractor.py

Current capabilities:

- Nintendo LZ11 decompression
- handles ZRC 0x20 padding
- parses DARC
- extracts DARC contents
- recursive ZRC discovery
- preserves directory structure
- failure logging

Current result:

    652 / 652 tested ZRCs successfully extracted

Do not modify the known-good decompression implementation without
keeping a backup.

### EveryFileExplorer

Useful for:
- inspecting DARC
- inspecting some CGFX/BCRES
- extracting nested archives

Limitations:
- crashes on some valid KIU CGFX resources
- should not be treated as the definitive validity check

---

## 8. Current format map

    .zrc
      ↓ LZ11
    DARC
      │
      ├── .arc
      │     ↓ often DARC
      │     ├── BCRES / CGFX
      │     │      ├── models
      │     │      ├── textures/materials
      │     │      ├── animations
      │     │      └── effects
      │     │
      │     └── PSLB / other game data
      │
      └── .snd
            ↓
           CSAR
            └── CWAV / sound resources

---

## 9. Next steps

NEXT:
Build an automated ROM format census.

For every file:
- path
- extension
- size
- first bytes / magic
- detected format

Then group files by signature.

Goals:
- discover formats hidden behind generic extensions
- classify `.bin`
- classify `.arc`
- verify `.snd`
- identify unknown formats
- determine which formats require reverse engineering

LATER:
- reverse engineer PSLB
- investigate model/animation relationships
- inspect `.code`
- identify the game's resource-loading functions
