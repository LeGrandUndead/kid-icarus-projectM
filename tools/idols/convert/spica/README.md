SPICA changes for this converter (on gdkchan/SPICA 82acbd6):
- `offline-build.patch`: target net8.0, no System.Drawing.Common package,
  bitmap code fenced off with `#if DRAWING`, `Gfx.GetSerializationOptions`
  made internal. Also delete `SPICA/Formats/Generic`.
- `GfxTexturesOnly.cs` (copy to `SPICA/Formats/CtrGfx/`): reads only the
  textures of a CGFX file; used by `dump file.bcres out textures` for
  effect files (particle images).
