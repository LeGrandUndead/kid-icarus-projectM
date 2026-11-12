# Main menu v10: v9 with the characters relit at compositing time (relight.py,
# from the normal buffers the renders now save): each character gets its
# stage's key colour, a shadow tint from the stage's colours, a rim of the
# stage's light colour on the side away from the key, and a little bounce
# from below. EVAL=1 with STILL=N prints the measurements (eval section).
#
# Main menu v9: v8 ("Ink & Paper poster") with the light and colour pass
# (claude/DESIGN_ANIMATION_BIBLE.md, section "Light, colour and integration"):
#  - each stage is a 3-stop gradient map in the mode's colours, kept in a
#    mid-dark band (perceptual lightness ~0.12-0.55) and slightly defocused,
#    so the full-colour character is the brightest, most saturated thing;
#  - one key light per mode, upper left, matching the light baked into the
#    renders: the sun, the glow and the rays all come from there; the side
#    away from it falls into a darker shadow family;
#  - the character is tied in: its darkest tones take the stage's shadow
#    hue, and the stage's light wraps round its edges;
#  - placements: headroom under the ornament, crops on tapering limbs
#    (shins, thighs), never on joints; similar sizes across modes.
#
# Below: the v8 notes, still true for layout and timing.
# Main menu v8, "Ink & Paper poster": one continuous take of the menu as a
# system. Built with the rulebook (skills game-motion-design, game-ui-ux,
# art-direction, game-camera-and-image).
#
# Identity (from the real KIU menu, menu 040): striped paper, the mode's
# emblem as a huge faded watermark, black ink ornaments and ground band,
# black word-art heading. Energy (from the poster tests): the mode's stage
# in a slanted window, the character big and breaking out of it.
#
# Colour script: paper = neutral 60%; each mode's own colour (Solo pink-red,
# Together amber, Vault green, Options purple) = 30% (watermark, window tint,
# paper tint, rim); gold = selection only. Values: paper light, ink black,
# window darkened into a narrow mid-dark range so the character is the
# strongest contrast.
#
# Timing chart (60 fps), 560 frames:
#   0-8      the paper wipes in from the left edge; 6-20 the ink band rises
#   4-10     the Solo window pulls back (anticipation); 10-22 it slams in;
#            Pit rides in 3 frames late
#   24-38    heading pops (shadow 3 f later), flourish draws; 28-46 buttons
#            arrive 3 f apart; 40-56 caption; 46-60 controls
#   130 / 230 / 320 / 420   hover changes (Together, Vault, Options, Together):
#            an ink brush sweeps the window (0-18 f, content swaps when covered),
#            the new character slides in with overshoot (8-24 f), the watermark
#            grows in (6-20 f), the paper tint shifts (0-12 f), the old heading
#            leaves in 7 f before the new one drops (5-19 f), caption 3 f later,
#            the selected button grows on a spring
#   452      click: button squash + confirm brighten + gold ring; menu leaves
#            (staggered ease-in, 12 f); the throw plays
#   496      the kick lands: 2 impact frames (ink silhouettes on bare paper),
#            hit-stop 10 f (fighters shake hard, window less), flash, feathers
#   522      ink line cuts across (4 f), halves part (ease-in, 16 f); the
#            Together screen's heading lands (overshoot)
#   python3 menu_v8.py  ->  v8_frames/NNNN.png     STILL=N (one frame, check/)   FROM/TO
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G, anim as A, glob
from PIL import ImageEnhance, ImageChops
N = 560; CLICK = 452; HIT = 496; HOLD = 10; CUT = 522
HOVERS = [(0, 0), (130, 1), (230, 2), (320, 3), (420, 1)]          # (frame, mode) the pointer selects
GOLD = (255, 208, 84); BLACK = (12, 8, 14)
STILL = int(os.environ.get('STILL', '-1'))

def faded(img, a):
    a = max(0.0, min(1.0, a))
    if a >= 0.999: return img
    o = img.copy(); o.putalpha(o.getchannel('A').point(lambda q: int(q * a))); return o
def scaled(img, sx, sy=None):
    sy = sx if sy is None else sy
    return img.resize((max(1, int(img.width * sx)), max(1, int(img.height * sy))), Image.BILINEAR)
def slant(x0, x1, y0, y1, lean): return [(x0, y0), (x1, y0), (x1 - lean, y1), (x0 - lean, y1)]
def mix(a, b, k): return tuple(int(x + (y - x) * k) for x, y in zip(a, b))
def tex(n): return Image.open(sorted(glob.glob(f'{S}/stages/tex/*/{n}.png'))[0]).convert('RGBA')

def active(v):
    """Selected mode at frame v, the previous one, and frames since the change."""
    cur, prev, t0 = 0, 0, 0
    for f, m in HOVERS:
        if v >= f: prev, cur, t0 = cur, m, f
    return cur, prev, v - t0

# --- paper field, tinted per mode ------------------------------------------------
PAPER = paper(seed=3).convert('RGB')
def paper_for(col): return Image.blend(PAPER, Image.new('RGB', (W, H), col), 0.10).convert('RGBA')
PAPERS = {i: paper_for(MODES[i]['color']) for i in range(4)}
EMB = {i: faded(emblem(MODES[i]), 0.55) for i in range(4)}

