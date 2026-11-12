# Direction 1 in motion, "action poster" (Together). 60 fps, 252 frames:
#   0-30     the slanted stage panel slams in from the right (with overshoot),
#            the heading drops in, the buttons slide in one after another
#   30-150   idle: the grapple in slow motion, speed lines flicker, feathers drift
#   150      click: the button squashes, the menu flies off, the throw plays
#   190-201  the kick lands: hit-stop (the pose holds 12 frames), flash,
#            impact burst, screen shake
#   216-250  a slash splits the screen; the halves part onto the next screen
#   python3 d1_motion.py  ->  d1_frames/NNNN.png     STILL=N: one frame to check/
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G
from PIL import ImageEnhance, ImageChops
FPS = 60; N = 252; CLICK = 150; HIT = 190; HOLD = 12; WIPE = 216
m = MODES[1]; ORANGE = (232, 140, 70); GOLD = (250, 205, 110); INK = (14, 8, 20)
STILL = int(os.environ.get('STILL', '-1'))
def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)
def back(t, s=1.7):
    t = max(0, min(1, t)); t -= 1; return t * t * ((s + 1) * t + s) + 1
def slant(x0, x1, y0, y1, lean): return [(x0, y0), (x1, y0), (x1 - lean, y1), (x0 - lean, y1)]
def faded(img, a):
    if a >= 0.999: return img
    o = img.copy(); o.putalpha(o.getchannel('A').point(lambda q: int(q * max(0, a)))); return o

# --- static layers -------------------------------------------------------------
yy, xx = np.mgrid[0:H, 0:W]; k = (xx / W * 0.6 + yy / H * 0.4)[..., None]
BASE = Image.fromarray((np.array([30, 14, 52]) * (1 - k) + np.array([74, 30, 96]) * k).astype(np.uint8)).convert('RGBA')
dots = Image.new('L', (W, H)); d = ImageDraw.Draw(dots)
for y in range(0, H, 22):
    for x in range(0, W, 22):
        r = 7 * max(0, 1 - x / (W * 0.55))
        if r > 0.6: d.ellipse((x - r, y - r, x + r, y + r), fill=60)
lay = Image.new('RGBA', (W, H), (150, 90, 210, 0)); lay.putalpha(dots); BASE.alpha_composite(lay)
PANEL = slant(860, W + 300, -20, H + 20, 330)
MASK = Image.new('L', (W + 1000, H)); ImageDraw.Draw(MASK).polygon(PANEL, fill=255)
st = Image.open('bg/together.png').convert('RGB').resize((W + 80, H + 45), Image.LANCZOS)
st = ImageEnhance.Brightness(ImageEnhance.Color(st).enhance(1.25)).enhance(1.15)
STAGE = Image.blend(st, Image.new('RGB', st.size, ORANGE), 0.25).convert('RGBA')
def panel_layer(dx, v):
    """The stage panel, slid right by dx: the stage drifting slowly inside, a black and gold edge."""
    lay = Image.new('RGBA', (W, H))
    o = int(40 + 30 * math.sin(v / 90)); lay.paste(STAGE.crop((o, 20, o + W, 20 + H)), (0, 0))
    mk = Image.new('L', (W, H)); ImageDraw.Draw(mk).polygon([(x + dx, y) for x, y in PANEL], fill=255)
    out = Image.new('RGBA', (W, H)); out.paste(lay, (0, 0), mk)
    d = ImageDraw.Draw(out)
    d.line([(PANEL[0][0] + dx, PANEL[0][1]), (PANEL[3][0] + dx, PANEL[3][1])], fill=INK + (255,), width=26)
    d.line([(PANEL[0][0] + dx + 14, PANEL[0][1]), (PANEL[3][0] + dx + 14, PANEL[3][1])], fill=GOLD + (255,), width=7)
    return out, mk
def speed_lines(seed, strength, mk):
    sl = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(sl); rnd = random.Random(seed)
    for _ in range(90):
        a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(260, 420); r1 = r0 + rnd.uniform(500, 1400); w = rnd.uniform(0.004, 0.012)
        d.polygon([(IMPACT[0] + math.cos(a) * r0, IMPACT[1] + math.sin(a) * r0),
                   (IMPACT[0] + math.cos(a - w) * r1, IMPACT[1] + math.sin(a - w) * r1),
                   (IMPACT[0] + math.cos(a + w) * r1, IMPACT[1] + math.sin(a + w) * r1)], fill=(255, 250, 235, int(rnd.uniform(90, 200) * strength)))
    sl.putalpha(ImageChops.multiply(sl.getchannel('A'), mk.filter(ImageFilter.GaussianBlur(30)))); return sl

