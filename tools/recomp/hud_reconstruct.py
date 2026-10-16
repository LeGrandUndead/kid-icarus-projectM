"""Hybrid reconstruction of the game's HUD atlases for PC resolutions.

Input: the HUD atlases exported from the user's own ROM (runtime names
`256x256-<fingerprint>.png`). Output: the same atlases at 4x, same layout
and UVs, for the local HUD pack (KIU_HUD_PACK). Nothing is drawn by hand;
every shape and colour comes from the source pixels. The generated images
stay on the user's machine (never commit them).

Each atlas is cut into pieces (connected shapes; the power-icon atlas into
its 32x32 cells). Each piece gets the method that suits it:

  flat    - pieces made of a few flat layers (black ornaments, white
            plates, white digits with black outlines, the score plate with
            its letters): each layer's coverage is enlarged and redrawn with
            the source's own colour and opacity. Opaque layers get their
            outline traced into smooth curves (potrace), so hard edges are
            clean at any size; semi-transparent layers (health bar frame,
            score tendrils) keep soft, smoothly enlarged edges, because
            tracing them hardens tapering tips and thickens lines.
  icon    - coloured art with hard outlines (power icons, wings): colours
            enlarged smoothly (Lanczos, with colours extended under the
            transparent border so no dark or white fringe appears), the
            outline traced like a flat layer. Detail inside is not invented.
  soft    - shaded or semi-transparent art (glows, gradients, soft tendrils,
            the orb): colour and opacity enlarged smoothly and separately,
            nothing sharpened.

Every result is checked against its source: shrunk back to the original size
it must match the source pixels and silhouette within set limits. A piece
that fails falls back to the next safer method (flat -> icon -> soft),
and the decision is written to the manifest.
"""
import hashlib
import json

import cv2
import numpy as np
import potrace
from PIL import Image, ImageChops, ImageDraw

FACTOR = 4      # output scale (the runtime accepts up to 1 megapixel per atlas)
SUPER = 4       # traced outlines are drawn this much larger again, then averaged
PAD = 2         # source pixels of context around each piece

# A piece passes when, shrunk back to the source size, it differs from the
# source by at most this much (mean, premultiplied RGBA, 0..1) and its
# silhouette overlaps the source silhouette at least this much (IoU).
# Plain enlargement shrinks back almost exactly by construction, so a sharper
# method is judged against it: about as close in colour, and a silhouette
# that still overlaps the source's (sharp edges move by a fraction of a
# source pixel, which costs small shapes like digits some overlap).
MAX_ERROR = {'flat': 0.01, 'paint': 0.01, 'ink': 0.01, 'icon': 0.01}
MIN_IOU = {'flat': 0.85, 'paint': 0.9, 'ink': 0.9, 'icon': 0.9}
MAX_INTERIOR = 0.015


# ---------------------------------------------------------------- pieces

def load(path):
    return np.asarray(Image.open(path).convert('RGBA'), dtype=np.float32) / 255.0


def find_pieces(rgba, grid=None):
    """Connected shapes (or grid cells), each with its bounding box and mask."""
    alpha = rgba[..., 3] > 0.02
    pieces = []
    if grid:
        h, w = alpha.shape
        for y in range(0, h, grid):
            for x in range(0, w, grid):
                mask = np.zeros_like(alpha)
                mask[y:y + grid, x:x + grid] = alpha[y:y + grid, x:x + grid]
                if mask.sum() >= 4:
                    pieces.append(dict(rect=[x, y, x + grid, y + grid], mask=mask))
        return pieces
    count, labels, stats, _ = cv2.connectedComponentsWithStats(alpha.astype(np.uint8), connectivity=8)
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area >= 4:
            pieces.append(dict(rect=[int(x), int(y), int(x + w), int(y + h)], mask=labels == i))
    return pieces


def features(rgba, mask):
    """Numbers used to choose a method (recorded in the manifest)."""
    a = rgba[..., 3][mask]
    rgb = rgba[..., :3][mask]
    lum = rgb.mean(-1)
    solid = a >= 0.5 * a.max()
    return dict(
        pixels=int(mask.sum()),
        saturation=round(float(np.ptp(rgb[solid], axis=-1).mean()), 3),
        alpha_max=round(float(a.max()), 3),
        mid_tones=round(float(((lum[solid] > 0.2) & (lum[solid] < 0.8)).mean()), 3),
    )


# ---------------------------------------------------------- flat layers

