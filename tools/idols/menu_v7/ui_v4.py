# Layout v4 pieces (rewritten 2026-11-12 after the work folder was lost),
# used by the Dream layout (still_v6.py, cast_menu_v7.py, solo_sky_v7.py):
#   heading + flourish, the black ground band with laurels, the caption in
#   the game's font, the controls panel, a soft glow, and the game's own
#   particle images (from the effect files, converted with `dump ... textures`).
# Needs menu_anim.py loaded first (W, H, U, S, art, fit, mask, put, heads, MODES, ui_).
import numpy as np, math, random, os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

GAME_FONT = S + '/mock/Montserrat-Regular.otf'   # the 3DS shared font is drawn from Montserrat Regular
HEADS = heads                  # the modes' headings (black letters, white edge)
HEAD_X = W * 0.445             # centre of the heading
BAND_Y = 905                   # top of the black ground band

def flourish_v4(width):
    """The flourish under the heading (MenTopUp0000), coloured with the
    game's own gradient strip (MenTopUp0001: magenta, blue, cyan)."""
    half, _ = art('040', 'MenTopUp0000')             # the left half; the game mirrors it
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

def laurel(height, flip=False):
    """One laurel sprig (MenCmnBgUp0006s), black."""
    img, k = art('040', 'MenCmnBgUp0006s')
    sp = img.crop((0, 0, int(52 * k), int(122 * k)))
    sp = fit(mask(sp, (8, 6, 8)), h=height)
    return sp.transpose(Image.FLIP_LEFT_RIGHT) if flip else sp

def ground_band():
    """The black ground the characters stand on: a gently waving top edge,
    a pair of crossed laurel sprigs in the middle and one at the right."""
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    pts = [(x, BAND_Y + 8 * math.sin(x / 260) + 5 * math.sin(x / 97 + 1)) for x in range(0, W + 1, 8)]
    d.polygon(pts + [(W, H), (0, H)], fill=(8, 6, 8, 255))
    for x, h in ((700, 150), (1830, 190)):
        l = laurel(h).rotate(18, expand=True, resample=Image.BICUBIC); r = laurel(h, True).rotate(-18, expand=True, resample=Image.BICUBIC)
        lay.alpha_composite(l, (int(x - l.width + 18), int(BAND_Y + 14 - l.height)))
        lay.alpha_composite(r, (int(x - 18), int(BAND_Y + 14 - r.height)))
    return lay

def spaced_text(d, xy, s, font, fill, spacing):
    """Text with extra space between letters, centred on xy."""
    widths = [d.textlength(c, font=font) for c in s]
    total = sum(widths) + spacing * (len(s) - 1)
    x = xy[0] - total / 2
    for c, w in zip(s, widths):
        d.text((x, xy[1]), c, font=font, fill=fill, anchor='lm'); x += w + spacing

def caption_band(m):
    """The mode's description on the band, in the game's font."""
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    spaced_text(d, (W / 2, 985), m['cap'], ImageFont.truetype(GAME_FONT, 40), (242, 236, 224, 255), 6)
    return lay

def controls_v4():
    """The controls: light keycaps, light words, bottom right."""
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    fk = ImageFont.truetype(GAME_FONT, 21); fw = ImageFont.truetype(GAME_FONT, 25)
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

def buttons_v4(sel, t):
    return ui_(sel, t)

def soft_glow(img, color, strength=0.35, radius=18):
    """A soft light around a rendered character (the 3DS's low resolution
    softens everything; at 1080p a little glow brings that back)."""
    a = img.getchannel('A').filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * strength))
    g = Image.new('RGBA', img.size, color + (0,)); g.putalpha(a); return g

# --- the game's particles ----------------------------------------------------
FX = {}
def fx_tex(key, name):
    """A particle image from a converted effect file (S/fx/<key>), as an
    RGBA array, top row first."""
    if (key, name) not in FX:
        for line in open(f'{S}/fx/{key}/textures.txt'):
            n, w, h = line.split('\t')
            if n == name:
                a = np.fromfile(f'{S}/fx/{key}/{n}.rgba', np.uint8).reshape(int(h), int(w), 4)[::-1]
                FX[key, name] = np.ascontiguousarray(a)
    return FX[key, name]

