# Skyworld v2 (Vault), rebuilt with the motion notes and anim.py.
#
# Colour plan: a deeper sky (60% blue), marble islands and clouds kept a step
# darker than the characters (30%), gold only for the selection: the hovered
# banner, its beam and a warm light on its island.
#
# Timing chart (frames, 60 fps), 300 frames:
#   0-36     the islands rise into place, far to near, 4 frames apart (overshoot)
#   24-45    the banners pop in, 3 frames apart; Together's takes the selection
#   30-52    heading, caption, controls (3 frames apart)
#   52-112   moving hold at Together's island; the pointer arcs toward Vault
#   112      hover Vault: Together's banner shrinks (9 f, ease-in), Vault's grows
#            (spring); the heading swaps (old leaves 9 f, new drops 3 f later)
#   116-124  anticipation: the camera leans left
#   124-178  the glide to Vault (ease-in-out), settling on a spring until ~196
#   182-214  Palutena dips into the clouds, then rises (overshoot)
#   214-250  moving hold; the staff and the banner glint
#   250      click: the banner squashes and flashes, a gold ring
#   254-262  the menu leaves (staggered); 256-264 the camera pulls back
#   264-284  the dive: the camera rushes in (ease-in), speed lines, blur
#   282-286  white; 286-300 the Vault screen's heading lands
#   python3 d2_v2.py  ->  d2v2_frames/NNNN.png      STILL=N: one frame in check/
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G, glob, anim as A
from PIL import ImageEnhance, ImageChops
N = 300; HOVER = 112; CLICK = 250
INK = (12, 14, 30); GOLD = (255, 208, 84); STILL = int(os.environ.get('STILL', '-1'))
def tex(n): return Image.open(sorted(glob.glob(f'{S}/stages/tex/*/{n}.png'))[0]).convert('RGBA')
def faded(img, a):
    a = max(0.0, min(1.0, a))
    if a >= 0.999: return img
    o = img.copy(); o.putalpha(o.getchannel('A').point(lambda q: int(q * a))); return o
def scaled(img, sx, sy=None):
    sy = sx if sy is None else sy
    return img.resize((max(1, int(img.width * sx)), max(1, int(img.height * sy))), Image.BILINEAR)

# --- sky: deeper at the top, the sun at the right ---------------------------------
yy = np.linspace(0, 1, H)[:, None, None]
sky = np.array([18, 44, 112]) * (1 - yy) ** 1.3 + np.array([120, 168, 220]) * (1 - (1 - yy) ** 1.3)
SKY = Image.fromarray(np.repeat(sky, W + 400, 1).astype(np.uint8)).convert('RGB')
sun = tex('a01m03_sun01').convert('RGB').resize((1000, 1000), Image.BICUBIC)
c = Image.new('RGB', (W + 400, H)); c.paste(sun, (int(W * 0.88) - 500, int(H * 0.04) - 500))
SKY = ImageChops.screen(SKY, c).convert('RGBA')
def cloud_band(width, y, height, seed, alpha, tint):
    lay = Image.new('L', (width, H)); d = ImageDraw.Draw(lay); r = random.Random(seed)
    for _ in range(int(width / 25)):
        x = r.uniform(-100, width + 100); rad = r.uniform(height * 0.4, height)
        d.ellipse((x - rad * 1.6, y - rad * 0.7 + r.uniform(-height * 0.3, height * 0.3), x + rad * 1.6, y + rad * 0.9 + 400), fill=255)
    lay = lay.filter(ImageFilter.GaussianBlur(height * 0.18)).point(lambda v: int(v * alpha))
    out = Image.new('RGBA', (width, H), tint + (0,)); out.putalpha(lay); return out
FAR_CLOUDS = cloud_band(W * 3, 780, 90, 1, 0.6, (150, 178, 215))          # blue-grey: a step below the figures
NEAR_CLOUDS = cloud_band(W * 4, 1120, 110, 3, 1.0, (196, 210, 232))

# --- islands: the temple, shaded a step darker and cooler -----------------------------
ISL = Image.open(S + '/poster/island.png').convert('RGBA').crop((562, 323, 1560, 1062))
a = np.asarray(ISL).astype(np.float32).copy(); r_ = np.clip((ISL.width - np.arange(ISL.width)) / 120, 0, 1); a[..., 3] *= r_[None, :]
a[..., :3] = a[..., :3] * 0.78 + np.array([30, 45, 80]) * 0.22                 # cooler, darker marble
ISL = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5))
def tinted(img, col, amount):
    b = np.asarray(img, np.float32).copy(); b[..., :3] = b[..., :3] * (1 - amount) + np.array(col) * amount
    return Image.fromarray(b.astype(np.uint8))
