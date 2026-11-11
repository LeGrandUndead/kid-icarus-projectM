// Writes a 3DS model (CGFX), posed on its skeleton, as plain data:
// mesh.bin: per vertex position(3) normal(3) uv(2) float32, triangle lists;
// meshes.txt: per mesh texture name and vertex count; textures as .rgba + textures.txt.
using System; using System.IO; using System.Numerics;
using SPICA.Formats.CtrGfx; using SPICA.Formats.CtrH3D.Animation; using SPICA.Formats.CtrH3D; using SPICA.Formats.CtrH3D.Model; using SPICA.Formats.CtrH3D.Model.Mesh;
class P {
  static string TC(SPICA.Formats.CtrH3D.Model.Material.H3DTextureCoord c) => $"{c.Scale.X:F2},{c.Scale.Y:F2},{c.Rotation:F2},{c.Translation.X:F2},{c.Translation.Y:F2}";
  static void Main(string[] a) {
    H3D h; using (var f = File.OpenRead(a[0])) h = Gfx.Open(f);
    Directory.CreateDirectory(a[1]);
    Console.WriteLine($"models {h.Models.Count} textures {h.Textures.Count} skeletal anims {h.SkeletalAnimations.Count} material anims {h.MaterialAnimations.Count}");
    foreach (var an in h.SkeletalAnimations) Console.WriteLine($"  anim {an.Name} frames {an.FramesCount} elements {an.Elements.Count}");
    var meshes = new StreamWriter(Path.Combine(a[1], "meshes.txt"));
    using var bin = new BinaryWriter(File.Create(Path.Combine(a[1], "mesh.bin")));
    foreach (H3DModel m in h.Models) {
      meshes.WriteLine($"# model {m.Name} bones {m.Skeleton?.Count}");
      foreach (H3DMesh mesh in m.Meshes) {
        if (mesh.Type == H3DMeshType.Silhouette) continue;
        var mat = m.Materials[mesh.MaterialIndex];
        var verts = mesh.GetVertices();
        int n = 0;
        foreach (H3DSubMesh sm in mesh.SubMeshes) {
          foreach (ushort i in sm.Indices) {
            var v = verts[i];
            var p = new Vector3(v.Position.X, v.Position.Y, v.Position.Z);
            var nn = new Vector3(v.Normal.X, v.Normal.Y, v.Normal.Z);
            if (m.Skeleton != null && m.Skeleton.Count > 0 && sm.Skinning != H3DSubMeshSkinning.Smooth) {
              var t = m.Skeleton[sm.BoneIndices[v.Indices[0]]].GetWorldTransform(m.Skeleton);
              p = Vector3.Transform(p, t); nn = Vector3.Normalize(Vector3.TransformNormal(nn, t));
            }
            bin.Write(p.X); bin.Write(p.Y); bin.Write(p.Z);
            bin.Write(nn.X); bin.Write(nn.Y); bin.Write(nn.Z);
            bin.Write(v.TexCoord0.X); bin.Write(v.TexCoord0.Y); bin.Write(v.TexCoord1.X); bin.Write(v.TexCoord1.Y); bin.Write(v.TexCoord2.X); bin.Write(v.TexCoord2.Y); bin.Write(v.Color.X); bin.Write(v.Color.Y); bin.Write(v.Color.Z); bin.Write(v.Color.W);
            n++;
          }
        }
        var mp = mat.MaterialParams; meshes.WriteLine($"{mat.Texture0Name ?? "-"}\t{n}\t{mat.Name}\t{mesh.Layer}\t{mesh.Priority}\t{mat.Texture1Name ?? "-"}\t{mat.Texture2Name ?? "-"}\t{mp.TextureCoords[0].MappingType}/{mp.TextureCoords[1].MappingType}/{mp.TextureCoords[2].MappingType}\t{mp.DiffuseColor}\t{TC(mp.TextureCoords[0])}|{TC(mp.TextureCoords[1])}|{TC(mp.TextureCoords[2])}\t{string.Join(",", mp.TextureSources)}\t{(mp.AlphaTest.Enabled ? mp.AlphaTest.Function + ":" + mp.AlphaTest.Reference : "-")}\t{mp.BlendFunction.ColorSrcFunc}/{mp.BlendFunction.ColorDstFunc}/{mp.ColorOperation.BlendMode}");
      }
    }
    meshes.Close();
    var texs = new StreamWriter(Path.Combine(a[1], "textures.txt"));
    foreach (var t in h.Textures) {
      try { File.WriteAllBytes(Path.Combine(a[1], t.Name + ".rgba"), t.ToRGBA()); texs.WriteLine($"{t.Name}\t{t.Width}\t{t.Height}"); }
      catch (Exception e) { Console.Error.WriteLine($"{t.Name}: {e.Message}"); }
    }
    texs.Close();
    if (a.Length >= 3 && a[2] == "check") {
      var m = h.Models[0]; var pose = Animate.Pose(m.Skeleton, null, 0);
      for (int i = 0; i < Math.Min(6, m.Skeleton.Count); i++) {
        Matrix4x4.Invert(m.Skeleton[i].InverseTransform.ToMatrix4x4(), out var bind);
        Console.WriteLine($"{m.Skeleton[i].Name} parent {m.Skeleton[i].ParentIndex}\n pose {pose[i].M41:F3} {pose[i].M42:F3} {pose[i].M43:F3} | bind {bind.M41:F3} {bind.M42:F3} {bind.M43:F3}\n poseRow1 {pose[i].M11:F3} {pose[i].M12:F3} {pose[i].M13:F3} | bindRow1 {bind.M11:F3} {bind.M12:F3} {bind.M13:F3}");
      }
      return;
    }
    // frames of an animation: dump model.bcres out anim step
    if (a.Length >= 3 && h.Models.Count > 0) {
      var model = h.Models[0];
      H3DAnimation anim = null;
      var animSource = h;
      if (a.Length >= 5) { using var af = File.OpenRead(a[4]); animSource = Gfx.Open(af); }
      foreach (var an in animSource.SkeletalAnimations) if (an.Name == a[2]) anim = an;
      if (anim != null) { int hit = 0; foreach (H3DAnimationElement e in anim.Elements) if (model.Skeleton.Find(e.Name) >= 0) hit++; Console.WriteLine($"bones matched {hit}/{anim.Elements.Count}"); }
      if (anim == null) { Console.Error.WriteLine("no animation " + a[2]); return; }
      float step = a.Length >= 4 ? float.Parse(a[3]) : 1f;
      using var fb = new BinaryWriter(File.Create(Path.Combine(a[1], a[2] + ".frames")));
      // and every bone's world matrix per frame (row-major 4x4), with the bone names
      using var bb = new BinaryWriter(File.Create(Path.Combine(a[1], a[2] + ".bones")));
      File.WriteAllLines(Path.Combine(a[1], "bones.txt"), System.Linq.Enumerable.Select(model.Skeleton, b => b.Name));
      int count = 0;
      // ANIM_START / ANIM_END (environment): only part of the animation
      float f0 = float.Parse(Environment.GetEnvironmentVariable("ANIM_START") ?? "0"), f1 = float.Parse(Environment.GetEnvironmentVariable("ANIM_END") ?? anim.FramesCount.ToString());
      for (float f = f0; f < Math.Min(f1, anim.FramesCount); f += step) {
        var pose = Animate.Pose(model.Skeleton, anim, f);
        foreach (var m in pose) { bb.Write(m.M11); bb.Write(m.M12); bb.Write(m.M13); bb.Write(m.M14); bb.Write(m.M21); bb.Write(m.M22); bb.Write(m.M23); bb.Write(m.M24); bb.Write(m.M31); bb.Write(m.M32); bb.Write(m.M33); bb.Write(m.M34); bb.Write(m.M41); bb.Write(m.M42); bb.Write(m.M43); bb.Write(m.M44); }
        var ps = new System.Collections.Generic.List<Vector3>(); var ns = new System.Collections.Generic.List<Vector3>();
        Animate.Skin(model, pose, ps, ns);
        for (int i = 0; i < ps.Count; i++) { fb.Write(ps[i].X); fb.Write(ps[i].Y); fb.Write(ps[i].Z); fb.Write(ns[i].X); fb.Write(ns[i].Y); fb.Write(ns[i].Z); }
        count++;
      }
      Console.WriteLine($"{a[2]}: {count} frames of {anim.FramesCount}");
    }
  }
}