def mirrored(a):
    """Some particle images are a quarter of the shape; the game mirrors
    them on both axes to complete it."""
    top = np.concatenate([a[:, ::-1], a], 1)
    return np.concatenate([top[::-1], top], 0)

def additive_sprite(a, color, size):
    """A greyscale particle image as a light of `color`: coverage =
    luminance x alpha (the game draws these additively)."""
    a = np.asarray(a, np.float32)
    cover = a[:, :, :3].mean(2) * a[:, :, 3] / 255
    out = np.zeros(a.shape, np.uint8); out[:, :, :3] = color; out[:, :, 3] = np.clip(cover, 0, 255)
    return Image.fromarray(out).resize((max(1, int(size[0])), max(1, int(size[1]))), Image.BILINEAR)

_P = {}
def _parts():
    if not _P:
        _P['hane'] = fx_tex('demo_024_demo', 'ptc_c05_040_hane')
        _P['kona'] = fx_tex('demo_051_demo', 'ptc_c11_030_konaA')
        leaf = fx_tex('demo_051_demo', 'ptc_c11_030_NatLeaf')
        _P['leaves'] = [leaf[y:y + 32, x:x + 32] for x in (0, 32) for y in (0, 32)]
        _P['flash'] = fx_tex('doll_008_doll', 'ptc_cmn_flashA')
        _P['spark'] = mirrored(fx_tex('demo_024_demo', 'ptc_c05_040_hikari01'))
    return _P

def particles(page, mode, t, cx, cy):
    """Particles drifting around the character, each mode with its own:
    together and solo: feathers; vault: twinkling sparks; options: leaves and
    powder. Deterministic in t (one seed per mode)."""
    P = _parts(); rnd = random.Random({'together': 1, 'vault': 2, 'options': 3, 'solo': 4}[mode])
    lay = Image.new('RGBA', (W, H))
    for k in range(44):
        x0 = rnd.uniform(cx - 620, cx + 520); sp = rnd.uniform(25, 70); ph = rnd.uniform(0, 1)
        sway = rnd.uniform(20, 60); size = rnd.uniform(0.7, 1.4); spin = rnd.uniform(-90, 90)
        if mode == 'options':           # leaves fall
            y = ((t * sp + ph * (H + 200)) % (H + 200)) - 100
        else:                            # feathers and sparks rise
            y = H + 100 - ((t * sp + ph * (H + 200)) % (H + 200))
        x = x0 + math.sin(t * 0.9 + k) * sway
        fade = min(1, max(0, (BAND_Y - y) / 120)) * min(1, max(0, (y + 60) / 160))
        if fade <= 0: continue
        if mode in ('together', 'solo'):
            col = (255, 255, 255) if k % 3 else (255, 200, 220)
            s = additive_sprite(P['hane'], col, (44 * size, 22 * size)).rotate(spin + t * 40, expand=True)
        elif mode == 'vault':
            tw = 0.5 + 0.5 * math.sin(t * 4 + k * 1.7)
            s = additive_sprite(P['spark'], (200, 255, 240), (26 * size * (0.6 + 0.6 * tw), 26 * size * (0.6 + 0.6 * tw)))
        else:
            if k % 3 == 0:
                s = additive_sprite(P['kona'], (255, 235, 248), (56 * size, 28 * size))
            else:
                s = additive_sprite(P['leaves'][k % 4], (255, 228, 240) if k % 2 else (255, 160, 205), (48 * size, 48 * size)).rotate(spin + t * 60, expand=True)
        s.putalpha(s.getchannel('A').point(lambda v, f=fade: int(v * f)))
        lay.alpha_composite(s, (int(x - s.width / 2), int(y - s.height / 2)))
    page.alpha_composite(lay)