# --- the windows: each mode's stage, darkened into a narrow range, tinted ---------
PANEL = slant(900, W + 300, -40, H + 40, 330)
# per mode: shadow, mid, light of the stage's gradient map; the key light's colour;
# where the key light sits (upper left of the window, like the renders' light)
TUNE = dict(gain=0.62, glow=0.30, rays=0.14, wrap=0.35, lines=0.6, halo=0.2)   # tuned by measuring (EVAL)
import json as _json; TUNE.update(_json.loads(os.environ.get('TUNE', '{}')))
PAL = {0: dict(deep=(36, 22, 64), mid=(132, 70, 112), high=(250, 178, 150), key=(255, 214, 180), at=(1080, 90), gain=0.82),
       1: dict(deep=(26, 14, 18), mid=(88, 44, 34), high=(176, 112, 66), key=(255, 210, 140), at=(1180, 160)),
       2: dict(deep=(8, 22, 26), mid=(30, 66, 62), high=(104, 150, 128), key=(210, 255, 230), at=(1150, 120)),
       3: dict(deep=(18, 10, 32), mid=(60, 38, 92), high=(134, 108, 172), key=(232, 210, 255), at=(1150, 120))}
def graded(img, mode, size=None, glow_on=True):
    """The stage as a gradient map in the mode's colours, kept mid-dark."""
    pal = PAL[mode]
    sw, shh = size or (W + 120, H + 70)
    img = img.convert('RGB').resize((sw, shh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3.5))   # slight defocus
    a = np.asarray(img, np.float32) / 255
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lo, hi = np.percentile(lum, 2), np.percentile(lum, 98)
    t = np.clip((lum - lo) / max(1e-3, hi - lo), 0, 1)[..., None]
    deep, mid, high = (np.array(pal[k], np.float32) / 255 for k in ('deep', 'mid', 'high'))
    m = np.where(t < 0.5, deep + (mid - deep) * (t / 0.5), mid + (high - mid) * ((t - 0.5) / 0.5))
    m = m * 0.8 + a * 0.2 * 0.6                        # keep a little of the stage's own colour
    # light family / shadow family: brighter toward the key light, darker away from it
    yy, xx = np.mgrid[0:shh, 0:sw].astype(np.float32)
    kx, ky = pal['at']; d = np.hypot(xx - kx, yy - ky)
    glow = np.exp(-(d / 650) ** 2)[..., None]
    m = m * pal.get('gain', TUNE['gain']) * (0.5 + 0.5 * np.clip(1 - (d / 1900), 0, 1))[..., None]            # falloff toward the far corner
    if not glow_on: d = np.full_like(d, 900); glow = glow * 0
    m = 1 - (1 - m) * (1 - glow * TUNE['glow'] * np.array(pal['key'], np.float32) / 255)   # screen the key glow
    return Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
def solo_sky():
    sky = tex('a01m03_bg00').convert('RGB').crop((96, 0, 160, 118)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))
    sun = tex('a01m03_sun01').convert('RGB').resize((900, 900), Image.BICUBIC)
    c = Image.new('RGB', (W, H)); c.paste(sun, (1080 - 450, 90 - 450))      # the sun where the key light is
    return ImageChops.screen(sky, c)
def solo_clouds():
    """Chapter 1's own sky: its gradient, a sea of clouds below, puffs above.
    One tile W wide, repeated twice so it can scroll past Pit."""
    sky = tex('a01m03_bg00').convert('RGB').crop((96, 0, 160, 118)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4)).convert('RGBA')
    sea = tex('a01m01_ukumo_a').resize((480, 240), Image.BICUBIC)
    band = Image.new('RGBA', (W, 240)); [band.paste(sea, (x, 0)) for x in range(0, W, 480)]
    fade = Image.linear_gradient('L').resize((W, 240)); band.putalpha(ImageChops.multiply(band.getchannel('A'), fade))
    sky.alpha_composite(band, (0, H - 300))
    puff = tex('a01m03_kumo01').resize((640, 640), Image.BICUBIC)
    yy, xx = np.mgrid[0:640, 0:640]; soft = np.clip(1 - np.hypot(xx - 320, yy - 320) / 320, 0, 1) ** 1.5      # round, soft-edged
    puff.putalpha(Image.fromarray((np.asarray(puff.getchannel('A'), np.float32) * soft * 0.8).astype(np.uint8)))
    for x, y in [(0, -120), (640, 60), (1280, -200), (320, 330), (960, 300), (1600, 320)]:
        sky.alpha_composite(puff, (x, y))
        if x + 640 > W: sky.alpha_composite(puff, (x - W, y))
    tile = sky.convert('RGB'); two = Image.new('RGB', (2 * W, H)); two.paste(tile, (0, 0)); two.paste(tile, (W, 0))
    return two
def glow_layer(mode):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); kx, ky = PAL[mode]['at']
    g = np.exp(-(np.hypot(xx - kx, yy - ky) / 650) ** 2)[..., None] * TUNE['glow'] * 1.4 * np.array(PAL[mode]['key'], np.float32)
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert('RGBA')
GLOW0 = glow_layer(0)
STAGE = {0: graded(solo_clouds(), 0, size=(2 * W, H + 70), glow_on=False), 1: graded(Image.open('bg/together.png'), 1),
         2: graded(Image.open('bg/vault.png'), 2), 3: graded(Image.open('bg/options.png'), 3)}
