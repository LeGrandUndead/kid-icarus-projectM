# Relighting a rendered character in 2D (the anime "satsuei" step: the
# character is lit to fit its background at compositing time).
# The renders save two buffers (idol.BUFS): <f>_base.png, the colour before
# the cutscene shading, and <f>_nrm.png, the surface normals (x right, y up,
# z toward the camera, stored as 0..255). With them we redo post_shade's
# lighting with any key direction, shadow tint and rim colour.
import numpy as np
from PIL import Image

def load(prefix):
    base = np.asarray(Image.open(prefix + '_base.png').convert('RGBA'), np.float32) / 255
    n = np.asarray(Image.open(prefix + '_nrm.png').convert('RGB'), np.float32) / 255 * 2 - 1
    ln = np.linalg.norm(n, axis=2, keepdims=True)
    has = ln[..., 0] > 0.5                       # pixels that had a normal (opaque surfaces)
    n = np.where(has[..., None], n / np.maximum(ln, 1e-6), 0)
    return base, n, has

def relight(prefix, key=(-0.85, 0.45, 0.28), key_col=(1, 1, 1), dark=0.55, shadow=(1, 1, 1),
            rim=(1, 1, 1), rim_strength=0.8, rim_side=None, bounce=None, bounce_strength=0.0):
    """Same maths as render/post_shade.py, plus:
    key_col: colour of the key light on the lit side;
    rim_side: direction the rim comes from (default: opposite the key);
    bounce: colour of light from below (the ground/stage), on down-facing surfaces."""
    base, n, has = load(prefix)
    colour, cover = base[..., :3], base[..., 3]
    L = np.array(key, np.float32); L /= np.linalg.norm(L)
    ndl = np.clip((n @ L) * 1.1 + 0.25, 0, 1)[..., None]
    sh = dark * np.array(shadow, np.float32)
    shade = sh * (1 - ndl) + np.array(key_col, np.float32) * ndl
    edge = np.clip(1 - np.abs(n[..., 2]), 0, 1) ** 2.5
    Rd = -L if rim_side is None else np.array(rim_side, np.float32) / np.linalg.norm(rim_side)
    side = np.clip(0.35 + 0.65 * (n @ Rd), 0, 1)
    r = (edge * side * rim_strength)[..., None] * np.array(rim, np.float32)
    out = colour * np.where(has[..., None], shade, 1) + np.where(has[..., None], r, 0)
    if bounce is not None:
        up = np.clip(-n[..., 1], 0, 1)[..., None] * bounce_strength       # surfaces facing down
        out = out + np.where(has[..., None], colour * up * np.array(bounce, np.float32), 0)
    out = np.dstack([np.clip(out, 0, 1), cover])
    return Image.fromarray((out * 255).astype(np.uint8), 'RGBA')