def flat_layers(rgba, mask):
    """Describe a piece as a stack of up to four flat layers, or None.

    A layer is a colour and an opacity that many pixels share exactly (the
    source has 16 opacity levels; edges use the levels in between). The
    stack is ordered from the outside in, by how far each layer's pixels lie
    from the outer edge (the score plate: dark plate, then the letters'
    black outline, then their white fill)."""
    a = np.round(rgba[..., 3] * 15) / 15
    lum = rgba[..., :3].mean(-1)
    inside = mask & (a > 0)
    total = inside.sum()
    levels, counts = np.unique(a[inside], return_counts=True)
    plateaus = [lv for lv, c in zip(levels, counts) if c >= 0.12 * total and lv >= 0.3]
    layers = []
    for p in plateaus:
        core = inside & (np.abs(a - p) < 0.01)
        l = lum[core]
        if l.max() - l.min() > 0.45:          # dark and light at this opacity
            split = (l.max() + l.min()) / 2
            groups = [core & (lum < split - 0.2), core & (lum > split + 0.2)]
        else:
            groups = [core]
        for g in groups:
            if g.sum() >= 0.04 * total:
                layers.append(dict(colour=np.median(rgba[..., :3][g], axis=0), alpha=float(p), core=g))
    if not 1 <= len(layers) <= 4:
        return None
    # outside in: the layer whose pixels lie nearest the outer edge first
    depth = cv2.distanceTransform(np.pad(mask, 1).astype(np.uint8), cv2.DIST_L2, 3)[1:-1, 1:-1]
    order = sorted(layers, key=lambda l: float(depth[l['core']].mean()))
    return order