RAYS = {}

# --- characters: frame index per mode, fixed placement per mode --------------------
CH_DIR = {0: f'{R}/poster_solo', 1: f'{R}/poster_tog', 2: f'{R}/vault', 3: f'{R}/options'}
def char_index(mode, v):
    if os.environ.get('CHAR_I'): return int(os.environ['CHAR_I'])     # for measuring one pose
    if mode == 0: return min(109, v)
    if mode == 1:
        if v >= CLICK + 4:
            c = 150 + (v - CLICK - 4)
            if c >= 190: c = 190 + max(0, v - HIT - HOLD)
            return min(215, c)
        if v >= 420: return min(149, 70 + int((v - 420) * 0.7))
        return min(149, int(max(0, v - 130) * 0.7))
    if mode == 2: return min(259, 150 + max(0, v - 236))         # she reacts to the selection: staff up, then the twirl
    return min(149, max(0, v - 320))
PLACE = {}
for mode, (h, cx, feet) in {0: (640, 1340, 880), 1: (940, 1400, H + 40), 2: (940, 1430, H + 60), 3: (1000, 1400, H + 60)}.items():
    ref = Image.open(f'{CH_DIR[mode]}/{[60, 100, 180, 60][mode]:04d}.png').getbbox()
    k = h / (ref[3] - ref[1]); PLACE[mode] = (k, cx - (ref[0] + ref[2]) / 2 * k, feet - ref[3] * k)
b190 = Image.open(f'{R}/poster_tog/0190.png').getbbox(); k1, x1, y1 = PLACE[1]
IMPACT = (int(x1 + (b190[0] + b190[2]) / 2 * k1), int(y1 + (b190[1] + 0.45 * (b190[3] - b190[1])) * k1))
for mode in range(4):    # rays from the key light (the kick's impact for Together)
    cx, cy = PAL[mode]['at'] if mode != 1 else IMPACT
    RAYS[mode] = G.backlight_rays((W, H), cx, cy, PAL[mode]['key'], n=24, length=1700, strength=TUNE['rays'])

import relight
BUF_DIR = {0: f'{R}/poster_solo_buf', 1: f'{R}/poster_tog_buf', 2: f'{R}/vault_buf', 3: f'{R}/options_buf'}
def mixw(c, k): return tuple(1 - (1 - x / 255) * k for x in c)        # a colour, k of the way from white
LIGHT = {m: dict(key=(-0.8, 0.5, 0.35), key_col=mixw(PAL[m]["key"], 0.45), dark=0.45,
                 shadow=mixw(PAL[m]["mid"], 0.35), rim=tuple(x / 255 for x in PAL[m]["high"]), rim_strength=1.8,
                 bounce=tuple(x / 255 for x in PAL[m]['mid']), bounce_strength=0.35) for m in range(4)}
for m in range(4): LIGHT[m].update(_json.loads(os.environ.get('LTUNE', '{}')))
RELIT = 0
def character(mode, v):
    global RELIT
    k, x0, y0 = PLACE[mode]; i = char_index(mode, v)
    if os.path.exists(f'{BUF_DIR[mode]}/{i:04d}_nrm.png'):
        im = relight.relight(f'{BUF_DIR[mode]}/{i:04d}', **LIGHT[mode]); RELIT += 1
    else:
        im = Image.open(f'{CH_DIR[mode]}/{i:04d}.png').convert('RGBA')
    return scaled(im, k), x0, y0

def integrate(ch, mode, panel, pos):
    """Tie a character into its stage: its darkest tones take the stage's shadow
    hue, and the stage's light wraps round the inside of its silhouette."""
    a = np.asarray(ch, np.float32) / 255; rgb, al = a[..., :3], a[..., 3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    deep = np.array(PAL[mode]['deep'], np.float32) / 255
    k = (np.clip(1 - lum / 0.5, 0, 1) ** 2 * 0.45)[..., None]           # only the darks, most in the darkest
    rgb = rgb + (deep * 1.6 - rgb) * k
    # light wrap: blurred stage, added just inside the edge
    x, y = pos; bg = Image.new('RGBA', ch.size); bg.paste(panel.crop((x, y, x + ch.width, y + ch.height)), (0, 0))
    bgb = np.asarray(bg.filter(ImageFilter.GaussianBlur(24)), np.float32)[..., :3] / 255
    am = Image.fromarray((al * 255).astype(np.uint8))
    inner = np.clip(al - np.asarray(am.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255, 0, 1)[..., None] * 1.6
    rgb = 1 - (1 - rgb) * (1 - np.clip(inner, 0, 1) * bgb * TUNE['wrap'])
    out = np.dstack([np.clip(rgb, 0, 1), al])
    return Image.fromarray((out * 255).astype(np.uint8), 'RGBA')

def speed_lines(cx, cy, seed, strength, col=(240, 230, 255), n=60):
    sl = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(sl); rnd = random.Random(seed)
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(300, 460); r1 = r0 + rnd.uniform(500, 1400); w = rnd.uniform(0.003, 0.010)
        d.polygon([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a - w) * r1, cy + math.sin(a - w) * r1),
                   (cx + math.cos(a + w) * r1, cy + math.sin(a + w) * r1)], fill=col + (int(rnd.uniform(60, 150) * strength),))
    return sl

