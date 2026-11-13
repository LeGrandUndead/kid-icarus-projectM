"""The scene's layers, each a picture in the design's 1920x1080 pixels
(or cropped, with its place given in the manifest)."""
import glob
import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

from . import config
from .config import BAND_Y, BLACK, H, TUNE, W
from .game_art import art
from .images import faded, fit, mask, oklch_to_rgb, only_largest, top_piece
from .modes import MODES, PALETTE, STAGE_STOPS


# --- the paper, tinted per mode ---------------------------------------------------

def paper(c0=(242, 234, 216), c1=(226, 213, 186), lines=True, seed=1):
    """The striped paper: a warm vignette, fine grain and the game's thin
    horizontal lines."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
    r = np.sqrt((x - 0.5) ** 2 * 1.2 + (y - 0.42) ** 2)
    t = np.clip(r * 1.3, 0, 1)[..., None]
    base = np.array(c0)[None, None, :] * (1 - t) + np.array(c1)[None, None, :] * t
    noise = ndimage.gaussian_filter(rng.normal(0, 1, (H, W)), 1.2) * 5
    base = base + noise[..., None]
    if lines:
        ly = (np.sin(np.arange(H) / H * 2 * math.pi * 48) > 0.92)[:, None, None] * -7
        base = base + ly
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGBA')


def papers():
    """Each mode's paper: the paper washed 10% in the mode's colour."""
    plain = paper(seed=3).convert('RGB')
    return {i: Image.blend(plain, Image.new('RGB', (W, H), MODES[i]['color']), 0.10).convert('RGBA') for i in range(4)}


def emblem(mode):
    """The mode's emblem as a big faded watermark in its colour."""
    e, _ = art(*MODES[mode]['emblem'])
    return faded(fit(mask(e, MODES[mode]['color'], 0.55), h=1100), 0.55)


# --- the stages -------------------------------------------------------------------

def stage_texture(name):
    return Image.open(sorted(glob.glob(f'{config.STAGE_TEXTURES}/*/{name}.png'))[0]).convert('RGBA')


def solo_clouds():
    """Chapter 1's own sky: its gradient, a sea of clouds below, puffs
    above. One tile W wide, twice, so it can scroll past Pit."""
    sky = stage_texture('a01m03_bg00').convert('RGB').crop((96, 0, 160, 118)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4)).convert('RGBA')
    sea = stage_texture('a01m01_ukumo_a').resize((480, 240), Image.BICUBIC)
    band = Image.new('RGBA', (W, 240)); [band.paste(sea, (x, 0)) for x in range(0, W, 480)]
    fade = Image.linear_gradient('L').resize((W, 240)); band.putalpha(ImageChops.multiply(band.getchannel('A'), fade))
    sky.alpha_composite(band, (0, H - 300))
    puff = stage_texture('a01m03_kumo01').resize((640, 640), Image.BICUBIC)
    yy, xx = np.mgrid[0:640, 0:640]; soft = np.clip(1 - np.hypot(xx - 320, yy - 320) / 320, 0, 1) ** 1.5      # round, soft-edged
    puff.putalpha(Image.fromarray((np.asarray(puff.getchannel('A'), np.float32) * soft * 0.8).astype(np.uint8)))
    for x, y in [(0, -120), (640, 60), (1280, -200), (320, 330), (960, 300), (1600, 320)]:
        sky.alpha_composite(puff, (x, y))
        if x + 640 > W: sky.alpha_composite(puff, (x - W, y))
    tile = sky.convert('RGB'); two = Image.new('RGB', (2 * W, H)); two.paste(tile, (0, 0)); two.paste(tile, (W, 0))
    return two


def graded(img, mode, size=None, glow_on=True):
    """A stage through its mode's gradient map (4 OKLCH stops, cool shadows
    to warm lights), slightly defocused, a little lighter toward the key
    light, with the key light's glow screened on."""
    pal = PALETTE[mode]; sw, shh = size or (W + 120, H + 70)
    img = img.convert('RGB').resize((sw, shh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3.0))
    a = np.asarray(img, np.float32) / 255
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lo, hi = np.percentile(lum, 2), np.percentile(lum, 98)
    t = np.clip((lum - lo) / max(1e-3, hi - lo), 0, 1)
    yy, xx = np.mgrid[0:shh, 0:sw].astype(np.float32); kx, ky = pal['at']; d = np.hypot(xx - kx, yy - ky)
    t = np.clip(t * 0.8 + 0.12 * np.exp(-(d / 900) ** 2) - 0.14 * np.clip(d / 1900, 0, 1), 0, 1)   # lighter toward the key light
    st = STAGE_STOPS[mode]; k = t * (len(st) - 1); i = np.clip(k.astype(int), 0, len(st) - 2); f = k - i
    S0 = np.array(st, np.float32)
    def lerp(col):
        x0, x1 = S0[i, col], S0[i + 1, col]; return x0 + (x1 - x0) * f
    hue0, hue1 = S0[i, 2], S0[i + 1, 2]; dh = (hue1 - hue0 + 180) % 360 - 180          # the short way round the hue circle
    m = oklch_to_rgb(lerp(0), lerp(1), hue0 + dh * f)
    m = m * 0.88 + a * 0.12                              # a little of the stage's own colour
    if glow_on:
        glow = np.exp(-(d / 650) ** 2)[..., None]
        m = 1 - (1 - m) * (1 - glow * TUNE['glow'] * np.array(pal['key'], np.float32) / 255)
    return Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).convert('RGBA')


