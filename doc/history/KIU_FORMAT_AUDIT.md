# Kid Icarus: Uprising — File Format Audit

> The resource-graph step below is now complete. See
> [the current native recompilation audit](NATIVE_RECOMP.md) for executable
> findings and the next engineering milestone. Keep resource research frozen
> unless a concrete execution problem requires it.

This audit separates formats that are already standard/documented from formats or conventions that still appear KIU-specific.

## Standard / already documented

### DARC (`darc`, many `.arc`)
NintendoWare archive format. Publicly documented and supported by existing tools such as darctool and 3DSkit.

**Project implication:** do not reverse-engineer the base archive format further. Maintain our own small reader only for controlled extraction, validation, and integration with the future ROM-preparation pipeline.

### PSLB (`PSLB`, including files named `.json`)
Nintendo/NW4C data-interchange format. Publicly documented as a typed tree containing strings, int32, float32, bytes, maps and lists.

**Project implication:** binary encoding is solved. Focus on KIU-specific keys, IDs, classes and resource relationships only when needed.

### CGFX (`CGFX`, `.bcres`, `.bctex`)
Nintendo CTR graphics resource container. Publicly documented; contains models, textures, materials, shaders, animations, cameras, lights, emitters and other graphics resources. Existing parsers/viewers include EveryFileExplorer and SPICA-family tooling.

**Project implication:** do not write a CGFX implementation from scratch unless runtime requirements force it. First decide whether the recomp runtime will consume CGFX natively, use an existing parser/library, or prepare/cache data during installation.

### BCSTM (`CSTM`, `.bcstm`)
Nintendo CTR streamed-audio format. Publicly documented; existing playback/conversion support exists in tools such as vgmstream and 3DSkit.

**Project implication:** use existing decoders/specification. KIU-specific work is mapping sound IDs/resources, not decoding samples from first principles.

### BCSAR (`CSAR`, KIU `.snd`)
Nintendo CTR sound archive. Publicly documented and supported by existing tooling.

**Project implication:** use existing archive/audio knowledge. Focus later on how KIU refers to specific sound resources.

### LZ11
Standard Nintendo compression supported by existing open-source tooling.

**Project implication:** our decoder is fine for validation/integration, but LZ11 itself is not a KIU reverse-engineering target.

### MoFlex / Mobiclip (`.moflex`)
Known Mobiclip-based video container/codec. Existing decoders exist, including Gericom's MobiclipDecoder and FFmpeg-derived implementations.

**Project implication:** do not reverse-engineer the video codec. Integrate an existing decoder later if native video playback is required.

## KIU-specific or still project-specific

### ZRC
Observed KIU convention:

`LZ11 stream -> decompressed DARC`

The building blocks are standard, but the fact that KIU's `.zrc` corpus consistently uses this wrapper is game-specific knowledge.

**Status:** wrapper behavior understood and validated across the tested corpus.

### `eff_00.bin`
KIU effect configuration family.

Observed:
- type 2: particle -> trigger
- type 3: model -> particle -> trigger
- model record size: `0x5C`
- particle record size: `0x54`
- trigger record size: `0x50`
- 700/700 files parse -> serialize byte-identically

No public specification or obvious matching open-source implementation was found in the targeted audit.

**Status:** outer format solved; field semantics partially understood. Revisit only when runtime/code behavior requires more meaning.

## Recommended project direction

1. Fix/standardize our DARC reader using the public specification.
2. Stop low-level RE of standard NintendoWare formats.
3. Build a resource/reference graph across KIU-specific data:
   - PSLB identifiers and paths
   - EFF effect references
   - CGFX model/texture/animation names
   - BCSAR sound identifiers
4. Use that graph to understand how the original game stitches resources together.
5. Only then return to `.code` / static recompilation when the data layer is sufficiently mapped.

The key rule going forward:

> Identify magic -> check public specification and existing open-source tools -> validate against KIU -> reverse-engineer only the game-specific layer.
