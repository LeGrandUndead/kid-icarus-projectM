# Together / Vault / Options in layout v5 "Dream", 60 fps.
#   idle:  the stage behind drifts slowly, particles move, the character
#          plays its idle (rendered with the extra menu shading)
#   click: the menu leaves (buttons slide off along the vine, the heading
#          rises, the ground band sinks), the camera pushes in while the
#          move plays, a burst of the game's particles in the mode's colour
#   wipe:  together: a slash, the halves part, feathers fly
#          vault:    a ring of light opens from Palutena's staff
#          options:  Viridi's swing sweeps the next screen in, petals on its edge
# python3 cast_menu_v7.py together vault options   ->  <mode>_frames_v7/
import sys
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v3.py').read()); exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
exec(open('still_v7.py').read().split('SHOTS = {')[0].split('from PIL import ImageChops, ImageEnhance')[1])   # dream_bg, heading_only
import json, random
import grade as G
from PIL import ImageChops, ImageEnhance
FPS = 60

def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)

def zoom(img, z, cx, cy):
    """The image scaled by z about the point (cx, cy), same size."""
    if abs(z - 1) < 1e-4: return img
    w, h = img.size; nw, nh = int(w * z), int(h * z)
    big = img.resize((nw, nh), Image.BILINEAR)
    x0, y0 = int(cx * z - cx), int(cy * z - cy)
    return big.crop((x0, y0, x0 + w, y0 + h))

def faded(img, a):
    if a >= 0.999: return img
    out = img.copy(); out.putalpha(out.getchannel('A').point(lambda v: int(v * a))); return out

