"""Build the local HD HUD pack from the game's own HUD atlases.

Input: original-resolution atlases exported from the user's ROM under their
runtime names (`<w>x<h>-<fingerprint>.png`, as export_texture_sources.py
writes them). Output: 4x versions under the same names, for KIU_TEXTURE_PACK.

Method (no trained model, no new drawing): the game's HUD art is mostly
flat shapes - black ornaments, white masks the game tints, outlined digits.
Each atlas is enlarged with premultiplied bicubic interpolation; then the
soft ramps that enlargement leaves at shape edges are narrowed back to about
one output pixel, in the alpha channel and in black/white areas. Shaded
areas (orbs, wing gradients, button shading) keep the plain interpolation,
because only pixels whose whole source neighbourhood is flat black, flat
white or empty are sharpened. The pack stays on the user's machine; it is
derived from their ROM and is never committed.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from export_texture_sources import fingerprint

FACTOR = 4
# Known HUD atlases (runtime fingerprints of the USA release, October 15).
HUD = {
    'D61A7866121DF76F': 'gm_00 (health/score frames, digits, plates, buttons)',
    '2303D42752AFD91E': 'gm_02 (ornaments, trays, panels)',
    '1033DFD830565E9A': 'gc_00 (wings, orbs, medallions)',
    '260C607B8981C6F8': 'mr (power icons)',
}


def flatness(rgba):
    """1 where a source pixel and its 3x3 neighbours are flat black, flat
    white or empty; 0 near shading. Decides where edges may be sharpened."""
    a = rgba[..., 3]
    lum = rgba[..., :3].mean(-1)
    sat = np.ptp(rgba[..., :3], axis=-1)
    flat = (a < 0.02) | ((sat < 0.12) & ((lum < 0.16) | (lum > 0.86)))
    return cv2.erode(flat.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32)


def enlarge(image, factor=FACTOR):
    src = np.asarray(image.convert('RGBA'), dtype=np.float32) / 255.0
    pm = src.copy()
    pm[..., :3] *= pm[..., 3:4]
    big = cv2.resize(pm, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC).clip(0, 1)
    big = cv2.GaussianBlur(big, (0, 0), factor * 0.22)
    alpha = big[..., 3]
    rgb = np.divide(big[..., :3], alpha[..., None], out=np.zeros_like(big[..., :3]), where=alpha[..., None] > 1e-4)

    k = factor * 2.2
    ramp = lambda x: 1.0 / (1.0 + np.exp(-(x - 0.5) * k))
    flat = cv2.resize(flatness(src), None, fx=factor, fy=factor, interpolation=cv2.INTER_LINEAR)[..., None]

    # Alpha: sharpen everywhere except inside shaded, semi-transparent art.
    soft_alpha = (src[..., 3] > 0.02) & (src[..., 3] < 0.98)
    soft_alpha = cv2.resize(cv2.dilate(soft_alpha.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32),
                            None, fx=factor, fy=factor, interpolation=cv2.INTER_LINEAR)
    out_alpha = alpha * soft_alpha + ramp(alpha) * (1 - soft_alpha)

    # Colour: black/white transitions get the same narrowing; shading stays.
    lum = rgb.mean(-1, keepdims=True)
    snapped = np.repeat(ramp(lum), 3, -1)
    grey = (np.ptp(rgb, axis=-1, keepdims=True) < 0.12).astype(np.float32)
    w = flat * grey
    out_rgb = rgb * (1 - w) + snapped * w

    out = np.concatenate([out_rgb.clip(0, 1), out_alpha.clip(0, 1)[..., None]], -1)
    out[out[..., 3] <= 1e-3, :3] = 0
    return Image.fromarray(np.rint(out * 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sources', type=Path, help='folder with exported originals (runtime names)')
    ap.add_argument('output', type=Path, help='new folder for the pack (must not exist)')
    args = ap.parse_args()
    found = []
    for hash_, label in HUD.items():
        name = f'256x256-{hash_}.png'
        path = args.sources / name
        if not path.exists():
            print(f'missing {name} ({label}); skipped')
            continue
        image = Image.open(path).convert('RGBA')
        if f'{fingerprint(image.tobytes()):016X}' != hash_:
            raise SystemExit(f'{name}: pixels do not match the runtime fingerprint')
        found.append((name, label, image))
    if not found:
        raise SystemExit('no HUD atlas found')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, label, image in found:
        enlarge(image).save(args.output / name)
        manifest.append(dict(file=name, atlas=label, factor=FACTOR, method='bicubic + flat-edge narrowing'))
        print(f'{name}: {label}')
    (args.output / 'pack.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
