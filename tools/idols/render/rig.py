# A small posing rig for the idols: the skeleton and skin the converter
# exports (dump <bcres> <out> skin, and LOCALS=1 for each animation's per-bone
# local transforms), so new animations can be made bone by bone: blends
# between any frames of any clip, rotations added on chosen bones, follow-
# through on hair and cloth. The result is the same vertex array as an
# animation's .frames file, so idol.render(pose=...) draws it.
#
# Conventions (System.Numerics, as the converter): row vectors, v' = v M;
# a bone's local matrix = Scale * Rotation * Translation; world = local * parent.
import numpy as np
from idol import S

class Rig:
    def __init__(self, key):
        out = f'{S}/out{key}'
        sk = [l.rstrip('\n').split('\t') for l in open(f'{out}/skeleton.txt')]
        self.names = [r[0] for r in sk]; self.index = {n: i for i, n in enumerate(self.names)}
        self.parent = np.array([int(r[1]) for r in sk]); self.comp = np.array([r[2] == '1' for r in sk])
        self.rest = np.array([[float(x) for x in r[3:13]] for r in sk], np.float32)      # s3 q4 t3
        skin = np.fromfile(f'{out}/skin.bin', np.float32).reshape(-1, 15)
        self.p, self.n = skin[:, 0:3], skin[:, 3:6]
        self.smooth = skin[:, 6] > 0.5
        self.bi = skin[:, 7:11].astype(int); self.w = skin[:, 11:15]
        self.out = out; self.clips = {}
        self.inv = np.linalg.inv(self.world(self.rest))

    def clip(self, anim):
        """Every frame's local transforms: frames x bones x 10."""
        if anim not in self.clips:
            self.clips[anim] = np.fromfile(f'{self.out}/{anim}.locals', np.float32).reshape(-1, len(self.names), 10)
        return self.clips[anim]

    def world(self, loc):
        n = len(self.names); res = np.zeros((n, 4, 4), np.float32)
        for i in range(n):
            s, q, t = loc[i, 0:3], loc[i, 3:7], loc[i, 7:10]
            m = np.diag([s[0], s[1], s[2], 1.0]).astype(np.float32) @ rot(q)
            p = self.parent[i]
            if self.comp[i] and p >= 0:
                ps = loc[p, 0:3]
                m = m @ trans(t * ps) @ np.diag([1 / ps[0], 1 / ps[1], 1 / ps[2], 1.0]).astype(np.float32) @ res[p]
            else:
                m = m @ trans(t)
                if p >= 0: m = m @ res[p]
            res[i] = m
        return res

    def skin(self, loc):
        """Vertices and normals for these local transforms (like a .frames frame)."""
        W = self.world(loc)
        M = np.where(self.smooth[:, None, None, None], np.einsum('bij,bjk->bik', self.inv, W)[self.bi], W[self.bi])   # V x 4 x 4 x 4
        ph = np.c_[self.p, np.ones(len(self.p), np.float32)]
        pos = np.einsum('vi,vkij->vkj', ph, M)[..., :3]
        nor = np.einsum('vi,vkij->vkj', self.n, M[:, :, :3, :3])
        w = self.w / np.maximum(self.w.sum(1, keepdims=True), 1e-6)
        P = (pos * w[..., None]).sum(1); N = (nor * w[..., None]).sum(1)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-6)
        return np.c_[P, N].astype(np.float32)

def rot(q):
    x, y, z, w = q
    # System.Numerics CreateFromQuaternion (row-vector form)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0],
                     [2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0],
                     [2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0],
                     [0, 0, 0, 1]], np.float32)
def trans(t):
    m = np.eye(4, dtype=np.float32); m[3, :3] = t; return m

# --- quaternions (x, y, z, w) ---------------------------------------------------
def qmul(a, b):
    """The rotation b then a? No: System.Numerics Quaternion.Multiply(a, b)."""
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz], np.float32)
def qaxis(axis, deg):
    a = np.asarray(axis, np.float32); a = a / np.linalg.norm(a); h = np.radians(deg) / 2
    return np.r_[a * np.sin(h), np.cos(h)].astype(np.float32)
def slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0: b = -b; d = -d
    if d > 0.9995: q = a + (b - a) * t; return q / np.linalg.norm(q)
    th = np.arccos(d); s = np.sin(th)
    return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / s

def blend(a, b, t, bones=None):
    """Local poses a -> b by t (0..1, may overshoot a little), per bone (slerp)."""
    out = a.copy()
    idx = range(len(a)) if bones is None else bones
    for i in idx:
        tt = t[i] if hasattr(t, '__len__') else t
        out[i, 0:3] = a[i, 0:3] + (b[i, 0:3] - a[i, 0:3]) * tt
        q = slerp(a[i, 3:7], b[i, 3:7], min(max(tt, 0.0), 1.0))
        if tt > 1:                       # overshoot: keep turning past b
            q = slerp(a[i, 3:7], b[i, 3:7], 1.0); extra = slerp(a[i, 3:7], b[i, 3:7], tt - 1.0)
            q = qmul(q, qmul(extra, np.r_[-a[i, 3:6], a[i, 6]]))
        out[i, 3:7] = q / np.linalg.norm(q)
        out[i, 7:10] = a[i, 7:10] + (b[i, 7:10] - a[i, 7:10]) * tt
    return out

def turn(loc, bone_i, axis, deg):
    """Adds a rotation of `deg` about `axis` (the bone's own frame) to one bone."""
    loc = loc.copy(); q = qmul(qaxis(axis, deg), loc[bone_i, 3:7]); loc[bone_i, 3:7] = q / np.linalg.norm(q); return loc
