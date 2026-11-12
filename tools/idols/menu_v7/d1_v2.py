# Action poster v2 (Together), rebuilt with the motion notes
# (claude/MOTION_DESIGN_NOTES.md) and the keyframe toolkit (anim.py).
#
# Colour plan (60-30-10): deep violet / warm orange (Pit's light) / gold only
# for the selection. Values: the stage behind the fighters is darkened and
# pushed toward violet so the fighters are the brightest, most contrasted thing.
#
# Timing chart (frames, 60 fps), 270 frames:
#   0-8      the violet field wipes in from the left edge
#   4-10     anticipation: the stage panel pulls back right
#   10-22    the panel slams in (overshoot), the fighters ride it 3 frames late
#   22-30    landing: small horizontal kick of the camera, a burst of speed lines
#   26-40    the heading pops in (shadow 3 frames later, flourish draws in after)
#   30-48    the buttons arrive one after another (3 frames apart)
#   48-60    Together takes the selection: grows on a spring, gold glow rises
#   44-62    caption ribbon, then the controls
#   60-170   moving hold: slow camera push, the grapple, speed lines on twos,
#            feathers, a glint on the selected button; the pointer arcs in
#   170      click: the button flashes and squashes, a gold ring bursts
#   174-186  the menu leaves (ease-in, staggered, 75% of its entrance)
#   174-214  the throw; the camera eases back just before contact
#   214-215  impact frames: black silhouettes on a white-gold burst
#   214-224  hit-stop: the pose holds, the fighters shake hard (decaying), the
#            stage shakes less; flash, burst, feathers thrown out
#   224-248  the kick finishes, a camera punch-in settles; feathers keep falling
#   240-246  a gold line cuts across; 246-262 the halves part (ease-in)
#   254-270  the next screen's heading lands (overshoot)
#   python3 d1_v2.py  ->  d1v2_frames/NNNN.png     STILL=N for one frame in check/
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G, anim as A
from PIL import ImageEnhance, ImageChops
N = 270; CLICK = 170; HIT = 214; HOLD = 10; CUT = 240
VIOLET = (40, 18, 66); VIOLET2 = (88, 40, 120); ORANGE = (240, 150, 70); GOLD = (255, 208, 84); INK = (12, 6, 18)
STILL = int(os.environ.get('STILL', '-1'))

def faded(img, a):
    a = max(0.0, min(1.0, a))
    if a >= 0.999: return img
    o = img.copy(); o.putalpha(o.getchannel('A').point(lambda q: int(q * a))); return o
def scaled(img, sx, sy=None):
    sy = sx if sy is None else sy
    return img.resize((max(1, int(img.width * sx)), max(1, int(img.height * sy))), Image.BILINEAR)
def slant(x0, x1, y0, y1, lean): return [(x0, y0), (x1, y0), (x1 - lean, y1), (x0 - lean, y1)]

# --- the field (60%: violet), quiet halftone -----------------------------------------
yy, xx = np.mgrid[0:H, 0:W]; k = (xx / W * 0.6 + yy / H * 0.4)[..., None]
FIELD = Image.fromarray((np.array(VIOLET) * (1 - k) + np.array(VIOLET2) * k).astype(np.uint8)).convert('RGBA')
dots = Image.new('L', (W, H)); d = ImageDraw.Draw(dots)
for y in range(0, H, 20):
    for x in range(0, W, 20):
        r = 6 * max(0, 1 - x / (W * 0.5))
        if r > 0.6: d.ellipse((x - r, y - r, x + r, y + r), fill=34)
lay = Image.new('RGBA', (W, H), (170, 120, 230, 0)); lay.putalpha(dots); FIELD.alpha_composite(lay)

