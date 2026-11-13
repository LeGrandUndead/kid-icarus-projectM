# Direction 2 in motion, "living Skyworld": each mode is a floating island in
# chapter 1's sky; the camera glides between them (layers at different
# depths, so nearer things move more). 60 fps, 300 frames:
#   0-130    Together hovered: the camera drifts at Together's island
#   100-130  the pointer moves to Vault's banner
#   130-190  hover changes: the camera glides along the light trail to Vault
#   185-215  Palutena rises from the clouds
#   240      click: the camera dives into the island, the Vault screen opens
#   python3 d2_motion.py  ->  d2_frames/NNNN.png      STILL=N: one frame to check/
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G, glob
from PIL import ImageEnhance, ImageChops
FPS = 60; N = 300; HOVER = 130; CLICK = 240
INK = (14, 10, 24); STILL = int(os.environ.get('STILL', '-1'))
def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)
def back(t, s=1.7):            # ease out with a little overshoot
    t = max(0, min(1, t)); t -= 1; return t * t * ((s + 1) * t + s) + 1
def tex(n): return Image.open(sorted(glob.glob(f'{S}/stages/tex/*/{n}.png'))[0]).convert('RGBA')

# --- prepared layers -----------------------------------------------------------
sky = tex('a01m03_bg00').convert('RGB').crop((96, 0, 160, 118)).resize((W + 400, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))
sun = tex('a01m03_sun01').convert('RGB').resize((1000, 1000), Image.BICUBIC)
c = Image.new('RGB', (W + 400, H)); c.paste(sun, (int(W * 0.85) - 500, int(H * 0.06) - 500))
SKY = ImageChops.screen(sky, c).convert('RGBA')

def cloud_band(width, y, height, seed, alpha, tint=(250, 252, 255)):
    lay = Image.new('L', (width, H)); d = ImageDraw.Draw(lay); r = random.Random(seed)
    for _ in range(int(width / 25)):
        x = r.uniform(-100, width + 100); rad = r.uniform(height * 0.4, height)
        d.ellipse((x - rad * 1.6, y - rad * 0.7 + r.uniform(-height * 0.3, height * 0.3), x + rad * 1.6, y + rad * 0.9 + 400), fill=255)
    lay = lay.filter(ImageFilter.GaussianBlur(height * 0.18)).point(lambda v: int(v * alpha))
    out = Image.new('RGBA', (width, H), tint + (0,)); out.putalpha(lay); return out
FAR_CLOUDS = cloud_band(W * 3, 760, 90, 1, 0.55, (238, 244, 252))
NEAR_CLOUDS = cloud_band(W * 4, 1110, 110, 3, 1.0)

ISL = Image.open(S + '/poster/island.png').convert('RGBA').crop((562, 323, 1560, 1062))
_fa = np.asarray(ISL).copy(); _r = np.clip((ISL.width - np.arange(ISL.width)) / 120, 0, 1); _fa[..., 3] = (_fa[..., 3] * _r[None, :]).astype(np.uint8)
ISL = Image.fromarray(_fa).filter(ImageFilter.GaussianBlur(0.5))
def tinted(img, col, amount):
    a = np.asarray(img, np.float32).copy(); a[..., :3] = a[..., :3] * (1 - amount) + np.array(col) * amount
    return Image.fromarray(a.astype(np.uint8))
# islands: mode, world x, y, depth (1 = the plane the camera glides along), width, flip, haze colour, haze
ISLANDS = [(0, -2600, 40, 0.55, 300, False, (255, 190, 215), 0.55),
           (3, 1500, 60, 0.6, 330, True, (205, 180, 240), 0.5),
           (1, -1300, 190, 1.0, 700, True, (255, 190, 140), 0.35),
           (2, 0, 210, 1.0, 800, False, (255, 255, 255), 0.0)]
ISL_IMG = {i[0]: tinted(ISL.transpose(Image.FLIP_LEFT_RIGHT) if i[5] else ISL, i[6], i[7]) for i in ISLANDS}
NATIVE = [192, 183, 118, 173]
FLASH = fx_tex('doll_008_doll', 'ptc_cmn_flashA')
DOT = additive_sprite(FLASH, (255, 232, 165), (40, 40)); DOT_S = additive_sprite(FLASH, (255, 232, 165), (28, 28))

def heading(i, h=130):
    y0, y1 = MODES[i]['head']
    hd = HEADS.crop((0, int(y0 * HEADS.height), HEADS.width, int(y1 * HEADS.height)))
    ink = hd.getchannel('A').point(lambda a: 255 if a > 200 else 0)
    hd = fit(hd.crop(ink.getbbox()), h=h); lay = Image.new('RGBA', (max(hd.width, 420) + 40, hd.height + 140))
    lay.alpha_composite(hd, (0, 0)); fl = flourish_v4(int(400 * h / 130)); lay.alpha_composite(fl, (max(0, int(hd.width / 2 - fl.width / 2)), hd.height - int(30 * h / 130)))
    return lay
