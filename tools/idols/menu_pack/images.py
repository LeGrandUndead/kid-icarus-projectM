"""Small picture helpers, on PIL images (RGBA unless said) and numpy arrays."""
import numpy as np
from PIL import Image, ImageFilter


def fit(img, w=None, h=None):
    """Resized to width w or height h (the other follows), or to both."""
    if w and not h: h = img.height * w / img.width
    if h and not w: w = img.width * h / img.height
    return img.resize((max(1, int(w)), max(1, int(h))), Image.LANCZOS)


def scaled(img, sx, sy=None):
    """Resized by a factor (bilinear)."""
    sy = sx if sy is None else sy
    return img.resize((max(1, int(img.width * sx)), max(1, int(img.height * sy))), Image.BILINEAR)


def faded(img, a):
    """With its alpha multiplied by a (0..1)."""
    a = max(0.0, min(1.0, a))
    if a >= 0.999: return img
    o = img.copy(); o.putalpha(o.getchannel('A').point(lambda q: int(q * a))); return o


def mask(img, color=(0, 0, 0), alpha=1.0):
    """A white-on-black mask picture as `color`, its luminance as coverage
    (much of the game's menu art is drawn this way and tinted)."""
    a = np.asarray(img).astype(float)
    L = a[:, :, :3].mean(axis=2) * (a[:, :, 3] / 255.0)
    out = np.zeros(a.shape, np.uint8); out[:, :, 0], out[:, :, 1], out[:, :, 2] = color
    out[:, :, 3] = np.clip(L * alpha, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def mix(a, b, k):
    """Colour a, k of the way to colour b (0..255 tuples)."""
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def mix_white(c, k):
    """Colour c (0..255) as 0..1, k of the way from white."""
    return tuple(1 - (1 - x / 255) * k for x in c)


def only_largest(img):
    """Only the biggest shape of a crop (the game's sheets pack other sprites
    right next to each other; their edges come along with a crop box)."""
    from scipy import ndimage
    a = np.asarray(img).copy()
    solid = a[:, :, 3] > 20
    labels, n = ndimage.label(ndimage.binary_dilation(solid, iterations=2))
    if n > 1:
        sizes = ndimage.sum(solid, labels, range(1, n + 1))
        a[labels != 1 + int(np.argmax(sizes))] = 0
    out = Image.fromarray(a)
    return out.crop(out.getchannel('A').getbbox())


def top_piece(img):
    """Only the shape(s) touching the top edge (a crop box would slice
    through a sheet's neighbouring ornaments)."""
    from scipy.ndimage import label
    a = np.asarray(img.convert('L'), np.float32) > 60; lab, n = label(a)
    keep = [i for i in range(1, n + 1) if np.nonzero(lab == i)[0].min() < 4]
    m = np.isin(lab, keep); out = img.convert('RGB').copy(); out.putalpha(Image.fromarray((m * 255).astype(np.uint8)))
    return out.crop(out.getchannel('A').getbbox())


def soft_glow(img, color, strength=0.35, radius=18):
    """A soft light around a rendered character (the 3DS's low resolution
    softens everything; at 1080p a little glow brings that back)."""
    a = img.getchannel('A').filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * strength))
    g = Image.new('RGBA', img.size, color + (0,)); g.putalpha(a); return g


def mirrored(a):
    """A quarter of a symmetric particle image completed (the game mirrors
    them on both axes)."""
    top = np.concatenate([a[:, ::-1], a], 1)
    return np.concatenate([top[::-1], top], 0)


def white_shape(a):
    """A greyscale particle image as a white shape, coverage = luminance x
    alpha (the game draws these additively; the game tints them)."""
    a = np.asarray(a, np.float32); cover = a[:, :, :3].mean(2) * a[:, :, 3] / 255
    out = np.zeros(a.shape[:2] + (4,), np.uint8); out[..., :3] = 255; out[..., 3] = np.clip(cover, 0, 255)
    return Image.fromarray(out)


def light_on_black(img):
    """An added light layer as the colour it adds (RGB on black)."""
    return Image.alpha_composite(Image.new('RGBA', img.size, (0, 0, 0, 255)), img).convert('RGB')


def add(page, lay):
    """`lay` added onto `page` (light)."""
    from PIL import ImageChops
    rgb = Image.alpha_composite(Image.new('RGBA', page.size, (0, 0, 0, 255)), lay).convert('RGB')
    return ImageChops.add(page.convert('RGB'), rgb).convert('RGBA')


def oklch_to_rgb(L, C, h):
    """OKLCH (arrays) to sRGB 0..1 (clipped)."""
    a = C * np.cos(np.radians(h)); b = C * np.sin(np.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b; m_ = L - 0.1055613458 * a - 0.0638541728 * b; s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s3 = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s3
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s3
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s3
    lin = np.clip(np.stack([r, g, bb], -1), 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
