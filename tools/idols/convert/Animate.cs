// Poses a model's skeleton at a frame of one of its skeletal animations and
// skins its vertices, the way SPICA's viewer does (SPICA.Rendering:
// SkeletalAnimation.cs, Mesh.cs), with System.Numerics instead of OpenTK.
using System;
using System.Collections.Generic;
using System.Numerics;
using SPICA.Formats.CtrH3D;
using SPICA.Formats.CtrH3D.Animation;
using SPICA.Formats.CtrH3D.Model;
using SPICA.Formats.CtrH3D.Model.Mesh;

static class Animate
{
    class Bone { public Vector3 Scale, Euler, Translation; public Quaternion Rotation; public int Parent; }

    static Quaternion FromEuler(Vector3 e)
    {
        double SX = Math.Sin(e.X * 0.5), SY = Math.Sin(e.Y * 0.5), SZ = Math.Sin(e.Z * 0.5);
        double CX = Math.Cos(e.X * 0.5), CY = Math.Cos(e.Y * 0.5), CZ = Math.Cos(e.Z * 0.5);
        return new Quaternion(
            (float)(CZ * SX * CY - SZ * CX * SY),
            (float)(CZ * CX * SY + SZ * SX * CY),
            (float)(SZ * CX * CY - CZ * SX * SY),
            (float)(CZ * CX * CY + SZ * SX * SY));
    }

    /// Every bone's local scale, rotation and translation at `frame` (for
    /// posing in Python: dump ... locals). Bones driven by whole matrices
    /// (rare) keep their rest values; their count is returned.
    public static (Vector3 s, Quaternion r, Vector3 t)[] Locals(H3DDict<H3DBone> skeleton, H3DAnimation anim, float frame, out int matrixBones)
    {
        var w = Pose(skeleton, anim, frame, out var bones, out var fixedM);
        matrixBones = 0; foreach (var f in fixedM) if (f) matrixBones++;
        var o = new (Vector3, Quaternion, Vector3)[bones.Length];
        for (int i = 0; i < bones.Length; i++) o[i] = (bones[i].Scale, bones[i].Rotation, bones[i].Translation);
        return o;
    }

    /// The world transform of every bone at `frame` (no animation: the rest pose).
    public static Matrix4x4[] Pose(H3DDict<H3DBone> skeleton, H3DAnimation anim, float frame) => Pose(skeleton, anim, frame, out _, out _);