HEAD = {1: heading(1), 2: heading(2)}
def caption(i):
    lay = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle((40, 985, 820, 1045), radius=30, fill=INK + (200,))
    spaced_text(d, (430, 1015), MODES[i]['cap'], ImageFont.truetype(GAME_FONT, 32), (250, 244, 232, 255), 3)
    return lay
CAP = {1: caption(1), 2: caption(2)}
CTRL = Image.new('RGBA', (W, H)); ImageDraw.Draw(CTRL).rounded_rectangle((1320, 1006, W - 40, 1066), radius=30, fill=INK + (200,)); CTRL.alpha_composite(controls_v4())
# the Vault screen behind the dive: the island's light, the heading big
CARD = Image.new('RGBA', (W, H), (250, 244, 228, 255))
CARD = G.add(CARD, G.backlight_rays((W, H), W / 2, H / 2, (255, 220, 150), n=24, length=1400, strength=0.5))
_h = heading(2, h=300); _h = _h.crop(_h.getbbox()); CARD.alpha_composite(_h, (int(W / 2 - _h.width / 2), int(H / 2 - _h.height / 2)))

# --- the camera ------------------------------------------------------------------
def camera(v):
    """x, y and zoom of the camera at frame v."""
    x0 = -1300 + 60 * math.sin(v / 70)
    k = ease((v - HOVER) / 60)
    x = x0 + (0 - x0) * k + (25 * math.sin(v / 80) if v > HOVER + 60 else 0)
    y = 20 * math.sin(v / 90)
    z = 1 + 0.02 * math.sin(v / 60)
    if v >= CLICK:
        kd = ((v - CLICK) / 40) ** 2
        z *= 1 + 3.5 * min(1, kd); y += -40 * min(1, kd)
    return x, y, z
def at(x, y, d, cam):
    cx, cy, z = cam
    return W / 2 + (x - cx) * d * z, H * 0.52 + (y - cy) * d * z

