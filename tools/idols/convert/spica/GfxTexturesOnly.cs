// Reads only the textures of a CGFX file. Effect files (effect.bcres) hold
// particle emitters SPICA cannot read; their textures sit in the second
// dictionary, so the reader stops after it. The Models dictionary is read
// with an empty item type (nothing behind each entry is followed).
using System.Collections.Generic;
using System.IO;
using SPICA.Formats.Common;
using SPICA.Formats.CtrGfx.Texture;
using SPICA.Formats.CtrH3D.Texture;
using SPICA.Serialization;
using SPICA.Serialization.Attributes;

namespace SPICA.Formats.CtrGfx
{
    public class GfxSkip : INamed
    {
        [Ignore] private string _Name;
        public string Name { get => _Name; set => _Name = value; }
    }

    public class GfxTexturesOnly
    {
        public GfxDict<GfxSkip>    Models;
        public GfxDict<GfxTexture> Textures;

        public static List<H3DTexture> Open(Stream Input)
        {
            var D = new BinaryDeserializer(Input, Gfx.GetSerializationOptions());
            D.Deserialize<GfxHeader>();
            var G = D.Deserialize<GfxTexturesOnly>();
            var Out = new List<H3DTexture>();
            foreach (GfxTexture T in G.Textures)
            {
                var Tex = new H3DTexture { Name = T.Name, Width = T.Width, Height = T.Height, Format = T.HwFormat, MipmapSize = (byte)T.MipmapSize };
                if (T is GfxTextureImage I) Tex.RawBuffer = I.Image.RawBuffer; else continue;
                Out.Add(Tex);
            }
            return Out;
        }
    }
}
