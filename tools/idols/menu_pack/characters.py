"""Each mode's character: which rendered frames it plays, where it stands,
and each frame relit for its stage, tied into it, and encoded for the game
(JPEG colour + PNG coverage, which the game decodes about 4x faster than
WebP)."""
import os

import numpy as np
from PIL import Image, ImageFilter

from . import config, relight
from .config import BAND_Y, TUNE, W, H
from .images import add, mix, scaled, soft_glow
from .modes import MODES, PALETTE, light

R = config.RENDERS

SEQUENCES = {
    # Pit: a seamless 6 s glide with a glance and a barrel roll (render/solo_loop.py)
    0: dict(dir=f'{R}/solo_loop_buf', idle=dict(range=[0, 359], play='loop'), confirm=dict(range=[1000, 1047])),
    # Pit and Dark Pit: a back-and-forth hold, then the throw and the kick (impact at 190)
    1: dict(dir=f'{R}/poster_tog_buf', idle=dict(range=[0, 149], play='pingpong'), confirm=dict(range=[150, 215], impact=190)),
    # Palutena and Viridi: their key-art animations (render/promo.py): an
    # entrance into the hero pose, a held pose that loops in 4 s, a confirm pose
    2: dict(dir=f'{R}/promo_P02_buf', intro=dict(range=[0, 39]), idle=dict(range=[100, 339], play='loop'), confirm=dict(range=[400, 439])),
    3: dict(dir=f'{R}/promo_V12_buf', intro=dict(range=[0, 39]), idle=dict(range=[100, 339], play='loop'), confirm=dict(range=[400, 439])),
}
"""Per mode: the frames' folder (render buffers) and its sequences."""

FEET = BAND_Y - 5           # standing characters' feet: on the ground band
FRAMING = {0: (640, 1340, 880), 1: (820, 1390, FEET + 4), 2: (860, 1420, FEET), 3: (800, 1410, FEET)}
"""Per mode: the character's height in a reference frame, the x of its middle
and the y of its feet (design pixels): full figures, none cut off."""
REFERENCE = {0: f'{R}/poster_solo/0060.png', 1: f'{R}/poster_tog_buf/0100_post.png',
             2: f'{R}/promo_P02_buf/0100_post.png', 3: f'{R}/promo_V12_buf/0100_post.png'}
SOLO_FIT = dict(scale=0.82, about=(1380, 460), move=(-90, 40))
"""Pit's loop (glance, barrel roll) sweeps wider than his reference pose
(measured over the loop: wings at x 690-2070, y -50-970): shrunk about his
flight centre and moved into the window."""


def placements():
    """Per mode: (scale, x, y) placing the render's pixels in the design."""
    place = {}
    for mode, (h, cx, feet) in FRAMING.items():
        if not os.path.exists(REFERENCE[mode]): print('no reference frame yet for mode', mode); continue
        ref = Image.open(REFERENCE[mode]).getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
        k = h / (ref[3] - ref[1]); place[mode] = (k, cx - (ref[0] + ref[2]) / 2 * k, feet - ref[3] * k)
    if 0 in place:
        k, x0, y0 = place[0]; sc = SOLO_FIT['scale']; (ax, ay), (mx, my) = SOLO_FIT['about'], SOLO_FIT['move']
        place[0] = (k * sc, ax + (x0 - ax) * sc + mx, ay + (y0 - ay) * sc + my)
    return place


def impact(place):
    """Where Together's kick lands (frame 190), design pixels: the rays and
    the impact effects start there."""
    b = Image.open(f'{R}/poster_tog_buf/0190_post.png').getbbox(); k, x, y = place[1]
    return (int(x + (b[0] + b[2]) / 2 * k), int(y + (b[1] + 0.45 * (b[3] - b[1])) * k))


def rest_window(mode, stage, solo_glow):
    """The window as it stands at rest (for the light wrap)."""
    win = Image.new('RGBA', (W, H)); o = 60
    win.paste(stage.crop((o, 35, o + W, 35 + H)), (0, 0))
    if mode == 0: win = add(win, solo_glow)
    return win


