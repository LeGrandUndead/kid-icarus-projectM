# v7 "game-menu feel": clearer focus on the vine, after what most game menus
# do (Smash Ultimate, Xenoblade, Mario Kart...), in KIU's own art:
#   - the other buttons step back: a little darker and less saturated
#   - the chosen one steps forward: bigger, leaning out from the vine
#   - a glint of light runs across it every couple of seconds
# k (0..1) is how far the focus has settled, so a change can be animated.
# Needs menu_anim.py's ITEMS, BTN, vine, fit, put, kA, U already loaded.
from PIL import ImageEnhance

DIM = 0.72        # brightness of the buttons not chosen
DESAT = 0.70      # their colour
GROW = 1.13       # the chosen button's size
LEAN = 22         # how far it leans out from the vine, in pixels

def glint(btn, t, period=2.4, width=0.16):
    """A diagonal band of light sweeping across the button, kept inside its
    shape. Visible for the first 0.5 s of every `period` seconds."""
    w, h = btn.size; ph = (t % period) / 0.5
    if ph >= 1: return btn
    yy, xx = np.mgrid[0:h, 0:w]
    pos = (xx / w + 0.35 * yy / h) / 1.35                 # 0..1 along the diagonal
    c = -width + ph * (1 + 2 * width)
    band = np.clip(1 - np.abs(pos - c) / width, 0, 1) ** 1.5
    a = np.asarray(btn.getchannel('A'), np.float32) / 255
    lay = np.zeros((h, w, 4), np.float32); lay[..., :3] = 255; lay[..., 3] = band * a * 200
    out = btn.copy(); out.alpha_composite(Image.fromarray(lay.astype(np.uint8))); return out

def step_back(p, k):
    q = ImageEnhance.Color(p).enhance(1 - (1 - DESAT) * k)
    q = ImageEnhance.Brightness(q).enhance(1 - (1 - DIM) * k)
    q.putalpha(p.getchannel('A')); return q

def buttons_v7(sel, t, k=1.0):
    lay = Image.new('RGBA', (W, H)); s = 0.46; rects = []; placed = []
    for (r, rot, (x, y), ang, node), p in zip(ITEMS, BTN):
        dy = math.sin(t * 1.3 + node * 2.1) * 1.2; dx = math.sin(t * 0.9 + node * 1.7) * 0.7
        w, h = p.width / kA * s, p.height / kA * s
        rects.append((x + dx, y + dy, x + dx + w, y + dy + h)); placed.append((p, x + dx, y + dy, w, h, ang, node))
    big = Image.new('L', (W * 2, H * 2), 0); d = ImageDraw.Draw(big)
    for poly in vine(rects): d.polygon([(px * U * 2, py * U * 2) for px, py in poly], fill=255)
    mv = big.resize((W, H), Image.LANCZOS)
    sh = Image.new('RGBA', (W, H)); sh.putalpha(mv.filter(ImageFilter.GaussianBlur(5)).point(lambda v: v * 0.3)); lay.alpha_composite(sh, (5, 8))
    blk = Image.new('RGBA', (W, H), (10, 6, 8, 255)); blk.putalpha(mv); lay.alpha_composite(blk)
    # the chosen one last, so it sits over its neighbours when it grows
    for p, x, y, w, h, ang, node in sorted(placed, key=lambda e: e[6] == sel):
        on = node == sel
        if on:
            b = glint(fit(p, w=w * U * (1 + (GROW - 1) * k)), t)
            lift = (GROW - 1) * k * h * U / 2 if node == 3 else 0     # the bottom one grows upward, clear of the band
            put(lay, b, x * U + w * U / 2 + LEAN * k, y * U + h * U / 2 - lift, anchor='c', sh=(8, 0.55, 8, 12),
                gl=(11, 12, (255, 208, 84), 0.75 + 0.25 * math.sin(t * 4)), rot=ang)
        else:
            put(lay, step_back(fit(p, w=w * U), k), x * U + w * U / 2, y * U + h * U / 2, anchor='c', sh=(6, 0.5, 6, 9), rot=ang)
    return lay