def frame(v, page_hover_prev):
    cam = camera(v); cx, cy, z = cam
    hov = 1 if v < HOVER else 2
    kh = ease((v - HOVER) / 15)                                     # how far the new hover has settled
    page = SKY.crop((int(200 + cx * 0.05), 0, int(200 + cx * 0.05) + W, H)).copy()
    o = int((cx * 0.3) % W); page.alpha_composite(FAR_CLOUDS.crop((o, 0, o + W, H)))
    # islands, far ones first
    pos = {}
    for mode, x, y, d, w, flip, col, hz in ISLANDS:
        sx, sy = at(x, y, d, cam); sc = z ** (0.4 if d < 1 else 1.0)
        im = ISL_IMG[mode]; ww = w * sc; im = im.resize((max(2, int(ww)), max(2, int(im.height * ww / im.width))), Image.BILINEAR)
        if mode in (1, 2):
            page.alpha_composite(soft_glow(im, (255, 248, 230), 0.3, 24), (int(sx - im.width / 2), int(sy - im.height / 2)))
        page.alpha_composite(im, (int(sx - im.width / 2), int(sy - im.height / 2)))
        pos[mode] = (sx, sy - im.height * 0.55, ww)
    # the light trail between the banners
    trail = Image.new('RGBA', (W, H)); order = [pos[0], pos[1], pos[2], pos[3]]
    for (ax, ay, _), (bx, by, _) in zip(order, order[1:]):
        for k in range(16):
            t = (k + (v * 0.08) % 1) / 16; x = ax + (bx - ax) * t; y = ay + (by - ay) * t - math.sin(t * math.pi) * 80
            s_ = DOT if k % 2 else DOT_S; trail.alpha_composite(s_, (int(x - s_.width / 2), int(y - s_.height / 2)))
    page = G.add(page, trail)
    # banners: the hovered one big, bright, on a beam; the others small and dim
    for mode in (0, 3, 1, 2):
        bx, by, ww = pos[mode]
        on = 0
        if mode == hov: on = kh if hov == 2 else 1 - (kh if v >= HOVER else 0)
        if mode == 1 and v >= HOVER: on = 1 - kh
        if mode == 2 and v < HOVER: on = 0
        size = NATIVE[mode] * (1.5 + 1.3 * back(on)) * (z ** 0.5 if mode in (1, 2) else 1)
        b = fit(BTN[mode], w=size)
        b = glint(b, v / FPS) if on > 0.5 else step_back(b, 1 - on)
        if on > 0.05:
            beam = Image.new('L', (W, H)); bw = 60 * on
            ImageDraw.Draw(beam).polygon([(bx - bw, by - 60), (bx + bw, by - 60), (bx + bw * 0.4, by + 220), (bx - bw * 0.4, by + 220)], fill=int(110 * on))
            bl = Image.new('RGBA', (W, H), (255, 240, 200, 0)); bl.putalpha(beam.filter(ImageFilter.GaussianBlur(40))); page.alpha_composite(bl)
        put(page, b, bx, by - 70 - 40 * on + 6 * math.sin(v / 25 + mode), anchor='c', sh=(8, 0.4, 6, 10),
            gl=(13, 14, (255, 208, 84), on) if on > 0.05 else None)
    # Palutena rises from the clouds once the camera reaches Vault
    if v >= 185:
        pal = Image.open(f'{R}/vault/{min(v - 185, 149):04d}.png').convert('RGBA'); pal = fit(pal.crop(pal.getbbox()), h=600 * z ** 0.6)
        px, py = at(560, 470, 1.15, cam); rise = 1 - back((v - 185) / 30, 1.2)
        px, py = px - pal.width / 2, py - pal.height + 60 + 400 * rise
        page.alpha_composite(soft_glow(pal, (255, 250, 235), 0.5, 24), (int(px), int(py))); page.alpha_composite(pal, (int(px), int(py)))
    o = int((cx * 1.5 * z + v * 0.6) % W); page.alpha_composite(NEAR_CLOUDS.crop((o, 0, o + W, H)))
    page = G.bloom(page, threshold=0.84, strength=0.28)
    page = G.grade(page, vignette=0.18)
    # the menu: heading and caption swap with a drop and a bounce when the hover changes
    lv = 1 - ease((v - CLICK) / 12) if v >= CLICK else 1
    for i, k in ((1, 1 - ease((v - HOVER) / 10) if v >= HOVER else 1), (2, back((v - HOVER - 6) / 18) if v >= HOVER + 6 else 0)):
        a = k * lv
        if a <= 0.01: continue
        hd = HEAD[i]; yoff = (1 - k) * (-60 if i == 1 else -120)
        if a < 0.99: hd = hd.copy(); hd.putalpha(hd.getchannel('A').point(lambda q, a=a: int(q * min(1, a))))
        page.alpha_composite(hd, (70, int(50 + yoff)))
        cp = CAP[i]
        if a < 0.99: cp = cp.copy(); cp.putalpha(cp.getchannel('A').point(lambda q, a=a: int(q * min(1, a))))
        page.alpha_composite(cp)
    if lv > 0.01:
        cl = CTRL if lv > 0.99 else CTRL.copy()
        if lv <= 0.99: cl.putalpha(cl.getchannel('A').point(lambda q: int(q * lv)))
        page.alpha_composite(cl)
    # the pointer: comes in, moves to Vault's banner, clicks
    if v < CLICK + 6:
        if v < 100: px_, py_ = W * 0.9 + (pos[1][0] + 40 - W * 0.9) * ease(v / 90), H * 0.8 + (pos[1][1] - 60 - H * 0.8) * ease(v / 90)
        elif v < HOVER: k = ease((v - 100) / 30); px_, py_ = pos[1][0] + 40 + (pos[2][0] + 40 - pos[1][0] - 40) * k, pos[1][1] - 60 + (pos[2][1] - 100 - pos[1][1] + 60) * k
        else: px_, py_ = pos[2][0] + 40, pos[2][1] - 100
        s = 1.3 * (0.9 if v >= CLICK else 1.0); pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
        ImageDraw.Draw(page).polygon([(px_ + x * s, py_ + y * s) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    # the dive: the island fills the screen, a flash, the Vault screen
    if v >= CLICK:
        kd = (v - CLICK) / 40
        if kd > 0.55:
            a = ease((kd - 0.55) / 0.35); page = Image.blend(page.convert('RGB'), CARD.convert('RGB'), a).convert('RGBA')
        if 0.4 < kd < 1.0:
            fl = Image.new('RGBA', (W, H), (255, 245, 220, int(200 * math.sin((kd - 0.4) / 0.6 * math.pi)))); page.alpha_composite(fl)
    return page

if __name__ == '__main__':
    out = 'd2_frames'; os.makedirs(out, exist_ok=True)
    frames = [STILL] if STILL >= 0 else range(int(os.environ.get('FROM', '0')), N)
    for v in frames:
        p = frame(v, None)
        if STILL >= 0: p.convert('RGB').save(f'check/d2m_{v:04d}.png')
        else: p.convert('RGB').save(f'{out}/{v:04d}.png')
    print('d2 motion', len(frames))