def cursor(page, x, y, down):
    s = 1.3 * (0.9 if down else 1.0); pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    ImageDraw.Draw(page).polygon([(x + px * s, y + py * s) for px, py in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)

def add_light(page, lay):
    """Additive blend, as the game draws its glows and particles."""
    rgb = Image.alpha_composite(Image.new('RGBA', page.size, (0, 0, 0, 255)), lay).convert('RGB')
    return ImageChops.add(page.convert('RGB'), rgb).convert('RGBA')

def card_v5(name, i, m):
    """Stand-in for the next screen: the same scene, softer, the mode's
    emblem and its heading large."""
    c = dream_bg(name, i, m).filter(ImageFilter.GaussianBlur(6))
    e, _ = art(*m['emb']); e = fit(mask(e, (255, 255, 255), 0.35), h=900); put(c, e, W / 2, H / 2, anchor='c')
    y0, y1 = m['head']
    hd = HEADS.crop((0, int(y0 * HEADS.height), HEADS.width, int(y1 * HEADS.height)))
    ink = hd.getchannel('A').point(lambda a: 255 if a > 200 else 0)
    l, t, r, b = ink.getbbox(); hd = fit(hd.crop((max(0, l - 24), max(0, t - 24), r + 24, b + 24)), h=240)
    c.alpha_composite(hd, (int(W / 2 - hd.width / 2), int(H * 0.40 - hd.height / 2)))
    fl = flourish_v4(820); c.alpha_composite(fl, (int(W / 2 - fl.width / 2), int(H * 0.40 + hd.height / 2 - 30)))
    return c

# the game's particle images used by the bursts
FLASH = fx_tex('doll_008_doll', 'ptc_cmn_flashA')
HANE = fx_tex('demo_024_demo', 'ptc_c05_040_hane')
LEAF = Image.fromarray(fx_tex('demo_051_demo', 'ptc_c11_030_NatLeaf'))
PETALS = [LEAF.crop((x, y, x + 32, y + 32)) for x in (0, 32) for y in (0, 32)]
SPARK = mirrored(fx_tex('demo_024_demo', 'ptc_c05_040_hikari01'))

def burst(mode, m, gg, cx, cy):
    """At the click: a flash in the mode's colour and the mode's particles
    thrown outward."""
    lay = Image.new('RGBA', (W, H))
    if gg < 0 or gg > 34: return lay
    col = tuple(int(c * 0.5 + 255 * 0.5) for c in m['color'])
    k = ease(gg / 10); fade = 1 - ease((gg - 8) / 22)
    s = int(300 + 900 * k)
    put(lay, faded(additive_sprite(FLASH, col, (s, s)), fade * 0.9), cx, cy, anchor='c')
    rnd = random.Random(11)
    for n in range(26):
        a = rnd.uniform(0, 2 * math.pi); sp = rnd.uniform(14, 34); d = sp * gg * (1 - gg / 90)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d + 0.15 * gg * gg
        if mode == 'options':
            p = PETALS[n % 4].resize((44, 44), Image.BILINEAR).rotate(gg * 12 + n * 40, expand=True)
            put(lay, faded(p, fade), x, y, anchor='c')
        elif mode == 'together':
            col2 = (255, 255, 255) if n % 2 else (120, 90, 170)
            p = additive_sprite(HANE, col2, (70, 35)).rotate(math.degrees(-a) + gg * 6, expand=True)
            put(lay, faded(p, fade), x, y, anchor='c')
        else:
            p = additive_sprite(SPARK, (200, 255, 245), (36, 36))
            put(lay, faded(p, fade), x, y, anchor='c')
    return lay

def run(name):
    i = {'together': 1, 'vault': 2, 'options': 3}[name]; m = MODES[i]
    J = json.load(open(f'{R}/{name}.json')); T = J['timeline']; CLICK = J['click']; WIPE = J['wipe']
    # the scene behind, a little larger so it can drift
    BG = dream_bg(name, i, m).resize((int(W * 1.06), int(H * 1.06)), Image.BILINEAR)
    HEAD = heading_only(m); BAND = ground_band(); CAP = caption_band(m); CTRL4 = controls_v4()
    NEXT = card_v5(name, i, m)
    # where the character goes: fixed from its first frame (no jitter)
    first = Image.open(f'{R}/{name}/0000.png').convert('RGBA'); bb = first.getbbox()
    cx, feet, height = {'together': (1450, H + 40, 860), 'vault': (1440, BAND_Y + 30, 760), 'options': (1440, BAND_Y + 30, 720)}[name]
    k = height / (bb[3] - bb[1])
    ox = cx - ((bb[0] + bb[2]) / 2) * k; oy = feet - bb[3] * k
    size = int(first.width * k)
    CX, CY = cx, feet - height * 0.55                     # the character's middle: camera and burst centre
    LC = tuple(int(c * 0.35 + 255 * 0.65) for c in m['color'])
    RAY = {'together': 0.55, 'vault': 0.28, 'options': 0.30}[name]
    RAYS = G.backlight_rays((W, H), cx + 60, feet - height * 0.70, LC, strength=RAY)
    # star flares on the character's brightest points of its first frame; they twinkle
    fch = first.resize((size, size), Image.LANCZOS)
    FLARES = G.bright_points(fch, int(ox), int(oy))
    BTN = [(18 * U + 120, 22 * U + 70), (28 * U + 130, 60.9 * U + 75), (22 * U + 120, 101.16 * U + 75), (28 * U + 125, 135.98 * U + 75)][i]
    out = f'{name}_frames_v7'; os.makedirs(out, exist_ok=True)
    for old in os.listdir(out): os.remove(f'{out}/{old}')
    for e in T:
        f = e['f']; t = f / FPS; gg = f - CLICK
        push = ease(gg / 45) if gg > 0 else 0            # the camera leans in on the move
        # scene: slow drift, a gentler push than the character (depth)
        dx = int(W * 0.03 + math.sin(t * 0.35) * W * 0.025); dy = int(H * 0.03 + math.cos(t * 0.27) * H * 0.012)
        page = zoom(BG.crop((dx, dy, dx + W, dy + H)), 1 + 0.04 * push, CX, CY)
        page = G.add(page, zoom(RAYS, 1 + 0.04 * push, CX, CY))               # light from behind
        # the character, glow, particles
        ch = Image.open(f'{R}/{name}/{f:04d}.png').convert('RGBA').resize((size, size), Image.LANCZOS)
        lay = Image.new('RGBA', (W, H))
        lay.alpha_composite(soft_glow(ch, (255, 250, 235), 0.45, 22), (int(ox), int(oy)))
        lay.alpha_composite(ch, (int(ox), int(oy)))
        page.alpha_composite(zoom(lay, 1 + 0.10 * push, CX, CY))
        particles(page, name, t, CX, CY)
        page = G.bloom(page, threshold=0.80, strength=0.38)
        tw = [(x, y, k * (0.75 + 0.25 * math.sin(t * 3 + n * 2.1)) * (1 - ease(gg / 10) if gg > 0 else 1)) for n, (x, y, k) in enumerate(FLARES)]
        page = G.flares(page, [p for p in tw if p[2] > 0.05])
        page = G.grade(page)
        page = add_light(page, burst(name, m, gg, CX, CY))
        # the menu, leaving after the click
        leave = ease((gg - 1) / 14) if gg >= 0 else 0
        if leave < 1:
            page.alpha_composite(faded(HEAD, 1 - leave), (0, int(-120 * leave)))
            page.alpha_composite(BAND, (0, int(260 * leave))); page.alpha_composite(faded(CAP, 1 - leave), (0, int(260 * leave)))
            page.alpha_composite(faded(CTRL4, 1 - leave), (0, int(260 * leave)))
            u = buttons_v7(i, t, ease(f / 18))          # v7: clearer focus, settling in
            if 0 <= gg < 6: u = u.resize((int(W * 0.995), int(H * 0.995)))
            page.alpha_composite(u, (int(-760 * leave), 0))
        if gg < 5:                                        # the pointer comes in, hovers, clicks
            kk = ease(f / 110); px, py = W * 0.9 + (BTN[0] - W * 0.9) * kk, H * 0.85 + (BTN[1] - H * 0.85) * kk
            cursor(page, px, py, gg >= 0)
        # the wipe to the next screen
        w = f - WIPE
        if w >= 0:
            kz = ease(w / 22); nxt = zoom(NEXT, 1.06 - 0.06 * kz, W / 2, H / 2)
            if name == 'together':
                a = math.radians(-58); ddx, ddy = math.cos(a), math.sin(a); nx, ny = -ddy, ddx
                msk = Image.new('L', (W, H)); ImageDraw.Draw(msk).polygon([(W/2-ddx*3000-ddy*3000, H/2-ddy*3000+ddx*3000), (W/2+ddx*3000-ddy*3000, H/2+ddy*3000+ddx*3000), (W/2+ddx*3000, H/2+ddy*3000), (W/2-ddx*3000, H/2-ddy*3000)], fill=255)
                gap = 900 * ease(w / 18)
                A = Image.new('RGBA', (W, H)); A.paste(page, (0, 0), msk); B = Image.new('RGBA', (W, H)); B.paste(page, (0, 0), ImageChops.invert(msk))
                base = nxt.copy()
                base.alpha_composite(A.transform((W, H), Image.AFFINE, (1, 0, nx * gap, 0, 1, ny * gap)))
                base.alpha_composite(B.transform((W, H), Image.AFFINE, (1, 0, -nx * gap, 0, 1, -ny * gap)))
                if w < 12:                                # the blade of light, then feathers along the cut
                    ln = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ln); L = 2600 * ease(w / 5)
                    d.line((W/2-ddx*L, H/2-ddy*L, W/2+ddx*L, H/2+ddy*L), fill=(255, 236, 170, int(255 * (1 - w / 12))), width=int(16 * (1 - w / 12)) + 2)
                    base = add_light(base, ln.filter(ImageFilter.GaussianBlur(5))); base.alpha_composite(ln)
                fl = Image.new('RGBA', (W, H)); rnd = random.Random(5)
                for n in range(24):
                    q = rnd.uniform(-1300, 1300); x, y = W/2 + ddx*q, H/2 + ddy*q
                    side = 1 if n % 2 else -1; x += nx * side * (40 + 18 * w); y += ny * side * (40 + 18 * w) + 0.3 * w * w
                    col2 = (255, 255, 255) if n % 3 else (120, 90, 170)
                    put(fl, faded(additive_sprite(HANE, col2, (80, 40)).rotate(n * 37 + w * 9, expand=True), 1 - ease((w - 10) / 14)), x, y, anchor='c')
                page = add_light(base, fl)
            elif name == 'vault':
                cx2, cy2 = CX - 40, CY - 300
                rad = 2300 * ease(w / 22) ** 1.4
                msk = Image.new('L', (W, H)); ImageDraw.Draw(msk).ellipse((cx2-rad, cy2-rad, cx2+rad, cy2+rad), fill=255)
                page = Image.composite(nxt, page, msk.filter(ImageFilter.GaussianBlur(4)))
                ring = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ring)
                for wd, col in [(30, (120, 230, 255, 140)), (10, (255, 236, 170, 255))]:
                    d.ellipse((cx2-rad, cy2-rad, cx2+rad, cy2+rad), outline=col, width=wd)
                ring = ring.filter(ImageFilter.GaussianBlur(6))
                rr = random.Random(w); fade = 1 - ease((w - 14) / 8)
                for _ in range(36):                       # sparkles riding the ring
                    an = rr.uniform(0, 2 * math.pi); q = rad * rr.uniform(0.95, 1.05); s2 = rr.randint(30, 70)
                    put(ring, additive_sprite(SPARK, (255, 250, 220), (s2, s2)), cx2 + math.cos(an) * q, cy2 + math.sin(an) * q, anchor='c')
                page = add_light(page, faded(ring, fade))
            else:
                cx2, cy2 = CX, CY + 80; ang = -200 + 260 * ease(w / 20)
                msk = Image.new('L', (W, H)); ImageDraw.Draw(msk).pieslice((cx2-3000, cy2-3000, cx2+3000, cy2+3000), -200, ang, fill=255)
                page = Image.composite(nxt, page, msk.filter(ImageFilter.GaussianBlur(3)))
                if w < 26:
                    a = math.radians(ang); edge = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(edge)
                    d.line((cx2, cy2, cx2 + math.cos(a) * 3000, cy2 + math.sin(a) * 3000), fill=(255, 210, 230, 200), width=12)
                    edge = edge.filter(ImageFilter.GaussianBlur(7))
                    rr = random.Random(w)
                    for n in range(16):                   # the game's petals along the sweep
                        q = rr.uniform(120, 1700); s2 = rr.randint(34, 64)
                        p = PETALS[n % 4].resize((s2, s2), Image.BILINEAR).rotate(rr.uniform(0, 360), expand=True)
                        put(edge, p, cx2 + math.cos(a) * q + rr.uniform(-40, 40), cy2 + math.sin(a) * q + rr.uniform(-40, 40), anchor='c')
                    page.alpha_composite(faded(edge, 1 - ease((w - 18) / 8)))
        if w >= 24: page = zoom(NEXT, 1.06 - 0.06 * ease(w / 22), W / 2, H / 2)
        page.convert('RGB').save(f'{out}/{f:04d}.png')
    print(name, len(T), flush=True)

if __name__ == '__main__':
    for name in sys.argv[1:]: run(name)