# --- menu pieces -------------------------------------------------------------------
def heading(i):
    y0, y1 = MODES[i]['head']
    hd = HEADS.crop((0, int(y0 * HEADS.height), HEADS.width, int(y1 * HEADS.height)))
    hd = fit(hd.crop(hd.getchannel('A').point(lambda a: 255 if a > 200 else 0).getbbox()), h=140)
    lay = Image.new('RGBA', (max(hd.width, 440) + 40, hd.height + 120)); lay.alpha_composite(hd, (0, 0))
    fl = flourish_v4(430); lay.alpha_composite(fl, (max(0, int(hd.width / 2 - 215)), hd.height - 32))
    return lay
HEAD = {i: heading(i) for i in range(4)}
def caption(i):
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    spaced_text(d, (W * 0.36, 978), MODES[i]['cap'], ImageFont.truetype(GAME_FONT, 38), (246, 240, 228, 255), 4)
    return lay
CAP = {i: caption(i) for i in range(4)}
BAND = ground_band()
ORN, _k = art('040', 'MenCmnBgUp0003s')
def top_piece(img):
    """Only the ornament piece(s) touching the top edge: a crop box would slice
    through the neighbouring ornaments of the sheet."""
    from scipy.ndimage import label
    a = np.asarray(img.convert('L'), np.float32) > 60; lab, n = label(a)
    keep = [i for i in range(1, n + 1) if np.nonzero(lab == i)[0].min() < 4]
    m = np.isin(lab, keep); out = img.convert('RGB').copy(); out.putalpha(Image.fromarray((m * 255).astype(np.uint8)))
    return out.crop(out.getchannel('A').getbbox())
_top = top_piece(ORN); _bg = Image.new("RGBA", _top.size, (0, 0, 0, 255)); _bg.paste(_top, (0, 0), _top)
SWIRL = fit(mask(_bg, BLACK), w=760).transpose(Image.FLIP_LEFT_RIGHT)   # top branch: its cut end (the sheet's edge) goes off the right of the screen
ORN6, _k6 = art('040', 'MenCmnBgUp0006s')
SPRIG = fit(mask(ORN6.crop((int(141 * _k6), int(120 * _k6), int(256 * _k6), int(256 * _k6))), BLACK), h=300)  # ink plume
CTRL = controls_v4()
FLASH = fx_tex('doll_008_doll', 'ptc_cmn_flashA'); HANE = fx_tex('demo_024_demo', 'ptc_c05_040_hane')

COL_Y0, COL_KY, BS = 200 / U, 0.72, 0.40      # the column sits under the heading (5% safe area)
def buttons(emph, t, press=None):
    """The vine and the four buttons; emph[node] in 0..1 is how selected each is."""
    lay = Image.new('RGBA', (W, H)); s = BS; rects = []; placed = []
    for (r, rot, (x, y), ang, node), p in zip(ITEMS, BTN):
        y = COL_Y0 + y * COL_KY
        dy = math.sin(t * 1.3 + node * 2.1) * 1.2; dx = math.sin(t * 0.9 + node * 1.7) * 0.7
        w, h = p.width / kA * s, p.height / kA * s
        rects.append((x + dx, y + dy, x + dx + w, y + dy + h)); placed.append((p, x + dx, y + dy, w, h, ang, node))
    big = Image.new('L', (W * 2, H * 2), 0); d = ImageDraw.Draw(big)
    for poly in vine(rects): d.polygon([(px * U * 2, py * U * 2) for px, py in poly], fill=255)
    mv = big.resize((W, H), Image.LANCZOS)
    blk = Image.new('RGBA', (W, H), BLACK + (255,)); blk.putalpha(mv); lay.alpha_composite(blk)
    for p, x, y, w, h, ang, node in sorted(placed, key=lambda e: emph.get(e[6], 0)):
        e = emph.get(node, 0.0)
        bw = w * U * (1 + 0.16 * e)
        b = fit(p, w=bw)
        if press and press[0] == node:
            sx, sy = A.squash(press[1], press[2]); b = scaled(b, sx, sy)
            if press[2] <= press[1] < press[2] + 4:
                wl = Image.new('RGBA', b.size, (255, 250, 230, 0)); wl.putalpha(b.getchannel('A').point(lambda q: int(q * 0.45))); b = b.copy(); b.alpha_composite(wl)
        b = glint(b, t) if e > 0.6 else step_back(b, 1 - e)
        lift = 0.16 * e * h * U / 2 if node == 3 else 0
        put(lay, b, x * U + w * U / 2 + 22 * e, y * U + h * U / 2 - lift, anchor='c', sh=(8, 0.5, 8, 12),
            gl=(12, 13, GOLD, 0.9 * e) if e > 0.05 else None, rot=ang)
    return lay