    static Matrix4x4[] Pose(H3DDict<H3DBone> skeleton, H3DAnimation anim, float frame, out Bone[] bonesOut, out bool[] fixedOut)
    {
        int n = skeleton.Count;
        var bones = new Bone[n];
        for (int i = 0; i < n; i++)
        {
            var b = skeleton[i];
            bones[i] = new Bone { Scale = b.Scale, Euler = b.Rotation, Translation = b.Translation, Parent = b.ParentIndex };
            bones[i].Rotation = FromEuler(bones[i].Euler);
        }
        var result = new Matrix4x4[n];
        var fixedM = new bool[n];
        if (anim != null)
        {
            foreach (H3DAnimationElement e in anim.Elements)
            {
                int i = skeleton.Find(e.Name);
                if (i < 0) continue;
                var bone = bones[i];
                switch (e.PrimitiveType)
                {
                    case H3DPrimitiveType.Transform:
                    {
                        var t = (H3DAnimTransform)e.Content;
                        void Set(H3DFloatKeyFrameGroup g, ref float v) { if (g.Exists) v = g.GetFrameValue(frame); }
                        Set(t.ScaleX, ref bone.Scale.X); Set(t.ScaleY, ref bone.Scale.Y); Set(t.ScaleZ, ref bone.Scale.Z);
                        Set(t.RotationX, ref bone.Euler.X); Set(t.RotationY, ref bone.Euler.Y); Set(t.RotationZ, ref bone.Euler.Z);
                        Set(t.TranslationX, ref bone.Translation.X); Set(t.TranslationY, ref bone.Translation.Y); Set(t.TranslationZ, ref bone.Translation.Z);
                        if (t.RotationExists) bone.Rotation = FromEuler(bone.Euler);
                        break;
                    }
                    case H3DPrimitiveType.QuatTransform:
                    {
                        var t = (H3DAnimQuatTransform)e.Content;
                        int f = (int)frame; float w = frame - f;
                        if (t.HasScale) bone.Scale = Vector3.Lerp(t.GetScaleValue(f), t.GetScaleValue(f + 1), w);
                        if (t.HasRotation) bone.Rotation = Quaternion.Slerp(t.GetRotationValue(f), t.GetRotationValue(f + 1), w);
                        if (t.HasTranslation) bone.Translation = Vector3.Lerp(t.GetTranslationValue(f), t.GetTranslationValue(f + 1), w);
                        break;
                    }
                    case H3DPrimitiveType.MtxTransform:
                        result[i] = ((H3DAnimMtxTransform)e.Content).GetTransform((int)frame).ToMatrix4x4();
                        fixedM[i] = true;
                        break;
                }
            }
        }
        for (int i = 0; i < n; i++)
        {
            if (fixedM[i]) continue;
            var b = bones[i];
            bool compensate = (skeleton[i].Flags & H3DBoneFlags.IsSegmentScaleCompensate) != 0 && b.Parent >= 0;
            var m = Matrix4x4.CreateScale(b.Scale) * Matrix4x4.CreateFromQuaternion(b.Rotation);
            if (compensate)
            {
                var ps = bones[b.Parent].Scale;
                m *= Matrix4x4.CreateTranslation(b.Translation * ps);
                m *= Matrix4x4.CreateScale(1f / ps.X, 1f / ps.Y, 1f / ps.Z);
                m *= result[b.Parent];
            }
            else
            {
                m *= Matrix4x4.CreateTranslation(b.Translation);
                if (b.Parent >= 0) m *= result[b.Parent];
            }
            result[i] = m;
        }
        bonesOut = bones; fixedOut = fixedM;
        return result;
    }

    /// The model's vertices (triangle lists, the export's order) moved by the pose.
    public static void Skin(H3DModel model, Matrix4x4[] pose, List<Vector3> positions, List<Vector3> normals)
    {
        var skel = model.Skeleton;
        // the bind pose: the skeleton at rest (the stored inverse matrices
        // do not survive the CGFX conversion)
        var rest = skel != null && skel.Count > 0 ? Pose(skel, null, 0) : new Matrix4x4[0];
        var inverse = new Matrix4x4[rest.Length];
        for (int b = 0; b < rest.Length; b++) Matrix4x4.Invert(rest[b], out inverse[b]);
        foreach (H3DMesh mesh in model.Meshes)
        {
            if (mesh.Type == H3DMeshType.Silhouette) continue;
            var verts = mesh.GetVertices();
            foreach (H3DSubMesh sm in mesh.SubMeshes)
            {
                bool smooth = sm.Skinning == H3DSubMeshSkinning.Smooth;
                foreach (ushort i in sm.Indices)
                {
                    var v = verts[i];
                    var p = new Vector3(v.Position.X, v.Position.Y, v.Position.Z);
                    var nn = new Vector3(v.Normal.X, v.Normal.Y, v.Normal.Z);
                    if (skel == null || skel.Count == 0 || pose.Length == 0) { positions.Add(p); normals.Add(nn); continue; }
                    Matrix4x4 Bone(int k)
                    {
                        int b = sm.BoneIndices[v.Indices[k]];
                        var t = pose[b];
                        return smooth ? inverse[b] * t : t;
                    }
                    if (!smooth)
                    {
                        var t = Bone(0);
                        positions.Add(Vector3.Transform(p, t)); normals.Add(Vector3.Normalize(Vector3.TransformNormal(nn, t)));
                        continue;
                    }
                    var sp = Vector3.Zero; var sn = Vector3.Zero; float total = 0;
                    for (int k = 0; k < 4; k++)
                    {
                        float w = v.Weights[k];
                        if (w <= 0) continue;
                        var t = Bone(k);
                        sp += Vector3.Transform(p, t) * w; sn += Vector3.TransformNormal(nn, t) * w; total += w;
                    }
                    if (total <= 0) { sp = p; sn = nn; total = 1; }
                    positions.Add(sp / total); normals.Add(Vector3.Normalize(sn));
                }
            }
        }
    }
}