# the characters: one fixed placement for the whole move
CH = f'{R}/poster_tog'
b100 = Image.open(f'{CH}/0100.png').getbbox(); b190 = Image.open(f'{CH}/0190.png').getbbox()
CK = 1060 / (b100[3] - b100[1])                                     # the grapple about 1060 px tall
CX0, CY0 = 1400 - (b100[0] + b100[2]) / 2 * CK, H + 70 - b100[3] * CK  # centred on the right, feet just below the edge
IMPACT = (int(CX0 + (b190[0] + b190[2]) / 2 * CK), int(CY0 + (b190[1] + 0.45 * (b190[3] - b190[1])) * CK))
RAYS = G.backlight_rays((W, H), *IMPACT, (255, 220, 160), n=26, length=1600, strength=0.6)
def char_frame(v):
    if v < HIT: return v
    if v < HIT + HOLD: return HIT
    return min(215, v - HOLD + 1)

# the heading, the buttons, the ribbons
y0_, y1_ = m['head']
hd = HEADS.crop((0, int(y0_ * HEADS.height), HEADS.width, int(y1_ * HEADS.height)))
hd = hd.crop(hd.getchannel('A').point(lambda a: 255 if a > 200 else 0).getbbox())
HEAD = fit(hd, h=150).rotate(6, expand=True, resample=Image.BICUBIC)
HSH = Image.new('RGBA', HEAD.size, ORANGE + (0,)); HSH.putalpha(HEAD.getchannel('A'))
FL = flourish_v4(470).rotate(6, expand=True, resample=Image.BICUBIC)
NATIVE = [192, 183, 118, 173]; BPOS = [(270, 420), (330, 580), (240, 745), (250, 860)]
BIMG = [fit(p, w=NATIVE[i] * (2.8 if i == 1 else 1.5)) for i, p in enumerate(BTN)]
BIMG = [b if i == 1 else step_back(b, 1.0) for i, b in enumerate(BIMG)]
RIB = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(RIB)
d.polygon(slant(-40, 1010, 975, 1045, 18), fill=INK + (235,)); d.line([(0, 973), (1010, 973)], fill=GOLD + (255,), width=4)
spaced_text(d, (500, 1010), m['cap'], ImageFont.truetype(GAME_FONT, 34), (250, 244, 232, 255), 3)
d.polygon(slant(1330, W + 40, 1005, 1065, 18), fill=INK + (235,)); RIB.alpha_composite(controls_v4(), (0, -2))
FLASH = fx_tex('doll_008_doll', 'ptc_cmn_flashA'); HANE = fx_tex('demo_024_demo', 'ptc_c05_040_hane')
# the next screen: violet, rays, the heading big
CARD = BASE.copy(); CARD = G.add(CARD, G.backlight_rays((W, H), W / 2, H / 2, (255, 200, 140), n=24, length=1500, strength=0.5))
_h = fit(hd, h=300).rotate(6, expand=True, resample=Image.BICUBIC); _s = Image.new('RGBA', _h.size, ORANGE + (0,)); _s.putalpha(_h.getchannel('A'))
CARD.alpha_composite(_s, (int(W / 2 - _h.width / 2) + 20, int(H / 2 - _h.height / 2) + 20)); CARD.alpha_composite(_h, (int(W / 2 - _h.width / 2), int(H / 2 - _h.height / 2)))

