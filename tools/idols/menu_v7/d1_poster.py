# Direction 1, "action poster" (Together): a strong diagonal, the stage in a
# slanted panel, the characters mid-kick breaking out of it, speed lines
# from the impact, a huge tilted heading with a block shadow, the buttons
# stepping down the diagonal, slanted ribbons for the caption and controls.
#   python3 d1_poster.py  ->  check/d1_together.png
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
import grade as G
from PIL import ImageEnhance, ImageChops

m = MODES[1]; ORANGE = (232, 140, 70); GOLD = (250, 205, 110); INK = (14, 8, 20)
IMPACT = (1290, 470)

def slant(x0, x1, y0, y1, lean):
    """A parallelogram: top edge from x0 to x1 at y0, bottom shifted left by `lean`."""
    return [(x0, y0), (x1, y0), (x1 - lean, y1), (x0 - lean, y1)]

# 1. deep violet behind everything, with comic halftone dots
yy, xx = np.mgrid[0:H, 0:W]
base = np.zeros((H, W, 3), np.float32)
k = (xx / W * 0.6 + yy / H * 0.4)[..., None]
base[:] = np.array([30, 14, 52]) * (1 - k) + np.array([74, 30, 96]) * k
page = Image.fromarray(base.astype(np.uint8)).convert('RGBA')
dots = Image.new('L', (W, H)); d = ImageDraw.Draw(dots)
for y in range(0, H, 22):
    for x in range(0, W, 22):
        r = 7 * max(0, 1 - x / (W * 0.55))          # big near the left edge, fading out
        if r > 0.6: d.ellipse((x - r, y - r, x + r, y + r), fill=60)
lay = Image.new('RGBA', (W, H), (150, 90, 210, 0)); lay.putalpha(dots); page.alpha_composite(lay)

# 2. the stage in a slanted panel (sharp, warm), black and gold border
PANEL = slant(860, W + 300, -20, H + 20, 330)
stage = Image.open('bg/together.png').convert('RGB').resize((W, H), Image.LANCZOS)
stage = ImageEnhance.Color(stage).enhance(1.25); stage = ImageEnhance.Brightness(stage).enhance(1.15)
warm = Image.new('RGB', (W, H), ORANGE); stage = Image.blend(stage, warm, 0.25).convert('RGBA')
mk_ = Image.new('L', (W, H)); ImageDraw.Draw(mk_).polygon(PANEL, fill=255)
page.paste(stage, (0, 0), mk_)
page = G.add(page, G.backlight_rays((W, H), *IMPACT, (255, 220, 160), n=26, length=1600, strength=0.6))
bd = ImageDraw.Draw(page)
bd.line([PANEL[0], PANEL[3]], fill=INK + (255,), width=26)
bd.line([(PANEL[0][0] + 14, PANEL[0][1]), (PANEL[3][0] + 14, PANEL[3][1])], fill=GOLD + (255,), width=7)

# 3. speed lines out of the impact
sl = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(sl); rnd = random.Random(3)
for _ in range(90):
    a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(260, 420); r1 = r0 + rnd.uniform(500, 1400); w = rnd.uniform(0.004, 0.012)
    d.polygon([(IMPACT[0] + math.cos(a) * r0, IMPACT[1] + math.sin(a) * r0),
               (IMPACT[0] + math.cos(a - w) * r1, IMPACT[1] + math.sin(a - w) * r1),
               (IMPACT[0] + math.cos(a + w) * r1, IMPACT[1] + math.sin(a + w) * r1)], fill=(255, 250, 235, int(rnd.uniform(90, 200))))
sl_m = sl.getchannel('A'); sl.putalpha(ImageChops.multiply(sl_m, mk_.filter(ImageFilter.GaussianBlur(30))))
page.alpha_composite(sl)

# 4. the characters, mid-kick, bigger than the panel and breaking its edge
ch = Image.open(S + '/poster/tog_190_-30.png').convert('RGBA'); ch = ch.crop(ch.getbbox())
ch = fit(ch, h=1180); x0, y0 = W - ch.width + 60, H - ch.height + 150
page.alpha_composite(soft_glow(ch, (255, 235, 200), 0.55, 26), (x0, y0)); page.alpha_composite(ch, (x0, y0))
fl = additive_sprite(fx_tex('doll_008_doll', 'ptc_cmn_flashA'), (255, 200, 140), (520, 520))
glow = Image.new('RGBA', (W, H)); glow.alpha_composite(fl, (IMPACT[0] - 260, IMPACT[1] - 260)); page = G.add(page, glow)
# feathers thrown out of the impact
lay = Image.new('RGBA', (W, H)); rnd = random.Random(8); hane = fx_tex('demo_024_demo', 'ptc_c05_040_hane')
for n in range(26):
    a = rnd.uniform(0, 2 * math.pi); dd = rnd.uniform(160, 620)
    col = (255, 255, 255) if n % 3 else (120, 90, 170)
    s_ = additive_sprite(hane, col, (90, 45)).rotate(math.degrees(-a) + rnd.uniform(-30, 30), expand=True)
    lay.alpha_composite(s_, (int(IMPACT[0] + math.cos(a) * dd - s_.width / 2), int(IMPACT[1] + math.sin(a) * dd - s_.height / 2)))
page.alpha_composite(lay)
page = G.bloom(page, threshold=0.8, strength=0.35)
page = G.grade(page, vignette=0.22)

# 5. the heading: huge, tilted, with a block shadow in the mode's colour
y0_, y1_ = m['head']
hd = HEADS.crop((0, int(y0_ * HEADS.height), HEADS.width, int(y1_ * HEADS.height)))
ink = hd.getchannel('A').point(lambda a: 255 if a > 200 else 0); hd = hd.crop(ink.getbbox())
hd = fit(hd, h=150).rotate(6, expand=True, resample=Image.BICUBIC)
shadow_ = Image.new('RGBA', hd.size, ORANGE + (0,)); shadow_.putalpha(hd.getchannel('A'))
page.alpha_composite(shadow_, (60 + 12, 70 + 12)); page.alpha_composite(hd, (60, 70))
fl2 = flourish_v4(470).rotate(6, expand=True, resample=Image.BICUBIC); page.alpha_composite(fl2, (110, 70 + hd.height - 40))

# 6. the buttons stepping down the diagonal; the chosen one big and bright
NATIVE = [192, 183, 118, 173]                     # the buttons' own widths in the game
for i, (p, (cx_, by)) in enumerate(zip(BTN, [(270, 420), (330, 580), (240, 745), (250, 860)])):
    on = i == 1
    w = NATIVE[i] * (2.8 if on else 1.5)
    b = fit(p, w=w)
    b = glint(b, 0.2) if on else step_back(b, 1.0)
    put(page, b, cx_, by, anchor='c', sh=(10, 0.6, 10, 14), gl=(13, 14, (255, 208, 84), 1.0) if on else None, rot=-6)

# 7. slanted ribbons: the caption (left), the controls (right)
rb = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(rb)
d.polygon(slant(-40, 1010, 975, 1045, 18), fill=INK + (235,)); d.line([(0, 973), (1010, 973)], fill=GOLD + (255,), width=4)
spaced_text(d, (500, 1010), m['cap'], ImageFont.truetype(GAME_FONT, 34), (250, 244, 232, 255), 3)
d.polygon(slant(1330, W + 40, 1005, 1065, 18), fill=INK + (235,))
page.alpha_composite(rb)
c4 = controls_v4(); page.alpha_composite(c4, (0, -2))
page.convert('RGB').save('check/d1_together.png'); print('d1')