def warm_light(img):
    """The selected island: a gold light from above (its banner's beam)."""
    b = np.asarray(img, np.float32).copy(); h = b.shape[0]
    k = np.clip(1 - np.linspace(0, 1, h) * 1.4, 0, 1)[:, None, None] * 0.35
    b[..., :3] = np.clip(b[..., :3] * (1 + k * 0.5) + np.array(GOLD) * k * 0.35, 0, 255); return Image.fromarray(b.astype(np.uint8))
# mode, world x, y, depth, width, flip, haze colour, haze, rise order
ISLANDS = [(0, -2600, 40, 0.55, 300, False, (150, 175, 215), 0.55, 0),
           (3, 1500, 60, 0.6, 330, True, (150, 175, 215), 0.5, 1),
           (1, -1300, 190, 1.0, 700, True, (120, 140, 190), 0.18, 2),
           (2, 0, 210, 1.0, 800, False, (255, 255, 255), 0.0, 3)]
ISL_IMG = {i[0]: tinted(ISL.transpose(Image.FLIP_LEFT_RIGHT) if i[5] else ISL, i[6], i[7]) for i in ISLANDS}
ISL_LIT = {k: warm_light(v) for k, v in ISL_IMG.items() if k in (1, 2)}
NATIVE = [192, 183, 118, 173]
FLASH = fx_tex('doll_008_doll', 'ptc_cmn_flashA')
DOT = additive_sprite(FLASH, (255, 226, 150), (34, 34)); DOT_S = additive_sprite(FLASH, (255, 226, 150), (22, 22))

def heading(i, h=130):
    y0, y1 = MODES[i]['head']
    hd = HEADS.crop((0, int(y0 * HEADS.height), HEADS.width, int(y1 * HEADS.height)))
    hd = fit(hd.crop(hd.getchannel('A').point(lambda a: 255 if a > 200 else 0).getbbox()), h=h)
    lay = Image.new('RGBA', (max(hd.width, 420) + 40, hd.height + 140)); lay.alpha_composite(hd, (0, 0))
    fl = flourish_v4(int(400 * h / 130)); lay.alpha_composite(fl, (max(0, int(hd.width / 2 - fl.width / 2)), hd.height - int(30 * h / 130)))
    return lay
HEAD = {1: heading(1), 2: heading(2)}
def caption(i):
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle((40, 985, 820, 1045), radius=30, fill=INK + (215,))
    spaced_text(d, (430, 1015), MODES[i]['cap'], ImageFont.truetype(GAME_FONT, 32), (250, 244, 232, 255), 3)
    return lay
CAP = {1: caption(1), 2: caption(2)}
CTRL = Image.new('RGBA', (W, H)); ImageDraw.Draw(CTRL).rounded_rectangle((1320, 1006, W - 40, 1066), radius=30, fill=INK + (215,)); CTRL.alpha_composite(controls_v4())
CARD = Image.new('RGBA', (W, H), (240, 232, 214, 255))
CARD = G.add(CARD, G.backlight_rays((W, H), W / 2, H / 2, GOLD, n=24, length=1400, strength=0.4))
CHEAD = heading(2, h=300); CHEAD = CHEAD.crop(CHEAD.getbbox())

def camera(v):
    """Camera x, y, zoom. Hold at Together, lean left (anticipation), glide to
    Vault, settle on a spring, pull back before the dive, dive."""
    lean = A.track(v, [(116, 0), (124, -60, 'in_out')])
    glide = A.track(v, [(124, 0), (178, 1, 'in_out')])
    settle = A.track(v, [(178, 0), (200, 1, 'spring')]) - A.track(v, [(178, 0), (200, 1)])
    x = -1300 + 1300 * glide + lean * (1 - glide) + 40 * settle + 30 * math.sin(v / 80)
    y = 14 * math.sin(v / 90)
    z = A.track(v, [(0, 1.0), (256, 1.0), (264, 0.95, 'out'), (284, 5.0, 'in')]) * (1 + 0.015 * math.sin(v / 60))
    if v >= 264: y -= 60 * A.track(v, [(264, 0), (284, 1, 'in')])
    return x, y, z
def at(x, y, d, cam):
    cx, cy, z = cam; return W / 2 + (x - cx) * d * z, H * 0.52 + (y - cy) * d * z