# --- the stage panel: darkened, pushed toward violet, a warm rim near the fighters ---
PANEL = slant(860, W + 300, -40, H + 40, 330)
st = Image.open('bg/together.png').convert('RGB').resize((W + 120, H + 70), Image.LANCZOS)
st = ImageEnhance.Color(st).enhance(0.45)
a = np.asarray(st, np.float32) / 255
a = a * 0.42 + np.array(VIOLET2) / 255 * 0.25                       # narrow, dark value range
STAGE = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
CH = f'{R}/poster_tog'
b100 = Image.open(f'{CH}/0100.png').getbbox(); b190 = Image.open(f'{CH}/0190.png').getbbox()
CK = 1060 / (b100[3] - b100[1])
CX0, CY0 = 1400 - (b100[0] + b100[2]) / 2 * CK, H + 70 - b100[3] * CK
IMPACT = (int(CX0 + (b190[0] + b190[2]) / 2 * CK), int(CY0 + (b190[1] + 0.45 * (b190[3] - b190[1])) * CK))
RAYS = G.backlight_rays((W, H), *IMPACT, ORANGE, n=24, length=1500, strength=0.55)

def speed_lines(seed, strength, col=(235, 220, 255)):
    sl = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(sl); rnd = random.Random(seed)
    for _ in range(70):
        a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(300, 460); r1 = r0 + rnd.uniform(500, 1400); w = rnd.uniform(0.003, 0.010)
        d.polygon([(IMPACT[0] + math.cos(a) * r0, IMPACT[1] + math.sin(a) * r0),
                   (IMPACT[0] + math.cos(a - w) * r1, IMPACT[1] + math.sin(a - w) * r1),
                   (IMPACT[0] + math.cos(a + w) * r1, IMPACT[1] + math.sin(a + w) * r1)], fill=col + (int(rnd.uniform(70, 170) * strength),))
    return sl

# --- the menu pieces -----------------------------------------------------------------
m = MODES[1]
y0_, y1_ = m['head']
hd = HEADS.crop((0, int(y0_ * HEADS.height), HEADS.width, int(y1_ * HEADS.height)))
hd = hd.crop(hd.getchannel('A').point(lambda a: 255 if a > 200 else 0).getbbox())
HEAD = fit(hd, h=150).rotate(6, expand=True, resample=Image.BICUBIC)
HSH = Image.new('RGBA', HEAD.size, INK + (0,)); HSH.putalpha(HEAD.getchannel('A').point(lambda a: int(a * 0.85)))
FL = flourish_v4(470).rotate(6, expand=True, resample=Image.BICUBIC)
NATIVE = [192, 183, 118, 173]; BPOS = [(270, 420), (330, 580), (240, 745), (250, 860)]
BIG = [fit(p, w=NATIVE[i] * 2.7) for i, p in enumerate(BTN)]
SMALL = [step_back(fit(p, w=NATIVE[i] * 1.5), 1.0) for i, p in enumerate(BTN)]
RIB = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(RIB)
d.polygon(slant(-40, 1010, 975, 1045, 18), fill=INK + (235,)); d.line([(0, 973), (1010, 973)], fill=ORANGE + (255,), width=4)
spaced_text(d, (500, 1010), m['cap'], ImageFont.truetype(GAME_FONT, 34), (250, 244, 232, 255), 3)
CTRL = Image.new('RGBA', (W, H)); ImageDraw.Draw(CTRL).polygon(slant(1330, W + 40, 1005, 1065, 18), fill=INK + (235,)); CTRL.alpha_composite(controls_v4(), (0, -2))
FLASH = fx_tex('doll_008_doll', 'ptc_cmn_flashA'); HANE = fx_tex('demo_024_demo', 'ptc_c05_040_hane')
# the next screen
CARD = FIELD.copy(); CARD = G.add(CARD, G.backlight_rays((W, H), W / 2, H / 2, ORANGE, n=24, length=1500, strength=0.45))
CHEAD = fit(hd, h=300).rotate(6, expand=True, resample=Image.BICUBIC)
CSH = Image.new('RGBA', CHEAD.size, INK + (0,)); CSH.putalpha(CHEAD.getchannel('A'))

def char_index(v):
    """The fighters' frame: the grapple until the click, the throw, a hold on
    the hit, then the kick finishes."""
    if v < CLICK + 4: return min(149, int(v * 150 / (CLICK + 4)))
    c = 150 + (v - CLICK - 4)
    if c >= 190: c = 190 + max(0, v - HIT - HOLD)
    return min(215, c)

