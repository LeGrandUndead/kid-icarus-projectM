"""Traced HD HUD pack: the game's own flat HUD shapes as smooth outlines.

Like build_hud_hd_pack.py (same input and output names, for KIU_HUD_PACK),
but the edges of flat shapes come from outlines traced around the original
pixels (potrace: the pixel steps of a shape become straight lines and
curves), drawn again at 4x. Nothing is drawn by hand; every shape is the
game's own, from the user's ROM, and the pack stays on the user's machine.

Per atlas, three masks are traced: the shape itself (alpha), its dark parts
(black ornaments, outlines of digits) and, for colourful icons, nothing more:
their colours keep the plain enlargement. Shaded areas (gradients, soft
glows) are never replaced, only edges between flat areas.

    python trace_hud_pack.py <sources folder> <new output folder>

Writes gm_00 and gm_02; copy the other two from the plain HD pack.

Needs: pip install potracer opencv-python pillow numpy
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import potrace
from PIL import Image, ImageChops, ImageDraw

from export_texture_sources import fingerprint
from build_hud_hd_pack import HUD

# Only the flat black/white atlases are traced. The colourful ones (power
# icons, wings, orbs) lost their small transparent corners when traced; the
# plain HD pack (build_hud_hd_pack.py) stays best for them.
TRACED = {'D61A7866121DF76F', '2303D42752AFD91E'}

FACTOR = 4          # output size: 4x (the runtime accepts up to 1 megapixel)
SUPER = 4           # outlines are drawn 4x larger again, then averaged (smooth edges)


def outline_points(curve, scale):
    """One traced outline as a list of points, curves cut into short lines."""
    points = [(curve.start_point.x * scale, curve.start_point.y * scale)]
    for segment in curve.segments:
        start = points[-1]
        if segment.is_corner:
            points.append((segment.c.x * scale, segment.c.y * scale))
            points.append((segment.end_point.x * scale, segment.end_point.y * scale))
        else:
            c1 = (segment.c1.x * scale, segment.c1.y * scale)
            c2 = (segment.c2.x * scale, segment.c2.y * scale)
            end = (segment.end_point.x * scale, segment.end_point.y * scale)
            for i in range(1, 9):
                t = i / 8
                u = 1 - t
                x = u*u*u*start[0] + 3*u*u*t*c1[0] + 3*u*t*t*c2[0] + t*t*t*end[0]
                y = u*u*u*start[1] + 3*u*u*t*c1[1] + 3*u*t*t*c2[1] + t*t*t*end[1]
                points.append((x, y))
    return points


def trace(mask):
    """Coverage (0..1) of a traced binary mask, at FACTOR times its size."""
    h, w = mask.shape
    big = FACTOR * SUPER
    canvas = Image.new('1', (w * big, h * big), 0)
    if mask.any():
        # potracer traces the zero pixels, so it is given the inverse
        curves = potrace.Bitmap(~mask).trace(turdsize=0, alphamax=1.0, opticurve=True, opttolerance=0.2)
        for curve in curves:
            points = outline_points(curve, big)
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            box = (max(0, int(min(xs)) - 1), max(0, int(min(ys)) - 1),
                   min(w * big, int(max(xs)) + 2), min(h * big, int(max(ys)) + 2))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            # outlines inside outlines are holes: each one flips what it covers
            piece = Image.new('1', (box[2] - box[0], box[3] - box[1]), 0)
            ImageDraw.Draw(piece).polygon([(x - box[0], y - box[1]) for x, y in points], fill=1)
            canvas.paste(ImageChops.logical_xor(canvas.crop(box), piece), box)
    small = canvas.convert('L').resize((w * FACTOR, h * FACTOR), Image.BOX)
    return np.asarray(small, dtype=np.float32) / 255.0


def flatness(rgba):
    """1 where a source pixel and its neighbours are empty, or fully opaque
    pure black or white. Soft, semi-transparent art (the health bar frame,
    the score plate's tendrils) and shading are left alone."""
    a = rgba[..., 3]
    lum = rgba[..., :3].mean(-1)
    sat = np.ptp(rgba[..., :3], axis=-1)
    solid = (a > 0.98) & (sat < 0.12) & ((lum < 0.16) | (lum > 0.86))
    flat = (a < 0.02) | solid
    return cv2.erode(flat.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32)


def enlarge(image):
    src = np.asarray(image.convert('RGBA'), dtype=np.float32) / 255.0
    # plain enlargement first (premultiplied, so empty pixels add no colour)
    pm = src.copy()
    pm[..., :3] *= pm[..., 3:4]
    big = cv2.resize(pm, None, fx=FACTOR, fy=FACTOR, interpolation=cv2.INTER_CUBIC).clip(0, 1)
    alpha = big[..., 3]
    rgb = np.divide(big[..., :3], alpha[..., None], out=np.zeros_like(big[..., :3]), where=alpha[..., None] > 1e-4)

    # where the original is flat (solid, empty, pure black or white), the
    # traced outlines decide; elsewhere the plain enlargement stays
    flat = cv2.resize(flatness(src), None, fx=FACTOR, fy=FACTOR, interpolation=cv2.INTER_LINEAR)

    shape = trace(src[..., 3] > 0.5)
    lum = src[..., :3].mean(-1)
    dark = trace((src[..., 3] > 0.5) & (lum < 0.5))

    out_alpha = alpha * (1 - flat) + shape * flat
    grey = (np.ptp(rgb, axis=-1) < 0.12).astype(np.float32)
    w = (flat * grey)[..., None]
    # the colours on each side of an edge, taken from the nearby pixels
    window = np.ones((FACTOR * 2 + 1, FACTOR * 2 + 1), np.uint8)
    light = cv2.dilate(rgb, window)
    dark_rgb = cv2.erode(rgb, window)
    traced_rgb = light * (1 - dark[..., None]) + dark_rgb * dark[..., None]
    out_rgb = rgb * (1 - w) + traced_rgb * w

    out = np.concatenate([out_rgb.clip(0, 1), out_alpha.clip(0, 1)[..., None]], -1)
    out[out[..., 3] <= 1e-3, :3] = 0
    return Image.fromarray(np.rint(out * 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sources', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    found = []
    for hash_, label in HUD.items():
        if hash_ not in TRACED:
            continue
        path = args.sources / f'256x256-{hash_}.png'
        if not path.exists():
            print(f'missing {path.name} ({label}); skipped')
            continue
        image = Image.open(path).convert('RGBA')
        if f'{fingerprint(image.tobytes()):016X}' != hash_:
            raise SystemExit(f'{path.name}: pixels do not match the runtime fingerprint')
        found.append((path.name, label, image))
    if not found:
        raise SystemExit('no HUD atlas found')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, label, image in found:
        enlarge(image).save(args.output / name)
        manifest.append(dict(file=name, atlas=label, factor=FACTOR, method='traced outlines for flat areas'))
        print(f'{name}: {label}')
    (args.output / 'pack.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
