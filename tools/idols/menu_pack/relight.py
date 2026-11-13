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
            rim=(1, 1, 1), rim_strength=0.8, rim_side=None, bounce=None, bounce_strength=0.0,
            skin_shadow=None, skin_flat=0.0, soft=0.0, rim_width=9):
    """Same maths as render/post_shade.py, plus:
    key_col: colour of the key light on the lit side;
    rim_side: direction the rim comes from (default: opposite the key);
    bounce: colour of light from below (the ground/stage), on down-facing surfaces;
    skin_shadow: shadow tint used on skin instead of `shadow` (skin stays warm);
    skin_flat: how much of the added shading skin is spared (0..1). Cutscene
    faces have hand-tuned normals for the game's own light; a strong side key
    draws hard edges across them (Dark Pit's face), so skin keeps mostly the
    game's shading;
    soft: blur radius (pixels) of the added shading, so it shapes the large
    forms but draws no hard edges across small ones (noses, cheeks)."""
    base, n, has = load(prefix)
    colour, cover = base[..., :3], base[..., 3]
    L = np.array(key, np.float32); L /= np.linalg.norm(L)
    ndl = np.clip((n @ L) * 1.1 + 0.25, 0, 1)[..., None]
    if soft > 0:
        # a blur that stays inside the figure (normalised by its coverage)
        from scipy.ndimage import gaussian_filter
        m = has.astype(np.float32)
        ndl = (gaussian_filter(ndl[..., 0] * m, soft) / np.maximum(gaussian_filter(m, soft), 1e-3))[..., None]
    sh = dark * np.array(shadow, np.float32)
    skin = None
    if skin_shadow is not None or skin_flat > 0:
        # skin: warm hue (about 0-45 degrees), light, moderately saturated
        mx, mn = colour.max(2), colour.min(2); sat = (mx - mn) / np.maximum(mx, 1e-3)
        r, g, b = colour[..., 0], colour[..., 1], colour[..., 2]
        skin = ((r >= g) & (g >= b) & (mx > 0.45) & (sat > 0.05) & (sat < 0.6) & ((g - b) > 0.2 * (r - b)))[..., None]
        if skin_shadow is not None: sh = np.where(skin, dark * np.array(skin_shadow, np.float32), sh)
    shade = sh * (1 - ndl) + np.array(key_col, np.float32) * ndl
    if skin is not None and skin_flat > 0:
        # soften the skin mask a little so the change has no hard edge
        from PIL import Image as _I, ImageFilter as _F
        m = np.asarray(_I.fromarray((skin[..., 0] * 255).astype(np.uint8)).filter(_F.GaussianBlur(2)), np.float32)[..., None] / 255
        flat = 1 - (1 - np.array(key_col, np.float32) * 0.92) * 0.3        # nearly even, a touch of the key's colour
        shade = shade + (flat - shade) * m * skin_flat
    # the rim only near the outline (screen space): normal-based rims light up
    # cutscene faces, whose hand-edited normals point sideways
    from scipy.ndimage import grey_erosion, grey_closing, gaussian_filter
    solid = grey_closing(cover, size=(7, 7))                  # tiny gaps (mouth, eyes) are not outline
    inside = grey_erosion(solid, size=(rim_width, rim_width))
    near_edge = gaussian_filter(np.clip(solid - inside, 0, 1), 1.0) * cover
    edge = np.clip(near_edge * 1.4, 0, 1) * (0.5 + 0.5 * np.clip(1 - np.abs(n[..., 2]), 0, 1))
    Rd = -L if rim_side is None else np.array(rim_side, np.float32) / np.linalg.norm(rim_side)
    side = np.clip(0.35 + 0.65 * (n @ Rd), 0, 1)
    r = (edge * side * rim_strength)[..., None] * np.array(rim, np.float32)
    lit = (cover > 0.01) if soft > 0 else has                # blurred shading covers decals without normals too
    out = colour * np.where(lit[..., None], shade, 1) + np.where(has[..., None], r, 0)
    if bounce is not None:
        up = np.clip(-n[..., 1], 0, 1)[..., None] * bounce_strength       # surfaces facing down
        out = out + np.where(has[..., None], colour * up * np.array(bounce, np.float32), 0)
    out = np.dstack([np.clip(out, 0, 1), cover])
    return Image.fromarray((out * 255).astype(np.uint8), 'RGBA')
