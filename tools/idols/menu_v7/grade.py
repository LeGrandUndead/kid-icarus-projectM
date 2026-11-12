# "Cutscene light" for the menus, after what the game shows in its own
# cutscenes and flight (chapter 1 gate and opening, captured 2026-11-12):
#   - light from behind: soft rays fanning out behind the character
#   - bloom: bright parts glow into their surroundings
#   - star flares (the game's four-point sparkle) on a few bright points
#   - a gentle grade: warm highlights, cool shadows, darker corners
# Each step is a small function on a PIL RGBA page (W x H).
import numpy as np, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

def backlight_rays(size, cx, cy, color, n=22, length=1500, strength=0.55, seed=4):
    """Soft rays of light fanning out from (cx, cy), drawn at quarter size
    and blurred, for an additive layer."""
    W, H = size; q = 4
    lay = Image.new('L', (W // q, H // q)); d = ImageDraw.Draw(lay); rnd = random.Random(seed)
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.12, 0.12); w = rnd.uniform(0.03, 0.08); L = length * rnd.uniform(0.6, 1.0) / q
        p = [(cx / q, cy / q), (cx / q + math.cos(a - w) * L, cy / q + math.sin(a - w) * L), (cx / q + math.cos(a + w) * L, cy / q + math.sin(a + w) * L)]
        d.polygon(p, fill=int(255 * rnd.uniform(0.35, 1.0)))
    # fade with distance from the centre
    yy, xx = np.mgrid[0:H // q, 0:W // q]
    r = np.sqrt((xx - cx / q) ** 2 + (yy - cy / q) ** 2) / (length / q)
    m = np.asarray(lay, np.float32) / 255 * np.clip(1 - r, 0, 1) ** 1.5
    core = np.exp(-(r * 3.2) ** 2)                       # the bright source itself
    m = np.clip(m + core * 0.9, 0, 1) * strength
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
    out = Image.new('RGBA', (W, H), color + (0,)); out.putalpha(img)
    return out

def add(page, lay):
    rgb = Image.alpha_composite(Image.new('RGBA', page.size, (0, 0, 0, 255)), lay).convert('RGB')
    return ImageChops.add(page.convert('RGB'), rgb).convert('RGBA')

def bloom(page, threshold=0.72, radius=28, strength=0.55):
    """Bright parts glow: keep what is above the threshold, blur it, add it back."""
    W, H = page.size; q = 3
    small = page.convert('RGB').resize((W // q, H // q), Image.BILINEAR)
    a = np.asarray(small, np.float32) / 255
    b = np.clip((a - threshold) / (1 - threshold), 0, 1) * a
    g = Image.fromarray((b * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius / q)).resize((W, H), Image.BILINEAR)
    g = Image.fromarray((np.asarray(g, np.float32) * strength).clip(0, 255).astype(np.uint8))
    return ImageChops.screen(page.convert('RGB'), g).convert('RGBA')

def star(size, color):
    """The game's four-point sparkle, drawn as two thin crossed glows."""
    s = size; im = Image.new('L', (s, s)); d = ImageDraw.Draw(im); c = s / 2
    d.polygon([(c, 0), (c + s * 0.04, c), (c, s), (c - s * 0.04, c)], fill=255)
    d.polygon([(0, c), (c, c - s * 0.04), (s, c), (c, c + s * 0.04)], fill=255)
    d.ellipse((c - s * 0.08, c - s * 0.08, c + s * 0.08, c + s * 0.08), fill=255)
    im = im.filter(ImageFilter.GaussianBlur(s / 60))
    out = Image.new('RGBA', (s, s), color + (0,)); out.putalpha(im); return out

def flares(page, points, color=(255, 245, 220), size=140):
    lay = Image.new('RGBA', page.size)
    for (x, y, k) in points:
        st = star(int(size * k), color); lay.alpha_composite(st, (int(x - st.width / 2), int(y - st.height / 2)))
    return add(page, lay)

def grade(page, warm=(1.04, 1.0, 0.94), cool=(0.92, 0.96, 1.06), vignette=0.28):
    """Warm highlights, cool shadows, darker corners."""
    W, H = page.size
    a = np.asarray(page.convert('RGB'), np.float32) / 255
    lum = a.mean(2, keepdims=True)
    tint = np.array(cool) * (1 - lum) + np.array(warm) * lum
    a = a * tint
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a *= (1 - vignette * np.clip(r - 0.55, 0, 1) ** 1.6)[:, :, None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert('RGBA')

def bright_points(ch, x0, y0, n=3, seed=2):
    """A few of the brightest spots of a rendered character (for flares)."""
    a = np.asarray(ch, np.float32); lum = a[..., :3].mean(2) * (a[..., 3] / 255)
    small = Image.fromarray(lum.astype(np.uint8)).resize((ch.width // 16, ch.height // 16), Image.BOX)
    s = np.asarray(small, np.float32); out = []
    for k in range(n):
        iy, ix = np.unravel_index(np.argmax(s), s.shape)
        out.append((x0 + ix * 16 + 8, y0 + iy * 16 + 8, 1.0 - 0.25 * k)); s[max(0, iy - 4):iy + 5, max(0, ix - 4):ix + 5] = 0
    return out