def frame(v):
    page = Image.new('RGBA', (W, H), (8, 4, 12, 255))
    # the field wipes in from the left edge
    fx = A.track(v, [(0, -W), (8, 0, 'out')]); page.alpha_composite(FIELD, (int(fx), 0))
    # camera: landing kick, slow push, ease back before the hit, punch after it
    cz = A.track(v, [(60, 1.0), (165, 1.035, 'in_out'), (208, 1.035), (214, 1.0, 'in_out'), (218, 1.07, 'out'), (240, 1.04, 'out')])
    kx, _ = A.shake(v, 22, 8, 7, 'x', seed=1)
    sx_hit, sy_hit = A.shake(v, HIT, HOLD + 10, 6, 'x', seed=2)                 # the stage shakes a little
    vx_hit, vy_hit = A.shake(v, HIT, HOLD + 10, 20, 'x', seed=3)                # the fighters shake hard
    # the panel: anticipation (pull back), slam (overshoot)
    pdx = A.track(v, [(0, 760), (4, 760), (10, 820, 'in'), (22, 0, 'out_back')])
    world = Image.new('RGBA', (W, H))
    o = int(60 + 40 * math.sin(v / 100)); world.paste(STAGE.crop((o, 30, o + W, 30 + H)), (0, 0))
    world = G.add(world, faded(RAYS, A.track(v, [(18, 0), (40, 1)])))
    if v >= 22:
        burst = 1.0 if v < 34 else (1.0 if HIT <= v < HIT + HOLD else 0.35 if v < CLICK else 0.6)
        world.alpha_composite(speed_lines((v // 2) if not HIT <= v < HIT + HOLD else 999, burst))
    mk = Image.new('L', (W, H)); ImageDraw.Draw(mk).polygon([(x + pdx, y) for x, y in PANEL], fill=255)
    panel = Image.new('RGBA', (W, H)); panel.paste(world, (int(sx_hit), int(sy_hit)), mk)
    d = ImageDraw.Draw(panel)
    d.line([(PANEL[0][0] + pdx, PANEL[0][1]), (PANEL[3][0] + pdx, PANEL[3][1])], fill=INK + (255,), width=26)
    d.line([(PANEL[0][0] + pdx + 14, PANEL[0][1]), (PANEL[3][0] + pdx + 14, PANEL[3][1])], fill=ORANGE + (255,), width=6)
    # the fighters ride the panel 3 frames late, overshooting a touch
    cdx = A.track(v, [(0, 760), (7, 760), (13, 820, 'in'), (25, 0, 'out_back')])
    ch = Image.open(f'{CH}/{char_index(v):04d}.png').convert('RGBA'); ch = scaled(ch, CK * cz)
    cx = CX0 + cdx + kx + vx_hit - (cz - 1) * (IMPACT[0] - CX0) ; cy = CY0 - (cz - 1) * (IMPACT[1] - CY0)
    impact_frame = HIT <= v < HIT + 2
    if impact_frame:
        # anime impact frames: a white-gold burst, the fighters as black silhouettes
        burst = Image.new('RGBA', (W, H), (255, 246, 222, 255)); burst = G.add(burst, G.backlight_rays((W, H), *IMPACT, GOLD, n=30, length=2200, strength=1.0))
        burst.alpha_composite(speed_lines(1000 + v, 1.0, (30, 14, 40)))
        sil = Image.new('RGBA', ch.size, INK + (0,)); sil.putalpha(ch.getchannel('A'))
        burst.alpha_composite(sil, (int(cx), int(cy))); page = burst
    else:
        page.alpha_composite(panel)
        page.alpha_composite(soft_glow(ch, (255, 226, 190), 0.55, 22), (int(cx), int(cy)))
        page.alpha_composite(ch, (int(cx), int(cy)))
        particles(page, 'together', v / 60, IMPACT[0], IMPACT[1])
        if v >= HIT + 2:
            t = v - HIT - 2; lay = Image.new('RGBA', (W, H))
            if t < 22:
                sz = int(400 + 1000 * A.out(min(1, t / 6))); fa = 1 - A.clamp01((t - 4) / 18)
                lay.alpha_composite(faded(additive_sprite(FLASH, (255, 220, 160), (sz, sz)), fa), (IMPACT[0] - sz // 2, IMPACT[1] - sz // 2))
                page = G.add(page, lay)
            if t < 70:
                fl = Image.new('RGBA', (W, H)); rnd = random.Random(8)
                for n in range(30):
                    an = rnd.uniform(0, 2 * math.pi); sp = rnd.uniform(10, 26)
                    dd = 100 + sp * 14 * A.out(min(1, t / 14)) + sp * max(0, t - 14) * 0.6        # burst, then drift
                    col = (255, 255, 255) if n % 3 else (150, 110, 200)
                    sp_ = faded(additive_sprite(HANE, col, (84, 42)).rotate(math.degrees(-an) + t * 6, expand=True), 1 - A.clamp01((t - 40) / 30))
                    fl.alpha_composite(sp_, (int(IMPACT[0] + math.cos(an) * dd - sp_.width / 2), int(IMPACT[1] + math.sin(an) * dd + 0.12 * t * t - sp_.height / 2)))
                page.alpha_composite(fl)
            if t < 8: page.alpha_composite(Image.new('RGBA', (W, H), (255, 244, 220, int(170 * (1 - t / 8)))))
    page = G.bloom(page, threshold=0.82, strength=0.32)
    page = G.grade(page, warm=(1.05, 1.0, 0.94), cool=(0.94, 0.94, 1.06), vignette=0.25)
    # --- the menu ---------------------------------------------------------------------
    out_k = [A.track(A.stagger(v, CLICK + 4, i, 3), [(0, 0), (12, 1, 'in')]) for i in range(6)]   # leaving, staggered
    # heading: pops in, the shadow 3 frames later, the flourish draws in
    hs = A.track(v, [(26, 0.6), (40, 1.0, 'out_back')]); ha = A.track(v, [(26, 0), (32, 1)]) * (1 - out_k[0])
    hy = -260 * out_k[0]
    if ha > 0:
        sh_s = A.track(v, [(29, 0.6), (43, 1.0, 'out_back')])
        hsh = scaled(HSH, sh_s); page.alpha_composite(faded(hsh, ha), (int(60 + 12 + HEAD.width * (1 - sh_s) / 2), int(70 + 12 + HEAD.height * (1 - sh_s) / 2 + hy)))
        hh = scaled(HEAD, hs); page.alpha_composite(faded(hh, ha), (int(60 + HEAD.width * (1 - hs) / 2), int(70 + HEAD.height * (1 - hs) / 2 + hy)))
        rev = A.track(v, [(38, 0), (52, 1)])
        if rev > 0:
            fl = FL.crop((0, 0, max(1, int(FL.width * rev)), FL.height)); page.alpha_composite(faded(fl, 1 - out_k[0]), (110, int(70 + HEAD.height - 40 + hy)))
    # buttons arrive one after another; Together takes the selection
    for i in range(4):
        t = A.stagger(v, 30, i, 3)
        if t < 0: continue
        bx = A.track(t, [(0, -180), (15, 0, 'out_back')]) - 900 * out_k[1 + min(i, 3)]
        ba = A.track(t, [(0, 0), (6, 1)])
        cx_, by = BPOS[i]
        if i == 1:
            sel = A.track(v, [(48, 0), (60, 1, 'spring')])
            b = BIG[1] if sel > 0.5 else SMALL[1]
            sc = (0.6 + 0.4 * sel) if sel <= 0.5 else (0.55 + 0.45 * sel)
            sqx, sqy = A.squash(v, CLICK)
            hov = 1 + 0.04 * (A.track(v, [(110, 0), (122, 1, 'spring')]) - A.track(v, [(110, 0), (122, 1)]))
            b = scaled(glint(b, v / 60) if sel > 0.5 else b, sc * sqx * hov, sc * sqy * hov)
            if CLICK <= v < CLICK + 4: b = Image.composite(Image.new('RGBA', b.size, (255, 255, 255, 255)), b, b.getchannel('A'))
            glow = (13, 14, GOLD, 0.9 * sel) if sel > 0.05 else None
            put(page, faded(b, ba), cx_ + bx, by, anchor='c', sh=(10, 0.6, 10, 14), gl=glow, rot=-6)
        else:
            put(page, faded(SMALL[i], ba), cx_ + bx, by, anchor='c', sh=(8, 0.5, 8, 12), rot=-6)
    # the click's gold ring
    if CLICK <= v < CLICK + 18:
        t = (v - CLICK) / 18; r = 60 + 340 * A.out(t)
        ring = Image.new('RGBA', (W, H)); ImageDraw.Draw(ring).ellipse((330 - r, 580 - r * 0.55, 330 + r, 580 + r * 0.55), outline=GOLD + (int(255 * (1 - t)),), width=int(10 * (1 - t)) + 2)
        page = G.add(page, ring.filter(ImageFilter.GaussianBlur(3))); page.alpha_composite(ring)
    ry = A.track(v, [(44, 140), (62, 0, 'out')]) + 220 * out_k[4]
    page.alpha_composite(RIB, (0, int(ry)))
    cy_ = A.track(v, [(50, 120), (66, 0, 'out')]) + 220 * out_k[5]
    page.alpha_composite(CTRL, (0, int(cy_)))
    # the pointer arcs in from bottom right and settles on Together
    if 70 <= v < CLICK + 8:
        t = A.in_out(A.clamp01((v - 70) / 40)); p0, p1, p2 = (W * 0.92, H * 0.95), (W * 0.55, H * 0.35), (430, 600)
        px = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]; py = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        s = 1.3 * (0.88 if CLICK <= v < CLICK + 5 else 1.0); pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
        ImageDraw.Draw(page).polygon([(px + x * s, py + y * s) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    # --- the cut: a gold line, then the halves part --------------------------------------
    if v >= CUT:
        ang = math.radians(-62); ux, uy = math.cos(ang), math.sin(ang); nx, ny = -uy, ux
        L = 3000; c0 = (W * 0.52, H * 0.5)
        msk = Image.new('L', (W, H)); ImageDraw.Draw(msk).polygon([(c0[0] - ux * L, c0[1] - uy * L), (c0[0] + ux * L, c0[1] + uy * L), (c0[0] + ux * L + nx * L, c0[1] + uy * L + ny * L), (c0[0] - ux * L + nx * L, c0[1] - uy * L + ny * L)], fill=255)
        gap = 1500 * A.track(v, [(246, 0), (262, 1, 'in')])
        base = CARD.copy()
        if v >= 254:
            s_ = A.track(v, [(254, 0.5), (268, 1.0, 'out_back')]); a_ = A.track(v, [(254, 0), (258, 1)])
            hh = scaled(CHEAD, s_); ss = scaled(CSH, s_)
            base.alpha_composite(faded(ss, a_), (int(W / 2 - hh.width / 2) + 16, int(H / 2 - hh.height / 2) + 16)); base.alpha_composite(faded(hh, a_), (int(W / 2 - hh.width / 2), int(H / 2 - hh.height / 2)))
        A1 = Image.new('RGBA', (W, H)); A1.paste(page, (0, 0), msk); B1 = Image.new('RGBA', (W, H)); B1.paste(page, (0, 0), ImageChops.invert(msk))
        base.alpha_composite(A1.transform((W, H), Image.AFFINE, (1, 0, -nx * gap, 0, 1, -ny * gap)))
        base.alpha_composite(B1.transform((W, H), Image.AFFINE, (1, 0, nx * gap, 0, 1, ny * gap)))
        lt = A.track(v, [(240, 0), (244, 1, 'out')]); la = 1 - A.track(v, [(253, 0), (261, 1), ])
        if la > 0:
            ln = Image.new('RGBA', (W, H)); Lh = 2600 * lt
            ImageDraw.Draw(ln).line((c0[0] - ux * Lh, c0[1] - uy * Lh, c0[0] + ux * Lh, c0[1] + uy * Lh), fill=GOLD + (int(255 * la),), width=int(14 * la) + 2)
            base = G.add(base, ln.filter(ImageFilter.GaussianBlur(6))); base.alpha_composite(ln)
        page = base
    return page

if __name__ == '__main__':
    out = 'd1v2_frames'; os.makedirs(out, exist_ok=True)
    frames = [STILL] if STILL >= 0 else range(int(os.environ.get('FROM', '0')), N)
    for v in frames:
        p = frame(v)
        if STILL >= 0: p.convert('RGB').save(f'check/d1v2_{v:04d}.png')
        else: p.convert('RGB').save(f'{out}/{v:04d}.png')
    print('d1 v2', len(frames))