def stages():
    """Each mode's stage: Solo's scrolling sky (its glow is a separate
    layer, it stays still while the sky scrolls), the other modes' renders."""
    return {0: graded(solo_clouds(), 0, size=(2 * W, H + 70), glow_on=False),
            1: graded(Image.open(f'{config.STAGE_RENDERS}/together.png'), 1),
            2: graded(Image.open(f'{config.STAGE_RENDERS}/vault.png'), 2),
            3: graded(Image.open(f'{config.STAGE_RENDERS}/options.png'), 3)}


def key_glow(mode):
    """The key light's glow alone, an added light (Solo's)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); kx, ky = PALETTE[mode]['at']
    g = np.exp(-(np.hypot(xx - kx, yy - ky) / 650) ** 2)[..., None] * TUNE['glow'] * 1.4 * np.array(PALETTE[mode]['key'], np.float32)
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert('RGBA')


def rays(centre, color, n=24, length=1700, strength=TUNE['rays'], seed=4):
    """Soft rays of light fanning out from `centre`, drawn at quarter size
    and blurred, an added light."""
    cx, cy = centre; q = 4
    lay = Image.new('L', (W // q, H // q)); d = ImageDraw.Draw(lay); rnd = random.Random(seed)
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.12, 0.12); w = rnd.uniform(0.03, 0.08); L = length * rnd.uniform(0.6, 1.0) / q
        p = [(cx / q, cy / q), (cx / q + math.cos(a - w) * L, cy / q + math.sin(a - w) * L), (cx / q + math.cos(a + w) * L, cy / q + math.sin(a + w) * L)]
        d.polygon(p, fill=int(255 * rnd.uniform(0.35, 1.0)))
    yy, xx = np.mgrid[0:H // q, 0:W // q]
    r = np.sqrt((xx - cx / q) ** 2 + (yy - cy / q) ** 2) / (length / q)
    m = np.asarray(lay, np.float32) / 255 * np.clip(1 - r, 0, 1) ** 1.5      # fading with distance
    core = np.exp(-(r * 3.2) ** 2)                                            # the bright source itself
    m = np.clip(m + core * 0.9, 0, 1) * strength
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
    out = Image.new('RGBA', (W, H), color + (0,)); out.putalpha(img)
    return out


# --- the heading and caption ------------------------------------------------------

def flourish(width):
    """The flourish under the heading (MenTopUp0000, mirrored as the game
    does), coloured with the game's gradient strip (MenTopUp0001)."""
    half, _ = art('040', 'MenTopUp0000')
    grad, _ = art('040', 'MenTopUp0001')
    shape = Image.new('RGBA', (half.width * 2, half.height))
    shape.paste(half, (0, 0)); shape.paste(half.transpose(Image.FLIP_LEFT_RIGHT), (half.width, 0))
    shape = fit(shape, w=width)
    g = np.asarray(grad.convert('RGB').resize((shape.width, 1), Image.BILINEAR), np.float32)[0]
    a = np.asarray(shape, np.float32)
    cover = a[:, :, :3].mean(2) * a[:, :, 3] / 255          # white-on-black mask
    out = np.zeros(a.shape, np.uint8)
    out[:, :, :3] = g[None, :, :]; out[:, :, 3] = np.clip(cover, 0, 255)
    return Image.fromarray(out)


def heading(mode):
    """The mode's word art (black letters, white edge) with the flourish."""
    words, _ = art('040', 'MenTopUp_Lang0000')
    y0, y1 = MODES[mode]['head']
    hd = words.crop((0, int(y0 * words.height), words.width, int(y1 * words.height)))
    hd = fit(hd.crop(hd.getchannel('A').point(lambda a: 255 if a > 200 else 0).getbbox()), h=140)
    lay = Image.new('RGBA', (max(hd.width, 440) + 40, hd.height + 120)); lay.alpha_composite(hd, (0, 0))
    fl = flourish(430); lay.alpha_composite(fl, (max(0, int(hd.width / 2 - 215)), hd.height - 32))
    return lay