def button_centre(node):
    (r, rot, (x, y), ang, n), p = ITEMS[node], BTN[node]
    y = COL_Y0 + y * COL_KY; w, h = p.width / kA * BS, p.height / kA * BS
    return x * U + w * U / 2, y * U + h * U / 2

EV = {}
def frame(v):
    cur, prev, ts = active(v)
    # 1. paper: wipe in from the left edge; its tint follows the selection
    page = Image.new('RGBA', (W, H), BLACK + (255,))
    pk = A.track(ts, [(0, 0), (12, 1, 'in_out')]) if v >= HOVERS[1][0] else 1
    pap = Image.blend(PAPERS[prev], PAPERS[cur], pk) if pk < 1 else PAPERS[cur]
    page.alpha_composite(pap, (int(A.track(v, [(0, -W), (8, 0, 'out')])), 0))
    # 2. watermark: grows in for the new mode, the old one fades
    if v >= HOVERS[1][0] and ts < 10: page.alpha_composite(faded(EMB[prev], 1 - A.track(ts, [(0, 0), (8, 1, 'in')])), (-180, 0))
    es = A.track(ts, [(6, 0.86), (20, 1.0, 'out_back')]) if v >= HOVERS[1][0] else A.track(v, [(10, 0.86), (28, 1.0, 'out_back')])
    ea = A.track(ts, [(6, 0), (12, 1)]) if v >= HOVERS[1][0] else A.track(v, [(10, 0), (18, 1)])
    em = scaled(EMB[cur], es); page.alpha_composite(faded(em, ea), (int(-180 + EMB[cur].width * (1 - es) / 2), int(EMB[cur].height * (1 - es) / 2)))
    # 3. the window: slams in on entry; on a hover an ink brush sweeps right to left
    #    and wipes the new mode in behind it (old content ahead of the brush, new behind)
    pdx = A.track(v, [(0, 1500), (6, 1500), (20, 0, 'out_back')])
    swap = v >= HOVERS[1][0] and ts < 20
    hitstop = HIT <= v < HIT + HOLD
    sx_hit, sy_hit = A.shake(v, HIT, HOLD + 10, 6, 'x', seed=2); vx_hit, _ = A.shake(v, HIT, HOLD + 10, 20, 'x', seed=3)
    kx, _ = A.shake(v, 20, 8, 7, 'x', seed=1)
    mk = Image.new('L', (W, H)); ImageDraw.Draw(mk).polygon([(x + pdx, y) for x, y in PANEL], fill=255)
    cz = A.track(v, [(HIT - 6, 1.0), (HIT, 0.98, 'in_out'), (HIT + 4, 1.06, 'out'), (CUT, 1.03, 'out')]) if cur == 1 and v >= HIT - 6 else 1.0
    def content(mode, slide):
        win = Image.new('RGBA', (W, H)); o = int(60 + 40 * math.sin(v / 100))
        if mode == 0: o = int(v * 7) % W                     # the clouds stream past Pit
        win.paste(STAGE[mode].crop((o, 30, o + W, 30 + H)), (0, 0))
        if mode == 0: win = G.add(win, GLOW0)
        win = G.add(win, faded(RAYS[mode], A.track(v, [(16, 0), (38, 1)])))
        sl = (1.0 if v < 32 or hitstop else 0.35 * TUNE['lines']) if mode == 1 else 0.25 * TUNE['lines']
        if v >= 20: win.alpha_composite(speed_lines(1400 if mode != 1 else IMPACT[0], 500 if mode != 1 else IMPACT[1], (v // 2) if not hitstop else 999, sl, mix(MODES[mode]['color'], (255, 255, 255), 0.6)))
        panel = Image.new('RGBA', (W, H)); panel.paste(win, (int(sx_hit + kx), int(sy_hit)), mk)
        ch, x0, y0 = character(mode, v)
        if cz != 1.0: ch = scaled(ch, cz); x0 -= (cz - 1) * (IMPACT[0] - x0); y0 -= (cz - 1) * (IMPACT[1] - y0)
        pos = (int(x0 + slide + vx_hit), int(y0))
        ch = integrate(ch, mode, panel, pos)
        if TUNE['halo'] > 0:
            # a soft shadow round the silhouette: the stage drops in value right next to the character
            q = 4; hal = Image.new('L', (W // q, H // q)); hal.paste(scaled(ch.getchannel('A'), 1 / q), (pos[0] // q, pos[1] // q))
            hal = np.asarray(hal.filter(ImageFilter.GaussianBlur(45 / q)).resize((W, H), Image.BILINEAR), np.float32) / 255
            pa = np.asarray(panel, np.float32); pa[..., :3] *= (1 - TUNE['halo'] * np.clip(hal * 1.6, 0, 1))[..., None]
            panel = Image.fromarray(pa.astype(np.uint8), 'RGBA')
        cl = Image.new('RGBA', (W, H))
        EV['mask'] = mk; EV['char'] = (ch, pos)
        cl.alpha_composite(soft_glow(ch, mix(MODES[mode]['color'], (255, 240, 220), 0.5), 0.5, 22), pos); cl.alpha_composite(ch, pos)
        return panel, cl, ch, pos
    if v < HOVERS[1][0]:
        panel, cl, ch, pos = content(cur, A.track(v, [(0, 1500), (9, 1500), (23, 0, 'out_back')]))
    elif not swap:
        panel, cl, ch, pos = content(cur, 0)
    else:
        bx = A.track(ts, [(0, 2800), (18, 300, 'in_out')])
        newm = Image.new('L', (W, H)); ImageDraw.Draw(newm).polygon(slant(bx, W + 2000, -40, H + 40, 330), fill=255)
        oldm = Image.new('L', (W, H)); ImageDraw.Draw(oldm).polygon(slant(-2000, bx - 520, -40, H + 40, 330), fill=255)
        brush = Image.new('L', (W, H)); ImageDraw.Draw(brush).polygon(slant(bx - 520, bx, -40, H + 40, 330), fill=255)
        po, co, _, _ = content(prev, -60 * A.track(ts, [(0, 0), (18, 1, 'in')]))
        pn, cn, ch, pos = content(cur, A.track(ts, [(0, 260), (20, 0, 'out_back')]))
        panel = Image.new('RGBA', (W, H)); panel.paste(po, (0, 0), oldm); panel.paste(pn, (0, 0), newm)
        ink = Image.new('RGBA', (W, H), BLACK + (255,)); panel.paste(ink, (0, 0), ImageChops.multiply(brush.filter(ImageFilter.GaussianBlur(2)), mk))
        cl = Image.new('RGBA', (W, H)); cl.paste(co, (0, 0), oldm); cl.paste(cn, (0, 0), newm)
    show = cur if not swap or ts >= 9 else prev
    d = ImageDraw.Draw(panel)
    d.line([(PANEL[0][0] + pdx, PANEL[0][1]), (PANEL[3][0] + pdx, PANEL[3][1])], fill=BLACK + (255,), width=24)
    d.line([(PANEL[0][0] + pdx + 13, PANEL[0][1]), (PANEL[3][0] + pdx + 13, PANEL[3][1])], fill=mix(MODES[prev]['color'], MODES[cur]['color'], A.track(ts, [(0, 0), (18, 1)]) if swap else 1) + (255,), width=6)
    impact_frame = HIT <= v < HIT + 2
    if impact_frame:
        # impact frames in KIU's own ink look: black silhouettes and lines on bare paper
        page = PAPERS[1].copy()
        page.alpha_composite(speed_lines(IMPACT[0], IMPACT[1], 1000 + v, 1.0, BLACK, n=90))
        sil = Image.new('RGBA', ch.size, BLACK + (0,)); sil.putalpha(ch.getchannel('A')); page.alpha_composite(sil, pos)
        page.alpha_composite(BAND)
    else:
        page.alpha_composite(panel)
        page.alpha_composite(cl)
        if v >= 14: particles(page, {0: 'solo', 1: 'together', 2: 'vault', 3: 'options'}[show], v / 60, 1400, 520)
        if v >= HIT + 2:
            t = v - HIT - 2; lay = Image.new('RGBA', (W, H))
            if t < 22:
                sz = int(400 + 1000 * A.out(min(1, t / 6))); fa = 1 - A.clamp01((t - 4) / 18)
                lay.alpha_composite(faded(additive_sprite(FLASH, (255, 220, 160), (sz, sz)), fa), (IMPACT[0] - sz // 2, IMPACT[1] - sz // 2)); page = G.add(page, lay)
            if t < 70:
                fl = Image.new('RGBA', (W, H)); rnd = random.Random(8)
                for n in range(30):
                    an = rnd.uniform(0, 2 * math.pi); sp = rnd.uniform(10, 26)
                    dd = 100 + sp * 14 * A.out(min(1, t / 14)) + sp * max(0, t - 14) * 0.6
                    sp_ = faded(additive_sprite(HANE, (255, 255, 255) if n % 3 else (120, 90, 170), (84, 42)).rotate(math.degrees(-an) + t * 6, expand=True), 1 - A.clamp01((t - 40) / 30))
                    fl.alpha_composite(sp_, (int(IMPACT[0] + math.cos(an) * dd - sp_.width / 2), int(IMPACT[1] + math.sin(an) * dd + 0.12 * t * t - sp_.height / 2)))
                page.alpha_composite(fl)
            if t < 8: page.alpha_composite(Image.new('RGBA', (W, H), (255, 244, 220, int(150 * (1 - t / 8)))))
        # ink ornaments framing the window, the ground band
        page.alpha_composite(SWIRL, (int(W - SWIRL.width + 40 + pdx), -30))
        page.alpha_composite(BAND, (0, int(A.track(v, [(6, 200), (20, 0, 'out')]))))
        page.alpha_composite(SPRIG, (int(780 - SPRIG.width / 2), int(BAND_Y - SPRIG.height + 40 + A.track(v, [(8, 260), (22, 0, 'out')]))))
    page = G.bloom(page, threshold=0.9, strength=0.22)
    page = G.grade(page, warm=(1.04, 1.0, 0.95), cool=(0.95, 0.95, 1.05), vignette=0.16)
    # 5. the menu
    out_k = [A.track(A.stagger(v, CLICK + 4, i, 3), [(0, 0), (12, 1, 'in')]) for i in range(5)]
    # heading: pops in on entry; on a hover change the old leaves (7 f) before the new drops (5-19 f)
    def put_head(i, a, s, yoff):
        if a <= 0.01: return
        hh = scaled(HEAD[i], s); page.alpha_composite(faded(hh, a), (int(100 + HEAD[i].width * (1 - s) / 2), int(64 + HEAD[i].height * (1 - s) / 2 + yoff)))
    if v < HOVERS[1][0]:
        put_head(cur, A.track(v, [(24, 0), (30, 1)]), A.track(v, [(24, 0.6), (38, 1.0, 'out_back')]), 0)
    else:
        if ts < 8: put_head(prev, 1 - A.track(ts, [(0, 0), (7, 1, 'in')]), 1.0, -50 * A.track(ts, [(0, 0), (7, 1, 'in')]))
        if ts >= 8: put_head(cur, A.track(ts, [(8, 0), (12, 1)]) * (1 - out_k[0]), A.track(ts, [(8, 0.6), (22, 1.0, 'out_back')]), -260 * out_k[0])
    # buttons
    emph = {}
    for f, m in HOVERS:
        if v >= f:
            emph = {mm: 0.0 for mm in range(4)}
    cur_k = A.track(ts, [(0, 0), (15, 1, 'spring')]) if v >= HOVERS[1][0] else A.track(v, [(48, 0), (60, 1, 'spring')])
    old_k = 1 - A.track(ts, [(0, 0), (9, 1, 'in')])
    emph[cur] = cur_k
    if v >= HOVERS[1][0] and prev != cur: emph[prev] = max(emph.get(prev, 0), old_k)
    press = (1, v, CLICK) if v >= CLICK else None
    bl = buttons(emph, v / 60, press)
    ba = A.track(v, [(28, 0), (40, 1)]); bx = -560 * (1 - A.track(v, [(28, 0), (46, 1, 'out_back')])) - 900 * out_k[1]
    page.alpha_composite(faded(bl, ba), (int(bx), 0))
    if CLICK <= v < CLICK + 18:
        t = (v - CLICK) / 18; r = 60 + 340 * A.out(t); bx_, by_ = button_centre(1)
        ring = Image.new('RGBA', (W, H)); ImageDraw.Draw(ring).ellipse((bx_ - r, by_ - r * 0.55, bx_ + r, by_ + r * 0.55), outline=GOLD + (int(255 * (1 - t)),), width=int(10 * (1 - t)) + 2)
        page = G.add(page, ring.filter(ImageFilter.GaussianBlur(3))); page.alpha_composite(ring)
    # caption swaps 3 f after the heading; controls
    if v < HOVERS[1][0]: page.alpha_composite(faded(CAP[cur], A.track(v, [(40, 0), (56, 1)])), (0, int(A.track(v, [(40, 30), (56, 0, 'out')]))))
    else:
        if ts < 7: page.alpha_composite(faded(CAP[prev], 1 - A.track(ts, [(0, 0), (6, 1, 'in')])))
        if ts >= 11: page.alpha_composite(faded(CAP[cur], A.track(ts, [(11, 0), (19, 1)]) * (1 - out_k[3])), (0, int(A.track(ts, [(11, 24), (23, 0, 'out')]) + 160 * out_k[3])))
    page.alpha_composite(faded(CTRL, A.track(v, [(46, 0), (60, 1)]) * (1 - out_k[4])), (0, int(160 * out_k[4])))
    # pointer: arcs between the buttons, arriving on each hover frame
    if 70 <= v < CLICK + 8:
        stops = [(70, (W * 0.9, H * 0.92))] + [(f, button_centre(m)) for f, m in HOVERS[1:]]
        px, py = stops[-1][1]
        for (fa, pa), (fb, pb) in zip(stops, stops[1:]):
            if fa <= v < fb:
                t = A.in_out(A.clamp01((v - (fb - 30)) / 30)) if fb - fa > 30 else A.in_out((v - fa) / (fb - fa))
                mx, my = (pa[0] + pb[0]) / 2 + 80, (pa[1] + pb[1]) / 2
                px = (1 - t) ** 2 * pa[0] + 2 * (1 - t) * t * mx + t * t * pb[0]; py = (1 - t) ** 2 * pa[1] + 2 * (1 - t) * t * my + t * t * pb[1]
                break
        px += 70; py += 10
        s = 1.3 * (0.88 if CLICK <= v < CLICK + 5 else 1.0); pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
        ImageDraw.Draw(page).polygon([(px + x * s, py + y * s) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    # 6. the cut: an ink line, then the halves part onto the Together screen
    if v >= CUT:
        ang = math.radians(-62); ux, uy = math.cos(ang), math.sin(ang); nx, ny = -uy, ux; L = 3000; c0 = (W * 0.55, H * 0.5)
        msk = Image.new('L', (W, H)); ImageDraw.Draw(msk).polygon([(c0[0] - ux * L, c0[1] - uy * L), (c0[0] + ux * L, c0[1] + uy * L), (c0[0] + ux * L + nx * L, c0[1] + uy * L + ny * L), (c0[0] - ux * L + nx * L, c0[1] - uy * L + ny * L)], fill=255)
        gap = 1500 * A.track(v, [(CUT + 6, 0), (CUT + 22, 1, 'in')])
        base = PAPERS[1].copy(); base.alpha_composite(EMB[1], (-180, 0)); base.alpha_composite(BAND)
        if v >= CUT + 12:
            s_ = A.track(v, [(CUT + 12, 0.55), (CUT + 26, 1.0, 'out_back')]); hh = scaled(HEAD[1], 1.9 * s_)
            base.alpha_composite(faded(hh, A.track(v, [(CUT + 12, 0), (CUT + 16, 1)])), (int(W / 2 - hh.width / 2), int(H / 2 - hh.height / 2 - 40)))
        A1 = Image.new('RGBA', (W, H)); A1.paste(page, (0, 0), msk); B1 = Image.new('RGBA', (W, H)); B1.paste(page, (0, 0), ImageChops.invert(msk))
        base.alpha_composite(A1.transform((W, H), Image.AFFINE, (1, 0, -nx * gap, 0, 1, -ny * gap)))
        base.alpha_composite(B1.transform((W, H), Image.AFFINE, (1, 0, nx * gap, 0, 1, ny * gap)))
        lt = A.track(v, [(CUT, 0), (CUT + 4, 1, 'out')]); la = 1 - A.track(v, [(CUT + 10, 0), (CUT + 18, 1)])
        if la > 0:
            ln = Image.new('RGBA', (W, H)); Lh = 2600 * lt
            ImageDraw.Draw(ln).line((c0[0] - ux * Lh, c0[1] - uy * Lh, c0[0] + ux * Lh, c0[1] + uy * Lh), fill=BLACK + (int(255 * la),), width=int(16 * la) + 3)
            base.alpha_composite(ln)
        page = base
    return page

def local_edge_contrast(Lp, ca, win, vis, r=10):
    """Median, along the silhouette, of |lightness just inside - just outside|:
    does the character's outline separate from what is right behind it?"""
    from scipy.ndimage import gaussian_filter
    def blur(x): return gaussian_filter(x.astype(np.float32), r)
    inside = (ca > 0.9).astype(np.float32); outside = ((ca < 0.05) & (win > 0.5)).astype(np.float32)
    li = blur(Lp * inside) / np.maximum(blur(inside), 1e-3); lo = blur(Lp * outside) / np.maximum(blur(outside), 1e-3)
    edge = (ca > 0.3) & (ca < 0.9) & vis & (blur(inside) > 0.2) & (blur(outside) > 0.2)
    return float(np.median(np.abs(li - lo)[edge])) if edge.any() else 0.0

def evaluate(page):
    """The numbers I check myself against (rulebook section 14)."""
    def L(a):
        a = a / 255; lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        return np.cbrt(lin @ np.array([0.2126, 0.7152, 0.0722]))
    img = np.asarray(page.convert('RGB'), np.float32); Lp = L(img)
    ch, (x, y) = EV['char']; ca = Image.new('L', (W, H)); ca.paste(ch.getchannel('A'), (x, y))
    ca = np.asarray(ca, np.float32) / 255; win = np.asarray(EV['mask'], np.float32) / 255
    vis = np.zeros((H, W), bool); vis[:BAND_Y - 10] = True             # above the ground band
    stage = (win > 0.5) & (ca < 0.05) & vis & (Lp > 0.08);      # not the black ink
    body = (ca > 0.9) & vis
    near = np.asarray(Image.fromarray((ca * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(25)), np.float32) / 255
    ring = (near > 0.5) & (ca < 0.05) & vis & (win > 0.5)
    inner = np.asarray(Image.fromarray((ca * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(25)), np.float32) / 255
    edge_in = (ca > 0.9) & (inner < 0.5) & vis
    ys, xs = np.nonzero(ca > 0.5); total = (ca > 0.5).sum()
    full = Image.new('L', (W + 4000, H + 4000)); full.paste(ch.getchannel('A'), (x + 2000, y + 2000)); fa = np.asarray(full) > 128
    inside = fa[2000:2000 + H, 2000:2000 + W].sum(); above_band = fa[2000:2000 + BAND_Y, 2000:2000 + W].sum()
    r = dict(stage_med=np.median(Lp[stage]), stage_p10=np.percentile(Lp[stage], 10), stage_p90=np.percentile(Lp[stage], 90),
             body_p90=np.percentile(Lp[body], 90), body_med=np.median(Lp[body]),
             edge_contrast=local_edge_contrast(Lp, ca, win, vis),
             shown=above_band / fa.sum(), offscreen=1 - inside / fa.sum(), top=int(ys.min()) if len(ys) else -1,
             relit=RELIT)
    return {k: (round(float(v), 3) if not isinstance(v, int) else v) for k, v in r.items()}

if __name__ == '__main__':
    out = 'v10_frames'; os.makedirs(out, exist_ok=True)
    frames = [STILL] if STILL >= 0 else range(int(os.environ.get('FROM', '0')), int(os.environ.get('TO', N)))
    for v in frames:
        p = frame(v)
        if STILL >= 0: p.convert('RGB').save(f'check/v10_{v:04d}.png')
        if os.environ.get('EVAL'): print(v, evaluate(p))
        else: p.convert('RGB').save(f'{out}/{v:04d}.png')
    print('v10', len(frames))
