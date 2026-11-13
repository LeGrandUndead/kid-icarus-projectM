# v7 = layout v5 "Dream" + cutscene light (v6) + clearer focus on the vine (ui_v7).
# python3 still_v7.py [together vault options]  ->  check/v7_<mode>.png
# Layout v5 "Dream" (Kevin's pick, 2026-11-12): the mode's game stage,
# blurred and washed in the mode's colour with a little paper grain; the
# heading and its flourish; the character with a soft glow and the game's
# particles; the black ground band with the description; no boxes.
lib = {'__name__': 'lib'}; exec(open('menu_anim.py').read(), lib)
g = globals(); g.update({k: v for k, v in lib.items() if not k.startswith('__')})
exec(open('ui_v4.py').read()); exec(open('ui_v7.py').read())
from PIL import ImageChops, ImageEnhance
import importlib.util, sys as _s; _s.path.insert(0, '.'); import grade as G

def dream_bg(name, i, m):
    st = Image.open(f'bg/{name}.png').convert('RGB').resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(10))
    st = ImageEnhance.Brightness(st).enhance(1.35); st = ImageEnhance.Color(st).enhance(0.75)
    wash = Image.new('RGB', (W, H), tuple(int(c * 0.55 + 255 * 0.45) for c in m['color']))
    st = Image.blend(st, wash, 0.45)
    return Image.blend(st, background(m, i).convert('RGB'), 0.22).convert('RGBA')

def heading_only(m):
    lay = Image.new('RGBA', (W, H)); y0, y1 = m['head']
    hd = HEADS.crop((0, int(y0 * HEADS.height), HEADS.width, int(y1 * HEADS.height)))
    ink = hd.getchannel('A').point(lambda a: 255 if a > 200 else 0)
    l, t, r, b = ink.getbbox(); hd = fit(hd.crop((max(0, l - 24), max(0, t - 24), r + 24, b + 24)), h=170)
    lay.alpha_composite(hd, (int(HEAD_X - hd.width / 2), 230))
    fl = flourish_v4(570); lay.alpha_composite(fl, (int(HEAD_X - fl.width / 2), 230 + hd.height - 26))
    return lay

SHOTS = {
    'together': (1, lambda: Image.open(f'{R}/together/0100.png').convert('RGBA'), 1450, H + 40, 860),
    'vault':    (2, lambda: Image.open(f'{R}/vault/0100.png').convert('RGBA'), 1440, BAND_Y + 30, 760),
    'options':  (3, lambda: Image.open(f'{R}/options/0100.png').convert('RGBA'), 1440, BAND_Y + 30, 720),
}
BAND = ground_band(); CTRL4 = controls_v4()
for name, (i, get, cx, feet, height) in SHOTS.items():
    if _s.argv[1:] and name not in _s.argv[1:]: continue
    m = MODES[i]; t = 2.0
    page = dream_bg(name, i, m)
    ch = get(); ch = ch.crop(ch.getbbox()); k = height / ch.height
    ch = ch.resize((int(ch.width * k), int(ch.height * k)), Image.LANCZOS)
    x0, y0 = int(cx - ch.width / 2), int(feet - ch.height)
    # cutscene light: rays from behind, the character, particles, bloom, flares, grade
    lc = tuple(int(c * 0.35 + 255 * 0.65) for c in m['color'])
    ray = {'together': 0.55, 'vault': 0.28, 'options': 0.30}[name]      # light scenes need less
    page = G.add(page, G.backlight_rays((W, H), cx + 60, y0 + ch.height * 0.30, lc, strength=ray))
    page.alpha_composite(soft_glow(ch, (255, 250, 235), 0.45, 22), (x0, y0)); page.alpha_composite(ch, (x0, y0))
    particles(page, name, t, cx, y0 + ch.height * 0.45)
    page = G.bloom(page, threshold=0.80, strength=0.38)
    page = G.flares(page, G.bright_points(ch, x0, y0))
    page = G.grade(page)
    page.alpha_composite(heading_only(m)); page.alpha_composite(BAND); page.alpha_composite(caption_band(m))
    page.alpha_composite(buttons_v7(i, 0.2)); page.alpha_composite(CTRL4)
    page.convert('RGB').save(f'check/v7_{name}.png'); print(name, flush=True)