def spaced_text(d, xy, s, font, fill, spacing):
    """Text with extra space between letters, centred on xy."""
    widths = [d.textlength(c, font=font) for c in s]
    total = sum(widths) + spacing * (len(s) - 1)
    x = xy[0] - total / 2
    for c, w in zip(s, widths):
        d.text((x, xy[1]), c, font=font, fill=fill, anchor='lm'); x += w + spacing


def caption(mode):
    """The mode's description on the ground band, in the game's font."""
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    spaced_text(d, (W * 0.36, 978), MODES[mode]['caption'], ImageFont.truetype(config.GAME_FONT, 38), (246, 240, 228, 255), 4)
    return lay


# --- the ground band, the controls, the ink ornaments --------------------------------

def laurel(height, flip=False):
    """One laurel sprig (MenCmnBgUp0006s), black."""
    img, k = art('040', 'MenCmnBgUp0006s')
    sp = img.crop((0, 0, int(52 * k), int(122 * k)))
    sp = fit(mask(sp, (8, 6, 8)), h=height)
    return sp.transpose(Image.FLIP_LEFT_RIGHT) if flip else sp


def ground_band():
    """The black ground the characters stand on: a gently waving top edge,
    crossed laurel sprigs in the middle and at the right."""
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    pts = [(x, BAND_Y + 8 * math.sin(x / 260) + 5 * math.sin(x / 97 + 1)) for x in range(0, W + 1, 8)]
    d.polygon(pts + [(W, H), (0, H)], fill=(8, 6, 8, 255))
    for x, h in ((700, 150), (1830, 190)):
        l = laurel(h).rotate(18, expand=True, resample=Image.BICUBIC); r = laurel(h, True).rotate(-18, expand=True, resample=Image.BICUBIC)
        lay.alpha_composite(l, (int(x - l.width + 18), int(BAND_Y + 14 - l.height)))
        lay.alpha_composite(r, (int(x - 18), int(BAND_Y + 14 - r.height)))
    return lay


def controls():
    """The controls, bottom right: light keycaps, light words."""
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    fk = ImageFont.truetype(config.GAME_FONT, 21); fw = ImageFont.truetype(config.GAME_FONT, 25)
    items = [('▲▼', 'Choose'), ('Enter', 'Select'), ('Esc', 'Back')]
    def cap_w(k): return max(d.textlength(k, font=fk) + 22, 42)
    total = sum(cap_w(k) + 12 + d.textlength(w_, font=fw) for k, w_ in items) + 34 * (len(items) - 1)
    x = W - 70 - total; y = 1036
    for k, w_ in items:
        kw = cap_w(k)
        d.rounded_rectangle((x, y - 18, x + kw, y + 18), radius=7, fill=(240, 232, 214, 255))
        if k == '▲▼':      # two small triangles (the font has no arrow glyphs)
            cx = x + kw / 2
            d.polygon([(cx - 9, y - 1), (cx - 3, y - 1), (cx - 6, y - 8)], fill=(30, 22, 20, 255))
            d.polygon([(cx + 3, y - 7), (cx + 9, y - 7), (cx + 6, y)], fill=(30, 22, 20, 255))
        else:
            d.text((x + kw / 2, y), k, font=fk, fill=(30, 22, 20, 255), anchor='mm')
        d.text((x + kw + 12, y), w_, font=fw, fill=(240, 232, 214, 255), anchor='lm')
        x += kw + 12 + d.textlength(w_, font=fw) + 34
    return lay


def swirl():
    """The ink swirl top right: the ornament sheet's top branch
    (MenCmnBgUp0003s), its cut end off the right of the screen."""
    orn, _ = art('040', 'MenCmnBgUp0003s')
    top = top_piece(orn); bg = Image.new('RGBA', top.size, (0, 0, 0, 255)); bg.paste(top, (0, 0), top)
    return fit(mask(bg, BLACK), w=760).transpose(Image.FLIP_LEFT_RIGHT)


def sprig():
    """The ink plume by the window's foot (MenCmnBgUp0006s), only its own
    shape."""
    orn, k = art('040', 'MenCmnBgUp0006s')
    return fit(only_largest(mask(orn.crop((int(141 * k), int(120 * k), int(256 * k), int(256 * k))), BLACK)), h=300)
