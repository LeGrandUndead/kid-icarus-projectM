# Direction 2, "living Skyworld" (Vault): the menu is a place. Each mode is a
# floating island in chapter 1's bright sky; the camera would fly between
# them. Here: Vault's island (chapter 20's temple) up close, the other modes'
# islands far away, each with its button floating above it like a banner on a
# beam of light, a trail of sparkles linking them. Palutena stands in the
# clouds in front.   python3 d2_skyworld.py  ->  check/d2_vault.png
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G, glob
from PIL import ImageEnhance, ImageChops

m = MODES[2]; INK = (14, 10, 24); GOLD = (250, 205, 110)
def tex(n): return Image.open(sorted(glob.glob(f'{S}/stages/tex/*/{n}.png'))[0]).convert('RGBA')

# 1. chapter 1's sky: its gradient, its sun
sky = tex('a01m03_bg00').convert('RGB').crop((96, 0, 160, 118)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))
sun = tex('a01m03_sun01').convert('RGB').resize((1000, 1000), Image.BICUBIC)
c = Image.new('RGB', (W, H)); c.paste(sun, (int(W * 0.80) - 500, int(H * 0.06) - 500))
page = ImageChops.screen(sky, c).convert('RGBA')

def cloud_bank(y, height, seed, alpha=1.0, tint=(255, 255, 255)):
    """A soft band of cloud puffs across the screen."""
    lay = Image.new('L', (W, H)); d = ImageDraw.Draw(lay); r = random.Random(seed)
    for _ in range(70):
        x = r.uniform(-100, W + 100); rad = r.uniform(height * 0.4, height)
        d.ellipse((x - rad * 1.6, y - rad * 0.7 + r.uniform(-height * 0.3, height * 0.3), x + rad * 1.6, y + rad * 0.9 + 400), fill=255)
    lay = lay.filter(ImageFilter.GaussianBlur(height * 0.18)).point(lambda v: int(v * alpha))
    out = Image.new('RGBA', (W, H), tint + (0,)); out.putalpha(lay); return out

# 2. far islands: the other modes, small, in the haze; a beam and their button above each
ISL = Image.open(S + '/poster/island.png').convert('RGBA'); ISL = ISL.crop((562, 323, 1560, 1062))
# its bridge runs off to the right: fade the cut edge out
_fa = np.asarray(ISL).copy(); _r = np.clip((ISL.width - np.arange(ISL.width)) / 120, 0, 1); _fa[..., 3] = (_fa[..., 3] * _r[None, :]).astype(np.uint8); ISL = Image.fromarray(_fa)
def far_island(scale, flip, haze, col):
    im = fit(ISL, w=ISL.width * scale)
    if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    hz = np.array([200, 222, 245]) * 0.6 + np.array(col) * 0.4      # haze tinted with the mode's colour
    a = np.asarray(im, np.float32); a[..., :3] = a[..., :3] * (1 - haze) + hz * haze
    return Image.fromarray(a.astype(np.uint8))
def beam(lay, x, y0, y1, w, col):
    b = Image.new('L', (W, H)); ImageDraw.Draw(b).polygon([(x - w, y0), (x + w, y0), (x + w * 0.4, y1), (x - w * 0.4, y1)], fill=120)
    b = b.filter(ImageFilter.GaussianBlur(w * 0.6)); l = Image.new('RGBA', (W, H), col + (0,)); l.putalpha(b); lay.alpha_composite(l)
page.alpha_composite(cloud_bank(760, 90, 1, 0.55, (238, 244, 252)))
FAR = [(0, 0.30, False, 0.5, (300, 640)), (1, 0.22, True, 0.6, (720, 420)), (3, 0.18, False, 0.65, (1560, 330))]
for mode, sc, flip, hz, (x, y) in FAR:
    im = far_island(sc, flip, hz, MODES[mode]['color']); page.alpha_composite(im, (int(x - im.width / 2), int(y - im.height / 2)))
    beam(page, x, y - 200 * sc * 3, y - im.height * 0.2, 26 * sc * 3, (255, 245, 220))
    b = step_back(fit(BTN[mode], w=[192, 183, 118, 173][mode] * sc * 4.2), 0.8)
    put(page, b, x, y - 210 * sc * 3.4, anchor='c', sh=(6, 0.35, 4, 6))

# 3. a trail of sparkles linking the islands (the path the camera would fly)
spark = fx_tex('doll_008_doll', 'ptc_cmn_flashA')
trail = Image.new('RGBA', (W, H)); pts = [(300, 640), (720, 420), (1100, 560), (1560, 330)]
for (ax, ay), (bx, by) in zip(pts, pts[1:]):
    for k in range(18):
        t = k / 18; x = ax + (bx - ax) * t; y = ay + (by - ay) * t - math.sin(t * math.pi) * 90
        s_ = additive_sprite(spark, (255, 230, 160), (30 + 14 * (k % 2), 30 + 14 * (k % 2)))
        trail.alpha_composite(s_, (int(x - s_.width / 2), int(y - s_.height / 2)))
page = G.add(page, trail)

# 4. Vault's island, close, with its button on a beam above it
isl = fit(ISL, w=840).filter(ImageFilter.GaussianBlur(0.6)); ix, iy = 700, 420
page.alpha_composite(soft_glow(isl, (255, 248, 230), 0.35, 30), (ix, iy)); page.alpha_composite(isl, (ix, iy))
beam(page, 1130, 120, 560, 70, (255, 240, 200))
vb = glint(fit(BTN[2], w=118 * 2.6), 0.2)
put(page, vb, 1130, 250, anchor='c', sh=(10, 0.4, 8, 14), gl=(15, 16, (255, 208, 84), 1.0))
page.alpha_composite(cloud_bank(1010, 120, 2, 0.9, (250, 252, 255)))

# 5. Palutena in the clouds in front
pal = Image.open(R + '/vault/0100.png').convert('RGBA'); pal = fit(pal.crop(pal.getbbox()), h=640)
px, py = int(1650 - pal.width / 2), 1080 - pal.height + 70
page = G.add(page, G.backlight_rays((W, H), px + pal.width * 0.5, py + 160, (255, 245, 220), n=20, length=900, strength=0.35))
page.alpha_composite(soft_glow(pal, (255, 250, 235), 0.5, 24), (px, py)); page.alpha_composite(pal, (px, py))
page.alpha_composite(cloud_bank(1120, 90, 3, 1.0, (252, 253, 255)))
page = G.bloom(page, threshold=0.82, strength=0.3)
page = G.grade(page, vignette=0.18)

# 6. heading top left; caption and controls on cloud-white ribbons
y0_, y1_ = m['head']
hd = HEADS.crop((0, int(y0_ * HEADS.height), HEADS.width, int(y1_ * HEADS.height)))
ink = hd.getchannel('A').point(lambda a: 255 if a > 200 else 0); hd = fit(hd.crop(ink.getbbox()), h=130)
page.alpha_composite(hd, (70, 50)); fl = flourish_v4(420); page.alpha_composite(fl, (int(70 + hd.width / 2 - 210), 50 + hd.height - 30))
rb = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(rb)
d.rounded_rectangle((40, 985, 820, 1045), radius=30, fill=INK + (200,))
spaced_text(d, (430, 1015), m['cap'], ImageFont.truetype(GAME_FONT, 32), (250, 244, 232, 255), 3)
d.rounded_rectangle((1320, 1006, W - 40, 1066), radius=30, fill=INK + (200,))
page.alpha_composite(rb); page.alpha_composite(controls_v4())
page.convert('RGB').save('check/d2_vault.png'); print('d2')
