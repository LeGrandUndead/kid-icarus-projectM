# Cutscene-style extra shading, applied after idol.py's game shading
# (idol.render: `if POST: colour = post_shade(colour, nbuf, cover, **POST)`,
# nbuf = per-pixel normals of the opaque surfaces). After real KIU
# cutscenes: one strong side light, a shadow side tinted with the scene's
# colour, a rim of light on the edges; the skin stays warm.
# Settings used: cast.py  rim=<mode rim>, light=(-0.85,0.45,0.28), dark=0.55,
#   rim_strength=0.8, shadow= together (0.75,0.6,1.0) / vault (0.7,0.85,1.0)
#   / options (0.95,0.7,0.95);  sky.py  rim=(0.9,0.95,1.0), dark=0.6,
#   shadow=(0.75,0.82,1.0).
import numpy as np

def post_shade(colour, nbuf, cover, rim=(1.0, 0.95, 0.85), light=(-0.55, 0.55, 0.62), dark=0.60,
               rim_strength=0.65, shadow=(1.0, 1.0, 1.0)):
    has = np.linalg.norm(nbuf, axis=2) > 0.5
    L = np.array(light, np.float32); L /= np.linalg.norm(L)
    ndl = np.clip((nbuf @ L) * 1.1 + 0.25, 0, 1)
    sh = dark * np.array(shadow, np.float32)
    shade = sh[None, None, :] * (1 - ndl[:, :, None]) + ndl[:, :, None]
    edge = np.clip(1 - np.abs(nbuf[:, :, 2]), 0, 1) ** 2.5
    side = np.clip(0.35 + 0.65 * (nbuf @ -L), 0, 1)
    r = (edge * side * rim_strength)[:, :, None] * np.array(rim, np.float32)[None, None, :]
    out = colour * np.where(has[:, :, None], shade, 1) + np.where(has[:, :, None], r, 0)
    return np.clip(out, 0, 1)