def integrate(ch, mode, window, pos):
    """A character tied into its stage: its darkest tones take the stage's
    shadow hue, and the stage's light wraps round the inside of its edge."""
    a = np.asarray(ch, np.float32) / 255; rgb, al = a[..., :3], a[..., 3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    deep = np.array(PALETTE[mode]['deep'], np.float32) / 255
    k = (np.clip(1 - lum / 0.5, 0, 1) ** 2 * 0.45)[..., None]           # only the darks, most in the darkest
    rgb = rgb + (deep * 1.6 - rgb) * k
    # light wrap: the blurred stage, added just inside the edge
    x, y = pos; bg = Image.new('RGBA', ch.size); bg.paste(window.crop((x, y, x + ch.width, y + ch.height)), (0, 0))
    bgb = np.asarray(bg.filter(ImageFilter.GaussianBlur(24)), np.float32)[..., :3] / 255
    am = Image.fromarray((al * 255).astype(np.uint8))
    inner = np.clip(al - np.asarray(am.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255, 0, 1)[..., None] * 1.6
    rgb = 1 - (1 - rgb) * (1 - np.clip(inner, 0, 1) * bgb * TUNE['wrap'])
    out = np.dstack([np.clip(rgb, 0, 1), al])
    return Image.fromarray((out * 255).astype(np.uint8), 'RGBA')


def bleed(img):
    """The colour under see-through pixels, filled from the nearby visible
    ones (a premultiplied blur divided by the blurred coverage), so JPEG has
    no dark or stray colour to bleed into the soft edges."""
    from scipy import ndimage
    a = np.asarray(img, np.float32) / 255
    alpha = a[:, :, 3:4]
    rgb = a[:, :, :3]
    soft = np.zeros_like(rgb); cover = np.zeros_like(alpha)
    for sigma in (2, 6, 18):                       # near colour first, far colour for big gaps
        pre = np.stack([ndimage.gaussian_filter(rgb[:, :, c] * alpha[:, :, 0], sigma) for c in range(3)], 2)
        cov = ndimage.gaussian_filter(alpha[:, :, 0], sigma)[:, :, None]
        fill = (cover < 1e-3) & (cov > 1e-3)
        soft = np.where(fill, pre / np.maximum(cov, 1e-6), soft)
        cover = np.where(fill, 1.0, cover)
    out = np.where(alpha > 0.98, rgb, alpha * rgb + (1 - alpha) * soft)
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))


def save_frame(lay, base):
    """One frame: colour (`base`.jpg) and coverage (`base`_a.png)."""
    bleed(lay).save(base + '.jpg', quality=92, subsampling=0)
    lay.getchannel('A').save(base + '_a.png', optimize=False, compress_level=6)


def frames(mode, out, place, stage, solo_glow, build_missing=True):
    """Builds mode's character frames into out/char_<mode> (frames already
    built are kept: each has a .at file with its corner and size; with
    build_missing False, only those are listed). Returns its manifest entry."""
    seq = SEQUENCES[mode]; k, x0, y0 = place[mode]; window = rest_window(mode, stage, solo_glow)
    os.makedirs(f'{out}/char_{mode}', exist_ok=True)
    built = {}
    wanted = sorted({i for part in ('intro', 'idle', 'confirm') if part in seq for i in range(seq[part]['range'][0], seq[part]['range'][1] + 1)})
    for i in wanted:
        pre = f'{seq["dir"]}/{i:04d}'
        if not os.path.exists(pre + '_nrm.png'):
            print('missing', pre); continue
        done = f'{out}/char_{mode}/{i:04d}.jpg'
        if os.path.exists(done) and os.path.exists(done + '.at'):
            built[i] = [int(x) for x in open(done + '.at').read().split()]; continue
        if not build_missing: continue
        ch = scaled(relight.relight(pre, **light(mode)), k)
        pos = (int(x0), int(y0))
        ch = integrate(ch, mode, window, pos)
        pad = 40
        lay = Image.new('RGBA', (ch.width + 2 * pad, ch.height + 2 * pad))
        lay.alpha_composite(soft_glow(ch, mix(MODES[mode]['color'], (255, 240, 220), 0.5), 0.22, 16), (pad, pad))
        lay.alpha_composite(ch, (pad, pad))
        bb = lay.getchannel('A').getbbox()
        lay = lay.crop(bb)
        save_frame(lay, done[:-4])
        built[i] = [pos[0] - pad + bb[0], pos[1] - pad + bb[1], lay.width, lay.height]
        open(done + '.at', 'w').write(' '.join(map(str, built[i])))
    parts = {p: seq[p] for p in ('intro', 'idle', 'confirm') if p in seq}
    return dict(dir=f'char_{mode}', frames=built, **parts)
