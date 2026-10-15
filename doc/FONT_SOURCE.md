# Shared font replacement

The previous runtime had no shared font file and generated an ASCII-only font by
enlarging 8x8 bitmap characters. This caused the visibly different dialogue and
menu lettering. The installed Azahar log also reports a missing system font, but
Azahar uses its open-source replacement archive instead of this crude fallback.

The local installation now uses that replacement, wrapped in the existing
Zakuro shared-memory font format. No emulator service code was copied.
It is a replacement font, not a Nintendo system-font dump.

Sources:

- [Azahar font archive](https://github.com/azahar-emu/azahar/blob/7f1303a8344724598015a3e48a4bc5aef77090fc/externals/open_source_archives/include/shared_font.app.romfs.h).
- [Generator source at the revision embedded in that archive](https://github.com/B3n30/citra_system_archives/tree/848af476fb2fad4144962dfb2548bd7841f1b72a).

The archive's embedded revision is used for provenance; the directory Readme names
an older generator revision. The source ZIP, downloaded header and notices are
retained in `build/font-source`. The generator is GPL v2; its font inputs include
Montserrat (SIL Open Font License 1.1) and GNU Unifont (GPL v2 or later with the
GNU Font Embedding Exception). Original notices extracted from those exact font
files and the license texts are kept beside the installed asset in
`build/user-data/kiu/sysdata/font-licenses`. Those assets retain their own licenses.

Installed file: `build/user-data/kiu/sysdata/shared_font.bin`, 3,134,822 bytes.
SHA-256: `cf8d18f3ce039383ee627d1167609c5710cadde8db4bd95caebcaefafade82cf`.
The source record is `shared_font.source.json` in the same directory.

To restore this local font, run:

```powershell
python tools/recomp/install_open_font.py build/font-source/shared_font.app.romfs.h
```

The installer verifies the source header's SHA-256, archive entry, decompressed
size and font header. It refuses to overwrite a different installed font.
The download's SHA-256 is
`316a05284c0746bcd1b5623c54ff770f2db736bdb90a592c2eda176e2c3ac6c1`.
The game uses its own textures for some lettering; replacing the shared font does
not increase the resolution of those assets.

The 16,068-frame recorded session with this font completed. Menu lettering was
checked at frame 1,000 and main-screen dialogue at frame 16,068. Evidence is in
`build/evaluation/land-oct9-open-font-3x`, including `font-result.png`.
New input recordings snapshot the font beside the initial saves. Replays use that
snapshot, or an explicit `--shared-font` path, and record its hash. Old recordings
without either retain the generated fallback; the live installed font does not
silently change isolated test cases.