def edge_softness(coverage):
    """Partly covered pixels per edge pixel of a layer: about 1 for a hard,
    anti-aliased edge; 1.5 and more for a soft edge (a shadow, a glow, a
    blurred or faint stroke)."""
    core = coverage >= 0.9
    partial = (coverage > 0.1) & (coverage < 0.9)
    edge = core & cv2.dilate((coverage < 0.9).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return float(partial.sum() / max(1, edge.sum()))


SOFT_EDGE = 1.5
GLOW_EDGE = 2.0
SOFT_ICON_EDGE = 0.35  # power icons: 0; wings and items with a soft dark rim: about 0.6


def layer_coverage(rgba, mask, layers):
    """How much of each source pixel each layer of the stack covers (0..1).

    Seen from the outside in, a pixel is a mix of two neighbouring levels of
    the stack (nothing -> layer 1 -> layer 2 ...). Each pixel is matched to
    the pair it is closest to (premultiplied colour and opacity); everything
    below that pair covers it fully."""
    px = np.concatenate([rgba[..., :3] * rgba[..., 3:4], rgba[..., 3:4]], -1)
    chain = [np.zeros(4, np.float32)] + [np.concatenate([l['colour'] * l['alpha'], [l['alpha']]]) for l in layers]
    best = np.full(mask.shape, np.inf, np.float32)
    level = np.zeros(mask.shape, np.int32)
    part = np.zeros(mask.shape, np.float32)
    for k in range(len(layers)):
        lo, hi = chain[k], chain[k + 1]
        d = hi - lo
        t = np.clip(((px - lo) * d).sum(-1) / max(float((d * d).sum()), 1e-6), 0, 1)
        residual = ((px - (lo + t[..., None] * d)) ** 2).sum(-1)
        better = residual < best
        best[better], level[better], part[better] = residual[better], k, t[better]
    cov = []
    for j in range(len(layers)):
        c = np.where(level > j, 1.0, np.where(level == j, part, 0.0))
        cov.append((c * mask).astype(np.float32))
    return cov


# ------------------------------------------------------------- outlines

def outline_points(curve, scale):
    pts = [(curve.start_point.x * scale, curve.start_point.y * scale)]
    for seg in curve.segments:
        start = pts[-1]
        if seg.is_corner:
            pts.append((seg.c.x * scale, seg.c.y * scale))
            pts.append((seg.end_point.x * scale, seg.end_point.y * scale))
        else:
            c1 = (seg.c1.x * scale, seg.c1.y * scale)
            c2 = (seg.c2.x * scale, seg.c2.y * scale)
            end = (seg.end_point.x * scale, seg.end_point.y * scale)
            for i in range(1, 9):
                t = i / 8
                u = 1 - t
                pts.append((u*u*u*start[0] + 3*u*u*t*c1[0] + 3*u*t*t*c2[0] + t*t*t*end[0],
                            u*u*u*start[1] + 3*u*u*t*c1[1] + 3*u*t*t*c2[1] + t*t*t*end[1]))
    return pts


def smooth_shape(coverage):
    """Coverage at source size -> anti-aliased shape at FACTOR times the size.

    The coverage is enlarged smoothly first (so thin strokes and partly
    covered edge pixels keep their place), cut at half, then its outline is
    traced into curves and drawn with anti-aliasing."""
    h, w = coverage.shape
    big = cv2.resize(coverage.astype(np.float32), (w * FACTOR, h * FACTOR), interpolation=cv2.INTER_CUBIC)
    bitmap = big > 0.5
    draw = SUPER
    canvas = Image.new('1', (w * FACTOR * draw, h * FACTOR * draw), 0)
    if bitmap.any():
        curves = potrace.Bitmap(~bitmap).trace(turdsize=0, alphamax=1.0, opticurve=True, opttolerance=0.2)
        for curve in curves:
            pts = outline_points(curve, draw)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            box = (max(0, int(min(xs)) - 1), max(0, int(min(ys)) - 1),
                   min(canvas.width, int(max(xs)) + 2), min(canvas.height, int(max(ys)) + 2))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            piece = Image.new('1', (box[2] - box[0], box[3] - box[1]), 0)
            ImageDraw.Draw(piece).polygon([(x - box[0], y - box[1]) for x, y in pts], fill=1)
            canvas.paste(ImageChops.logical_xor(canvas.crop(box), piece), box)  # holes flip
    return np.asarray(canvas.convert('L').resize((w * FACTOR, h * FACTOR), Image.BOX), dtype=np.float32) / 255.0


# --------------------------------------------------------------- methods

def bleed(rgba):
    """Extend colours under transparent pixels so enlargement adds no fringe."""
    rgb = rgba[..., :3].copy()
    known = rgba[..., 3] > 0.02
    if not known.any():
        return rgb
    for _ in range(8):
        if known.all():
            break
        grown = cv2.dilate(known.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        weights = cv2.blur(known.astype(np.float32), (3, 3))
        summed = cv2.blur(rgb * known[..., None], (3, 3))
        fill = grown & ~known
        rgb[fill] = summed[fill] / np.maximum(weights[fill][..., None], 1e-6)
        known = grown
    return rgb


def lanczos(channels):
    h, w = channels.shape[:2]
    return cv2.resize(channels, (w * FACTOR, h * FACTOR), interpolation=cv2.INTER_LANCZOS4)


def method_flat(crop, mask):
    layers = flat_layers(crop, mask)
    if layers is None:
        return None
    cov = layer_coverage(crop, mask, layers)
    out = np.zeros((crop.shape[0] * FACTOR, crop.shape[1] * FACTOR, 4), np.float32)
    for layer, c in zip(layers, cov):
        softness = edge_softness(c)
        shape = smooth_shape(c)
        if softness > GLOW_EDGE:
            # real soft art (shadows, glows): the outline is traced (no pixel
            # steps), then given back the soft falloff the source has, as
            # wide as measured on its edge. Edges up to GLOW_EDGE are only the
            # 3DS's anti-aliasing (health frame, score tendrils): kept crisp.
            width = max(0.0, softness - 1.0) * FACTOR * 0.4
            if width > 0.3:
                shape = cv2.GaussianBlur(shape, (0, 0), width)
        shape = shape * layer['alpha']
        # straight-alpha "over" of a flat colour
        a = shape + out[..., 3] * (1 - shape)
        rgb = (layer['colour'] * shape[..., None] + out[..., :3] * out[..., 3:4] * (1 - shape[..., None]))
        out[..., :3] = np.divide(rgb, a[..., None], out=np.zeros_like(rgb), where=a[..., None] > 1e-6)
        out[..., 3] = a
    return out


def palette(crop, mask, limit=8):
    """The few flat colours a coloured piece is painted with, or None."""
    solid = mask & (crop[..., 3] > 0.9)
    total = solid.sum()
    if total < 16:
        return None
    q = np.round(crop[..., :3][solid] * 15).astype(int)
    colours, counts = np.unique(q, axis=0, return_counts=True)
    order = np.argsort(-counts)
    chosen = []
    for i in order:
        if counts[i] < 0.02 * total:
            break
        c = colours[i] / 15.0
        if all(np.abs(c - d).max() > 0.12 for d in chosen):
            chosen.append(c)
        if len(chosen) == limit:
            break
    if len(chosen) < 2:
        return None
    return np.array(chosen, np.float32)


def method_paint(crop, mask):
    """Flat-colour art (power icons, simple coloured glyphs): each colour
    area is traced on its own and painted with the source's exact colour,
    so the symbol inside an icon gets clean edges too. Pixels on a border
    between two colours are split between them by how much of each they
    hold. Gradients and shading are refused (they are not a few colours)."""
    a = crop[..., 3] * mask
    top = a[mask].max() if mask.any() else 0
    if top <= 0 or edge_softness(np.clip(a / top, 0, 1)) > SOFT_ICON_EDGE:
        return None
    colours = palette(crop, mask)
    if colours is None:
        return None
    rgb = crop[..., :3]
    h, w = mask.shape
    best = np.full((h, w), np.inf, np.float32)
    first = np.zeros((h, w), np.int32)
    second = np.zeros((h, w), np.int32)
    part = np.zeros((h, w), np.float32)
    for i in range(len(colours)):
        for j in range(len(colours)):
            d = colours[j] - colours[i]
            if i == j:
                t = np.zeros((h, w), np.float32)
            elif i > j:
                continue
            else:
                t = np.clip(((rgb - colours[i]) * d).sum(-1) / float((d * d).sum()), 0, 1)
            residual = ((rgb - (colours[i] + t[..., None] * d)) ** 2).sum(-1)
            better = residual < best
            best[better], first[better], second[better], part[better] = residual[better], i, j, t[better]
    solid = mask & (crop[..., 3] > 0.5)
    if (best[solid] > 0.006).mean() > 0.05:
        return None          # shading or gradients: not a flat-colour piece
    weights = []
    for k in range(len(colours)):
        m = np.where(first == k, 1 - part, 0) + np.where(second == k, part, 0)
        m = np.where(first == second, (first == k).astype(np.float32), m)
        m = (m * (crop[..., 3] > 0.02)).astype(np.float32)
        # extend colour areas under the transparent border, so edges keep colour
        m = np.maximum(m, cv2.dilate(m, np.ones((3, 3), np.uint8)) * (crop[..., 3] <= 0.02))
        weights.append(smooth_shape(m) if m.any() else np.zeros((h * FACTOR, w * FACTOR), np.float32))
    weights = np.stack(weights, -1)
    total = weights.sum(-1, keepdims=True)
    fallback = np.clip(lanczos(bleed(crop)), 0, 1)
    colour = np.where(total > 1e-3, (weights @ colours) / np.maximum(total, 1e-3), fallback)
    alpha = smooth_shape(np.clip(a / top, 0, 1)) * top
    return np.concatenate([np.clip(colour, 0, 1), alpha[..., None]], -1)


def method_ink(crop, mask):
    """Cartoon art drawn with a dark neutral outline (wings, item icons,
    skulls): the dark ink lines are traced as one layer and drawn over the
    piece's colours, which are enlarged smoothly underneath (gradients and
    shading stay soft). The silhouette is traced too. Refused when the dark
    parts are coloured (shading, like the orb) or there is no ink."""
    a = crop[..., 3] * mask
    top = a[mask].max() if mask.any() else 0
    if top <= 0 or edge_softness(np.clip(a / top, 0, 1)) > 1.0:
        return None
    lum = crop[..., :3].mean(-1)
    sat = np.ptp(crop[..., :3], axis=-1)
    ink = np.clip((0.5 - lum) / 0.3, 0, 1) * (a > 0.02)
    dark = ink > 0.8
    if dark.sum() < 0.05 * mask.sum():
        return None
    if np.median(sat[dark]) > 0.12 or np.median(lum[dark]) > 0.3:
        return None
    colour_ink = np.median(crop[..., :3][dark], axis=0)
    body = crop.copy()
    body[..., 3] = np.where(ink > 0.5, 0, crop[..., 3])
    colour = np.clip(lanczos(bleed(body)), 0, 1)
    lines = smooth_shape(ink)[..., None]
    rgb = colour * (1 - lines) + colour_ink * lines
    alpha = smooth_shape(np.clip(a / top, 0, 1)) * top
    return np.concatenate([np.clip(rgb, 0, 1), alpha[..., None]], -1)


def method_icon(crop, mask):
    a = crop[..., 3] * mask
    top = a[mask].max()
    if top <= 0:
        return None
    # only art with hard outlines: a soft rim or glow (wings, orb, items
    # of gc_00) would turn into a hard dark outline if traced
    if edge_softness(np.clip(a / top, 0, 1)) > SOFT_ICON_EDGE:
        return None
    colour = np.clip(lanczos(bleed(crop)), 0, 1)
    alpha = smooth_shape(np.clip(a / top, 0, 1)) * top
    return np.concatenate([colour, alpha[..., None]], -1)


def method_soft(crop, mask):
    colour = np.clip(lanczos(bleed(crop)), 0, 1)
    alpha = np.clip(lanczos(crop[..., 3] * mask), 0, 1)
    return np.concatenate([colour, alpha[..., None]], -1)


METHODS = {'flat': method_flat, 'paint': method_paint, 'ink': method_ink, 'icon': method_icon, 'soft': method_soft}
FALLBACK = {'flat': 'paint', 'paint': 'ink', 'ink': 'icon', 'icon': 'soft'}


# ----------------------------------------------------------- validation

def shrink(img):
    h, w = img.shape[0] // FACTOR, img.shape[1] // FACTOR
    pm = img.copy()
    pm[..., :3] *= pm[..., 3:4]
    small = cv2.resize(pm, (w, h), interpolation=cv2.INTER_AREA)
    return small


def check(crop, mask, out):
    """Mean premultiplied difference and silhouette overlap, at source size."""
    src = crop.copy()
    src[..., :3] *= src[..., 3:4]
    small = shrink(out)
    region = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    error = float(np.abs(small - src)[region].mean())
    half = 0.5 * crop[..., 3][mask].max()
    a, b = src[..., 3] > half, small[..., 3] > half
    iou = float((a & b).sum() / max(1, (a | b).sum()))
    # away from the edges a faithful result reproduces the source exactly
    # (catches shading or thin grey detail flattened into one colour)
    inner = cv2.erode(mask.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    interior = float(np.abs(small - src)[inner].mean()) if inner.any() else 0.0
    return round(error, 4), round(iou, 4), round(interior, 4)


def choose(features_):
    """First choice of method from the piece's numbers."""
    if features_['saturation'] > 0.12:
        return 'paint'
    if features_['mid_tones'] > 0.35:
        return 'ink'
    return 'flat'


def reconstruct_piece(rgba, piece, forced=None):
    x0, y0, x1, y1 = piece['rect']
    h, w = rgba.shape[:2]
    X0, Y0, X1, Y1 = max(0, x0 - PAD), max(0, y0 - PAD), min(w, x1 + PAD), min(h, y1 + PAD)
    crop = rgba[Y0:Y1, X0:X1] * piece['mask'][Y0:Y1, X0:X1, None]
    mask = piece['mask'][Y0:Y1, X0:X1]
    info = dict(rect=piece['rect'], **features(rgba, piece['mask']))
    method = forced or choose(info)
    info['first_choice'] = method
    soft_error, soft_iou, soft_interior = check(crop, mask, method_soft(crop, mask))
    info['soft_error'], info['soft_iou'], info['soft_interior'] = soft_error, soft_iou, soft_interior
    while True:
        out = METHODS[method](crop, mask)
        if out is not None:
            error, iou, interior = check(crop, mask, out)
            # sharper methods must stay about as faithful as plain enlargement
            ok = method == 'soft' or (error <= max(MAX_ERROR[method], 1.25 * soft_error)
                                      and iou >= MIN_IOU[method]
                                      and interior <= max(MAX_INTERIOR, 1.3 * soft_interior))
            info.setdefault('tried', []).append(dict(method=method, error=error, iou=iou, interior=interior, passed=ok))
            if ok:
                break
        else:
            info.setdefault('tried', []).append(dict(method=method, passed=False, note='does not fit this method'))
        method = FALLBACK[method]
    info['method'] = method
    return (X0, Y0, X1, Y1), out, info


def reconstruct_atlas(rgba, grid=None, overrides=None):
    """Whole atlas at FACTOR times its size, and the per-piece manifest."""
    h, w = rgba.shape[:2]
    out = np.zeros((h * FACTOR, w * FACTOR, 4), np.float32)
    owner = np.zeros((h * FACTOR, w * FACTOR), bool)
    manifest = []
    for piece in find_pieces(rgba, grid):
        forced = (overrides or {}).get(','.join(map(str, piece['rect'])))
        (X0, Y0, X1, Y1), result, info = reconstruct_piece(rgba, piece, forced)
        # each piece writes only inside its own (slightly grown) area
        area = cv2.dilate(piece['mask'][Y0:Y1, X0:X1].astype(np.uint8), np.ones((3, 3), np.uint8))
        area = cv2.resize(area, (result.shape[1], result.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
        sl = (slice(Y0 * FACTOR, Y1 * FACTOR), slice(X0 * FACTOR, X1 * FACTOR))
        free = area & ~owner[sl]
        out[sl][free] = result[free]
        owner[sl] |= free
        manifest.append(info)
    out[out[..., 3] <= 1e-3, :3] = 0
    return out, manifest


def to_image(arr):
    return Image.fromarray(np.rint(np.clip(arr, 0, 1) * 255).astype(np.uint8))


def digest(image):
    return hashlib.sha256(image.tobytes()).hexdigest()[:16]
