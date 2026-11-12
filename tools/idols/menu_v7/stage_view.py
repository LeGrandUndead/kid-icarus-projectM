# A game stage seen from inside, with a perspective camera, shaded like the
# game (pica.py). For the menus' backgrounds.
#   view(key, W, H, eye, target, fov_deg) -> RGBA image
# key: a converted stage in idols/out<key> (textures in idols/tex<key>).
import math, numpy as np
from PIL import Image
import idol, pica

def look_at(eye, target, up=(0, 1, 0)):
    # rows: camera right, up, back (the camera looks down -z)
    f = np.asarray(target, float) - eye; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return np.array([r, u, -f])

def clip_near(p, a, near):
    """Clip one triangle (camera-space points p, attributes a) to z <= -near.
    Returns a list of triangles (points, attributes)."""
    inside = p[:, 2] <= -near
    if inside.all(): return [(p, a)]
    if not inside.any(): return []
    poly_p, poly_a = [], []
    for i in range(3):
        j = (i + 1) % 3
        if inside[i]: poly_p.append(p[i]); poly_a.append(a[i])
        if inside[i] != inside[j]:
            t = (-near - p[i, 2]) / (p[j, 2] - p[i, 2])
            poly_p.append(p[i] + t * (p[j] - p[i])); poly_a.append(a[i] + t * (a[j] - a[i]))
    out = []
    for k in range(1, len(poly_p) - 1):
        out.append((np.array([poly_p[0], poly_p[k], poly_p[k + 1]]), np.array([poly_a[0], poly_a[k], poly_a[k + 1]])))
    return out

def raster(tris, W, H, f, depth, test):
    """Nearest fragment of each pixel among `tris` [(group, camera points,
    attributes)], perspective-correct (attributes interpolated over 1/w)."""
    gid = np.full((H, W), -1, np.int32); attr = np.zeros((H, W, 13), np.float32); zb = np.full((H, W), -1e9, np.float32)
    for g_i, p, at in tris:
        w = -p[:, 2]                                       # distance in front of the camera
        x = W / 2 + f * p[:, 0] / w; y = H / 2 - f * p[:, 1] / w
        x0, x1 = int(max(0, math.floor(x.min()))), int(min(W - 1, math.ceil(x.max())))
        y0, y1 = int(max(0, math.floor(y.min()))), int(min(H - 1, math.ceil(y.max())))
        if x1 < x0 or y1 < y0: continue
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        c = 1 - a - b
        inside = (a >= 0) & (b >= 0) & (c >= 0)
        if not inside.any(): continue
        iw = a / w[0] + b / w[1] + c / w[2]                # 1/w: bigger is nearer
        win = inside & (iw > zb[y0:y1 + 1, x0:x1 + 1]) & (iw > depth[y0:y1 + 1, x0:x1 + 1])
        if not win.any(): continue
        wa, wb, wc = a[win] / w[0], b[win] / w[1], c[win] / w[2]; s = wa + wb + wc
        vals = (wa[:, None] * at[0] + wb[:, None] * at[1] + wc[:, None] * at[2]) / s[:, None]
        keep = test(g_i, vals)
        if keep is not None:
            full = np.zeros_like(win); full[win] = keep; win = full; vals = vals[keep]
            if not win.any(): continue
        zb[y0:y1 + 1, x0:x1 + 1][win] = iw[win]; gid[y0:y1 + 1, x0:x1 + 1][win] = g_i
        attr[y0:y1 + 1, x0:x1 + 1][win] = vals
    return gid, attr, zb

def view(key, W, H, eye, target, fov_deg=50, near=5.0, env=None, skip=()):
    v, groups, texs = idol.load(key)
    mats, luts = idol.LOADED[key]
    eye = np.asarray(eye, float); R = look_at(eye, target)
    P = (v[:, 0:3] - eye) @ R.T
    N = v[:, 3:6] @ R.T
    A = np.concatenate([N, v[:, 6:16]], 1)                # normal, 3 UV sets, colour
    f = (H / 2) / math.tan(math.radians(fov_deg) / 2)
    env = pica.in_view(env or pica.LIGHTS.get(key, pica.ENV), R)
    def unpack(vals):
        n = vals[:, 0:3]; n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        return n, [(vals[:, 3], vals[:, 4]), (vals[:, 5], vals[:, 6]), (vals[:, 7], vals[:, 8])], vals[:, 9:13]
    def test(g_i, vals):
        m = mats[g_i]
        if not m.get('alpha_test'): return None
        n, uvs, vc = unpack(vals)
        return pica.passes_alpha_test(m, pica.shade(m, n, uvs, vc, texs, luts, env, need_light=False)[:, 3])
    colour = np.zeros((H, W, 3), np.float32); cover = np.zeros((H, W), np.float32)
    depth = np.full((H, W), -1e9, np.float32)
    for layer in sorted(set(m['layer'] for m in mats)):
        tris = []
        for gi, g in enumerate(groups):
            m = mats[gi]
            if m['layer'] != layer or m['name'] in skip: continue
            for t in range(g['start'], g['start'] + g['count'], 3):
                for p, a in clip_near(P[t:t + 3], A[t:t + 3], near):
                    tris.append((gi, p, a))
        gid, attr, z = raster(tris, W, H, f, depth, test)
        for gi in set(np.unique(gid)) - {-1}:
            m = mats[gi]; sel = gid == gi
            n, uvs, vc = unpack(attr[sel])
            src = pica.shade(m, n, uvs, vc, texs, luts, env)
            blend = m['blend']; dst = np.c_[colour[sel], cover[sel]]
            if blend[1] == 'One' and blend[2] == 'Zero':
                colour[sel] = src[:, :3]; cover[sel] = 1
            else:
                sf = pica.blend_factor(blend[1], src, dst); df = pica.blend_factor(blend[2], src, dst)
                colour[sel] = np.clip(src[:, :3] * sf + dst[:, :3] * df, 0, 1)
                al = src[:, 3] if 'SourceAlpha' in blend[1] else np.ones(len(src))
                cover[sel] = np.clip(al + dst[:, 3] * (1 - al), 0, 1)
            if m['depth_write']:
                depth[sel] = np.maximum(depth[sel], z[sel])
    return Image.fromarray((np.clip(np.dstack([colour, cover]), 0, 1) * 255).astype(np.uint8), 'RGBA')