def frame(v):
    page = BASE.copy()
    dx = 900 * (1 - back(v / 24))                                      # the panel slams in
    pl, mk = panel_layer(dx, v); page.alpha_composite(pl)
    page = G.add(page, faded(RAYS, ease(v / 20)))
    # speed lines: a burst on entry, a flicker while idle, full at the hit
    hit = HIT <= v < HIT + HOLD
    s_ = 1.0 if v < 14 else (1.0 if hit else (0.45 if v < CLICK else 0.75))
    page.alpha_composite(speed_lines(v // 3 if not hit else v, s_, mk))
    # the characters ride in with the panel
    ch = Image.open(f'{CH}/{char_frame(v):04d}.png').convert('RGBA'); ch = ch.resize((int(ch.width * CK), int(ch.height * CK)), Image.BILINEAR)
    page.alpha_composite(soft_glow(ch, (255, 235, 200), 0.5, 24), (int(CX0 + dx), int(CY0))); page.alpha_composite(ch, (int(CX0 + dx), int(CY0)))
    particles(page, 'together', v / FPS, IMPACT[0], IMPACT[1])
    # the hit: impact light, feathers thrown out
    if v >= HIT:
        t = v - HIT; lay = Image.new('RGBA', (W, H))
        if t < 26:
            sz = int(300 + 900 * ease(t / 8)); fa = 1 - ease((t - 6) / 20)
            lay.alpha_composite(faded(additive_sprite(FLASH, (255, 210, 150), (sz, sz)), fa), (IMPACT[0] - sz // 2, IMPACT[1] - sz // 2))
            page = G.add(page, lay)
        if t < 50:
            fl = Image.new('RGBA', (W, H)); rnd = random.Random(8)
            for n in range(28):
                a = rnd.uniform(0, 2 * math.pi); dd = 120 + rnd.uniform(14, 30) * t
                col = (255, 255, 255) if n % 3 else (120, 90, 170)
                sp = faded(additive_sprite(HANE, col, (90, 45)).rotate(math.degrees(-a) + t * 7, expand=True), 1 - ease((t - 30) / 20))
                fl.alpha_composite(sp, (int(IMPACT[0] + math.cos(a) * dd - sp.width / 2), int(IMPACT[1] + math.sin(a) * dd + 0.2 * t * t - sp.height / 2)))
            page.alpha_composite(fl)
    page = G.bloom(page, threshold=0.8, strength=0.35)
    page = G.grade(page, vignette=0.22)
    # the menu: heading drops in, buttons slide in; after the click they fly off
    lv = ease((v - CLICK - 4) / 14) if v >= CLICK else 0
    hy = -320 * (1 - back((v - 6) / 20)) - 200 * lv
    page.alpha_composite(faded(HSH, 1 - lv), (72, int(82 + hy))); page.alpha_composite(faded(HEAD, 1 - lv), (60, int(70 + hy)))
    page.alpha_composite(faded(FL, ease((v - 16) / 10) * (1 - lv)), (110, int(70 + HEAD.height - 40 + hy)))
    for i, (b, (cx_, by)) in enumerate(zip(BIMG, BPOS)):
        bx = -560 * (1 - back((v - 10 - 4 * i) / 18)) - 900 * lv
        on = i == 1
        if on:
            sq = 0.92 if CLICK <= v < CLICK + 6 else 1.0 + 0.03 * math.sin(v / 8)
            b = glint(b, v / FPS); b = b.resize((int(b.width * sq), int(b.height * sq)), Image.BILINEAR)
        put(page, b, cx_ + bx, by, anchor='c', sh=(10, 0.6, 10, 14), gl=(13, 14, (255, 208, 84), 0.8 + 0.2 * math.sin(v / 6)) if on else None, rot=-6)
    page.alpha_composite(RIB, (0, int(140 * (1 - ease((v - 14) / 14)) + 200 * lv)))
    # the pointer: comes in, sits on Together, clicks
    if v < CLICK + 8:
        kk = ease((v - 40) / 80); px_, py_ = W * 0.9 + (420 - W * 0.9) * kk, H * 0.85 + (600 - H * 0.85) * kk
        s = 1.3 * (0.9 if v >= CLICK else 1.0); pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
        ImageDraw.Draw(page).polygon([(px_ + x * s, py_ + y * s) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    # hit-stop: a flash and a shake
    if hit or HIT + HOLD <= v < HIT + HOLD + 10:
        t = v - HIT; rnd = random.Random(v); amp = 16 * (1 - t / (HOLD + 10))
        page = ImageChops.offset(page, int(rnd.uniform(-amp, amp)), int(rnd.uniform(-amp, amp)))
        if t < 8: page.alpha_composite(Image.new('RGBA', (W, H), (255, 240, 215, int(150 * (1 - t / 8)))))
    # the slash, then the halves part onto the next screen
    w = v - WIPE
    if w >= 0:
        a = math.radians(-58); ddx, ddy = math.cos(a), math.sin(a); nx, ny = -ddy, ddx
        msk = Image.new('L', (W, H)); ImageDraw.Draw(msk).polygon([(W/2-ddx*3000-ddy*3000, H/2-ddy*3000+ddx*3000), (W/2+ddx*3000-ddy*3000, H/2+ddy*3000+ddx*3000), (W/2+ddx*3000, H/2+ddy*3000), (W/2-ddx*3000, H/2-ddy*3000)], fill=255)
        gap = 1100 * ease(w / 20)
        A = Image.new('RGBA', (W, H)); A.paste(page, (0, 0), msk); B = Image.new('RGBA', (W, H)); B.paste(page, (0, 0), ImageChops.invert(msk))
        base = CARD.copy()
        base.alpha_composite(A.transform((W, H), Image.AFFINE, (1, 0, nx * gap, 0, 1, ny * gap)))
        base.alpha_composite(B.transform((W, H), Image.AFFINE, (1, 0, -nx * gap, 0, 1, -ny * gap)))
        if w < 12:
            ln = Image.new('RGBA', (W, H)); L = 2600 * ease(w / 5)
            ImageDraw.Draw(ln).line((W/2-ddx*L, H/2-ddy*L, W/2+ddx*L, H/2+ddy*L), fill=(255, 236, 170, int(255 * (1 - w / 12))), width=int(18 * (1 - w / 12)) + 2)
            base = G.add(base, ln.filter(ImageFilter.GaussianBlur(5))); base.alpha_composite(ln)
        page = base
    return page

if __name__ == '__main__':
    out = 'd1_frames'; os.makedirs(out, exist_ok=True)
    frames = [STILL] if STILL >= 0 else range(N)
    for v in frames:
        p = frame(v)
        if STILL >= 0: p.convert('RGB').save(f'check/d1m_{v:04d}.png')
        else: p.convert('RGB').save(f'{out}/{v:04d}.png')
    print('d1 motion', len(frames))