def frame(v):
    cam = camera(v); cx, cy, z = cam
    page = SKY.crop((int(200 + cx * 0.05), 0, int(200 + cx * 0.05) + W, H)).copy()
    o = int((cx * 0.3) % W); page.alpha_composite(FAR_CLOUDS.crop((o, 0, o + W, H)))
    sel = 1 if v < HOVER else 2
    pos = {}
    for mode, x, y, d, w, flip, col, hz, order in ISLANDS:
        t = A.stagger(v, 0, order, 4)
        rise = A.track(t, [(0, 500), (24, 0, 'out_back')]); ra = A.track(t, [(0, 0), (8, 1)])
        sx, sy = at(x, y, d, cam); sc = z ** (0.4 if d < 1 else 1.0)
        lit = mode == sel and mode in ISL_LIT
        im = ISL_LIT[mode] if lit else ISL_IMG[mode]
        ww = w * sc; im = scaled(im, ww / im.width)
        sy += rise + 6 * math.sin(v / 50 + order)                                  # islands bob a little
        if mode in (1, 2): page.alpha_composite(faded(soft_glow(im, (255, 236, 190) if lit else (200, 215, 240), 0.35 if lit else 0.15, 26), ra), (int(sx - im.width / 2), int(sy - im.height / 2)))
        page.alpha_composite(faded(im, ra), (int(sx - im.width / 2), int(sy - im.height / 2)))
        pos[mode] = (sx, sy - im.height * 0.55, ww)
    # the light trail, travelling along the path
    ta = A.track(v, [(30, 0), (50, 1)]) * (1 - A.track(v, [(256, 0), (266, 1)]))
    if ta > 0:
        trail = Image.new('RGBA', (W, H)); order_ = [pos[0], pos[1], pos[2], pos[3]]
        for (ax, ay, _), (bx, by, _) in zip(order_, order_[1:]):
            for k in range(14):
                t = (k + (v * 0.06) % 1) / 14; x = ax + (bx - ax) * t; y = ay + (by - ay) * t - math.sin(t * math.pi) * 80
                s_ = DOT if k % 2 else DOT_S; trail.alpha_composite(faded(s_, ta), (int(x - s_.width / 2), int(y - s_.height / 2)))
        page = G.add(page, trail)
    # banners: pop in, the selected one big on a gold beam
    for mode in (0, 3, 1, 2):
        bx, by, ww = pos[mode]; i = [0, 3, 1, 2].index(mode)
        t = A.stagger(v, 24, i, 3); pop = A.track(t, [(0, 0), (12, 1, 'out_back')])
        if pop <= 0: continue
        if mode == 1: on = A.track(v, [(40, 0), (52, 1, 'spring'), (HOVER, 1), (HOVER + 9, 0, 'in')])
        elif mode == 2: on = A.track(v, [(HOVER, 0), (HOVER + 15, 1, 'spring')])
        else: on = 0
        leave = A.track(v, [(CLICK + 4, 0), (CLICK + 12, 1, 'in')])
        size = NATIVE[mode] * (1.5 + 1.2 * on) * (z ** 0.5 if mode in (1, 2) else 1) * pop
        b = fit(BTN[mode], w=max(4, size))
        if mode == 2:
            sqx, sqy = A.squash(v, CLICK); b = scaled(b, sqx, sqy)
            if CLICK <= v < CLICK + 4: b = Image.composite(Image.new('RGBA', b.size, (255, 255, 255, 255)), b, b.getchannel('A'))
        b = glint(b, v / 60) if on > 0.6 else step_back(b, max(0, 1 - on))
        if on > 0.05:
            beam = Image.new('L', (W, H)); bw = 64 * on
            ImageDraw.Draw(beam).polygon([(bx - bw, by - 60), (bx + bw, by - 60), (bx + bw * 0.4, by + 230), (bx - bw * 0.4, by + 230)], fill=int(120 * on))
            bl = Image.new('RGBA', (W, H), GOLD + (0,)); bl.putalpha(beam.filter(ImageFilter.GaussianBlur(40))); page = G.add(page, faded(bl, 1 - leave))
        put(page, faded(b, 1 - leave), bx, by - 70 - 40 * on + 6 * math.sin(v / 25 + mode), anchor='c', sh=(8, 0.4, 6, 10),
            gl=(13, 14, GOLD, on) if on > 0.05 else None)
    if CLICK <= v < CLICK + 18:
        t = (v - CLICK) / 18; r = 60 + 300 * A.out(t); bx, by, _ = pos[2]
        ring = Image.new('RGBA', (W, H)); ImageDraw.Draw(ring).ellipse((bx - r, by - 110 - r * 0.6, bx + r, by - 110 + r * 0.6), outline=GOLD + (int(255 * (1 - t)),), width=int(10 * (1 - t)) + 2)
        page = G.add(page, ring.filter(ImageFilter.GaussianBlur(3))); page.alpha_composite(ring)
    # Palutena: a dip into the clouds, then she rises (overshoot); she stands against the sky
    if v >= 182:
        pal = Image.open(f'{R}/vault/{min(v - 182, 149):04d}.png').convert('RGBA'); pal = fit(pal.crop(pal.getbbox()), h=620 * z ** 0.6)
        px, py = at(560, 430, 1.15, cam)
        rise = A.track(v, [(182, 420), (190, 450, 'in'), (214, 0, 'out_back')])
        px, py = px - pal.width / 2, py - pal.height + 60 + rise
        page.alpha_composite(soft_glow(pal, (255, 244, 220), 0.55, 24), (int(px), int(py))); page.alpha_composite(pal, (int(px), int(py)))
    o = int((cx * 1.5 * z + v * 0.6) % W); page.alpha_composite(NEAR_CLOUDS.crop((o, 0, o + W, H)))
    # the dive: speed lines toward the island, blur grows
    if v >= 262:
        k = A.track(v, [(264, 0), (284, 1, 'in')])
        if k > 0:
            page = page.filter(ImageFilter.GaussianBlur(6 * k))
            sl = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(sl); rnd = random.Random(v // 2); cx0, cy0 = pos[2][0], pos[2][1] + 180
            for _ in range(60):
                an = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(200, 500) * (1 - k * 0.5); r1 = r0 + rnd.uniform(400, 1400); w_ = rnd.uniform(0.004, 0.01)
                d.polygon([(cx0 + math.cos(an) * r0, cy0 + math.sin(an) * r0), (cx0 + math.cos(an - w_) * r1, cy0 + math.sin(an - w_) * r1), (cx0 + math.cos(an + w_) * r1, cy0 + math.sin(an + w_) * r1)], fill=(255, 255, 255, int(200 * k)))
            page.alpha_composite(sl)
    page = G.bloom(page, threshold=0.84, strength=0.28)
    page = G.grade(page, vignette=0.2)
    # the menu: heading and caption, entering, swapping on hover, leaving after the click
    leave = [A.track(A.stagger(v, CLICK + 4, i, 3), [(0, 0), (9, 1, 'in')]) for i in range(3)]
    for i in (1, 2):
        if i == 1: k_in = A.track(v, [(30, 0), (45, 1, 'out_back')]); k_out = A.track(v, [(HOVER, 0), (HOVER + 9, 1, 'in')])
        else: k_in = A.track(v, [(HOVER + 3, 0), (HOVER + 18, 1, 'out_back')]); k_out = leave[0]
        a_ = min(1, k_in) * (1 - k_out)
        if a_ <= 0.01: continue
        y_ = -90 * (1 - k_in) - 120 * k_out
        page.alpha_composite(faded(HEAD[i], a_), (70, int(50 + y_)))
        cy_ = 120 * (1 - A.track(v, [(33 if i == 1 else HOVER + 6, 0), (48 if i == 1 else HOVER + 18, 1, 'out')])) + 160 * (k_out if i == 1 and v < CLICK else leave[1])
        page.alpha_composite(faded(CAP[i], a_), (0, int(cy_)))
    cy_ = 120 * (1 - A.track(v, [(36, 0), (52, 1, 'out')])) + 160 * leave[2]
    page.alpha_composite(CTRL, (0, int(cy_)))
    # the pointer: arcs in toward Vault's banner, rides it during the glide, clicks
    if 70 <= v < CLICK + 8:
        t = A.in_out(A.clamp01((v - 70) / 42)); p0 = (W * 0.9, H * 0.9); p2 = (pos[2][0] + 40, pos[2][1] - 110); p1 = ((p0[0] + p2[0]) / 2, H * 0.35)
        px = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]; py = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        s = 1.3 * (0.88 if CLICK <= v < CLICK + 5 else 1.0); pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
        ImageDraw.Draw(page).polygon([(px + x * s, py + y * s) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    # white, then the Vault screen; its heading lands
    if v >= 280:
        wa = A.track(v, [(280, 0), (284, 1)]) * (1 - A.track(v, [(286, 0), (294, 1)]))
        base = CARD.copy()
        if v >= 286:
            s_ = A.track(v, [(286, 0.55), (300, 1.0, 'out_back')]); hh = scaled(CHEAD, s_)
            base.alpha_composite(faded(hh, A.track(v, [(286, 0), (290, 1)])), (int(W / 2 - hh.width / 2), int(H / 2 - hh.height / 2)))
            page = base
        page.alpha_composite(Image.new('RGBA', (W, H), (255, 252, 244, int(255 * wa))))
    return page

if __name__ == '__main__':
    out = 'd2v2_frames'; os.makedirs(out, exist_ok=True)
    frames = [STILL] if STILL >= 0 else range(int(os.environ.get('FROM', '0')), N)
    for v in frames:
        p = frame(v)
        if STILL >= 0: p.convert('RGB').save(f'check/d2v2_{v:04d}.png')
        else: p.convert('RGB').save(f'{out}/{v:04d}.png')
    print('d2 v2', len(frames))
