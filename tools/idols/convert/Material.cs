// Writes what the 3DS GPU needs to shade each mesh the way the game does
// (materials.json, one entry per exported mesh, in order) and the lighting
// look-up tables (luts.json). Field meanings: SPICA.Rendering's
// FragmentShaderGenerator and DefaultVertexShader.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using SPICA.Formats.CtrH3D;
using SPICA.Formats.CtrH3D.Model.Material;
using SPICA.Formats.CtrH3D.Model.Mesh;
using SPICA.Math3D;
using SPICA.PICA.Commands;
using SPICA.PICA.Converters;

static class Material
{
    static float[] C(RGBA c) => new[] { c.R / 255f, c.G / 255f, c.B / 255f, c.A / 255f };
    public static object Describe(H3DMaterial mat, H3DMesh mesh)
    {
        var p = mat.MaterialParams;
        var stages = p.TexEnvStages.Select((s, i) => new Dictionary<string, object> {
            ["color_src"] = s.Source.Color.Select(x => x.ToString()).ToArray(),
            ["alpha_src"] = s.Source.Alpha.Select(x => x.ToString()).ToArray(),
            ["color_op"] = s.Operand.Color.Select(x => x.ToString()).ToArray(),
            ["alpha_op"] = s.Operand.Alpha.Select(x => x.ToString()).ToArray(),
            ["color_mode"] = s.Combiner.Color.ToString(),
            ["alpha_mode"] = s.Combiner.Alpha.ToString(),
            ["color_scale"] = 1 << (int)s.Scale.Color,
            ["alpha_scale"] = 1 << (int)s.Scale.Alpha,
            ["update_color_buffer"] = s.UpdateColorBuffer,
            ["update_alpha_buffer"] = s.UpdateAlphaBuffer,
            ["color_pass"] = s.IsColorPassThrough,
            ["alpha_pass"] = s.IsAlphaPassThrough,
            ["constant"] = C(p.GetConstantIndex(i) switch { 1 => p.Constant1Color, 2 => p.Constant2Color, 3 => p.Constant3Color, 4 => p.Constant4Color, 5 => p.Constant5Color, _ => p.Constant0Color }),
            ["stage_color"] = C(s.Color),
        }).ToArray();
        string Lut(string table, string sampler) => table == null ? null : table + "/" + sampler;
        return new Dictionary<string, object> {
            ["name"] = mat.Name,
            ["textures"] = new[] { mat.Texture0Name, mat.Texture1Name, mat.Texture2Name },
            ["mapping"] = p.TextureCoords.Select(t => t.MappingType.ToString()).ToArray(),
            ["texcoord_config"] = p.TexCoordConfig.ToString(),
            ["texture_sources"] = p.TextureSources,
            ["flags"] = p.Flags.ToString(),
            ["fragment_flags"] = p.FragmentFlags.ToString(),
            ["emission"] = C(p.EmissionColor), ["ambient"] = C(p.AmbientColor), ["diffuse"] = C(p.DiffuseColor),
            ["specular0"] = C(p.Specular0Color), ["specular1"] = C(p.Specular1Color),
            ["color_scale"] = p.ColorScale,
            ["buffer_color"] = C(p.TexEnvBufferColor),
            ["stages"] = stages,
            ["lut_input"] = new Dictionary<string, object> {
                ["dist0"] = new object[] { p.LUTInputSelection.Dist0.ToString(), p.LUTInputScale.Dist0.ToSingle(), p.LUTInputAbsolute.Dist0, Lut(p.LUTDist0TableName, p.LUTDist0SamplerName) },
                ["dist1"] = new object[] { p.LUTInputSelection.Dist1.ToString(), p.LUTInputScale.Dist1.ToSingle(), p.LUTInputAbsolute.Dist1, Lut(p.LUTDist1TableName, p.LUTDist1SamplerName) },
                ["fresnel"] = new object[] { p.LUTInputSelection.Fresnel.ToString(), p.LUTInputScale.Fresnel.ToSingle(), p.LUTInputAbsolute.Fresnel, Lut(p.LUTFresnelTableName, p.LUTFresnelSamplerName) },
                ["reflec_r"] = new object[] { p.LUTInputSelection.ReflecR.ToString(), p.LUTInputScale.ReflecR.ToSingle(), p.LUTInputAbsolute.ReflecR, Lut(p.LUTReflecRTableName, p.LUTReflecRSamplerName) },
                ["reflec_g"] = new object[] { p.LUTInputSelection.ReflecG.ToString(), p.LUTInputScale.ReflecG.ToSingle(), p.LUTInputAbsolute.ReflecG, Lut(p.LUTReflecGTableName ?? p.LUTReflecRTableName, p.LUTReflecGSamplerName ?? p.LUTReflecRSamplerName) },
                ["reflec_b"] = new object[] { p.LUTInputSelection.ReflecB.ToString(), p.LUTInputScale.ReflecB.ToSingle(), p.LUTInputAbsolute.ReflecB, Lut(p.LUTReflecBTableName ?? p.LUTReflecRTableName, p.LUTReflecBSamplerName ?? p.LUTReflecRSamplerName) },
            },
            ["fresnel_selector"] = p.FresnelSelector.ToString(),
            ["bump_mode"] = p.BumpMode.ToString(), ["bump_texture"] = p.BumpTexture,
            ["alpha_test"] = p.AlphaTest.Enabled ? new object[] { p.AlphaTest.Function.ToString(), p.AlphaTest.Reference / 255f } : null,
            ["blend"] = new[] { p.ColorOperation.BlendMode.ToString(), p.BlendFunction.ColorSrcFunc.ToString(), p.BlendFunction.ColorDstFunc.ToString(), p.BlendFunction.AlphaSrcFunc.ToString(), p.BlendFunction.AlphaDstFunc.ToString() },
            ["depth_write"] = p.DepthBufferWrite,
            ["cull"] = p.FaceCulling.ToString(),
            ["light_set"] = p.LightSetIndex,
            ["layer"] = mesh.Layer,
            ["has_color"] = mesh.Attributes.Any(x => x.Name == SPICA.PICA.Commands.PICAAttributeName.Color),
            ["shader"] = p.ShaderReference,
        };
    }
    public static void Write(H3D h, List<object> mats, string dir)
    {
        var o = new JsonSerializerOptions { WriteIndented = false };
        File.WriteAllText(Path.Combine(dir, "materials.json"), JsonSerializer.Serialize(mats, o));
        var luts = new Dictionary<string, object>();
        foreach (var l in h.LUTs)
            foreach (var s in l.Samplers)
                luts[l.Name + "/" + s.Name] = new Dictionary<string, object> { ["absolute"] = (s.Flags & SPICA.Formats.CtrH3D.LUT.H3DLUTFlags.IsAbsolute) != 0, ["table"] = s.Table };
        File.WriteAllText(Path.Combine(dir, "luts.json"), JsonSerializer.Serialize(luts, o));
        var lights = new List<object>();
        foreach (var l in h.Lights)
        {
            var d = new Dictionary<string, object> { ["name"] = l.Name, ["type"] = l.Type.ToString(), ["enabled"] = l.IsEnabled, ["flags"] = l.Flags.ToString(),
                ["rotation"] = new[] { l.TransformRotation.X, l.TransformRotation.Y, l.TransformRotation.Z },
                ["translation"] = new[] { l.TransformTranslation.X, l.TransformTranslation.Y, l.TransformTranslation.Z } };
            switch (l.Content)
            {
                case SPICA.Formats.CtrH3D.Light.H3DFragmentLight f:
                    d["ambient"] = C(f.AmbientColor); d["diffuse"] = C(f.DiffuseColor); d["specular0"] = C(f.Specular0Color); d["specular1"] = C(f.Specular1Color);
                    d["direction"] = new[] { f.Direction.X, f.Direction.Y, f.Direction.Z }; break;
                case SPICA.Formats.CtrH3D.Light.H3DHemisphereLight hl:
                    d["sky"] = new[] { hl.SkyColor.X, hl.SkyColor.Y, hl.SkyColor.Z, hl.SkyColor.W }; d["ground"] = new[] { hl.GroundColor.X, hl.GroundColor.Y, hl.GroundColor.Z, hl.GroundColor.W };
                    d["direction"] = new[] { hl.Direction.X, hl.Direction.Y, hl.Direction.Z }; d["lerp"] = hl.LerpFactor; break;
                case SPICA.Formats.CtrH3D.Light.H3DAmbientLight al:
                    d["color"] = C(al.Color); break;
                case SPICA.Formats.CtrH3D.Light.H3DVertexLight vl:
                    d["ambient"] = new[] { vl.AmbientColor.X, vl.AmbientColor.Y, vl.AmbientColor.Z }; d["diffuse"] = new[] { vl.DiffuseColor.X, vl.DiffuseColor.Y, vl.DiffuseColor.Z }; d["direction"] = new[] { vl.Direction.X, vl.Direction.Y, vl.Direction.Z }; break;
            }
            lights.Add(d);
        }
        if (lights.Count > 0) File.WriteAllText(Path.Combine(dir, "lights.json"), JsonSerializer.Serialize(lights, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"materials {mats.Count} luts {luts.Count} lights {h.Lights.Count}");
    }
}
