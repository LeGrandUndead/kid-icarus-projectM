"""Build an opt-in, non-AI reconstruction pack from reviewed local originals.

This improves enlargement, not source detail. No downloaded or generated art.
Uses premultiplied-alpha Lanczos to avoid dark fringes around original sprites.
Only assets explicitly exported into sources.json are accepted; framebuffer
captures must never be passed here as static replacements.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from export_texture_sources import fingerprint


def reconstruct(image, factor):
    source = np.asarray(image.convert('RGBA'), dtype=np.float32) / 255.0
    target = (image.width * factor, image.height * factor)
    alpha = source[:, :, 3]
    premultiplied = source[:, :, :3] * alpha[:, :, None]

    def enlarge(channel):
        return np.asarray(Image.fromarray(channel).resize(target, Image.Resampling.LANCZOS))

    out_alpha = np.clip(enlarge(alpha), 0.0, 1.0)
    rgb = np.stack([enlarge(premultiplied[:, :, c]) for c in range(3)], axis=2)
    # Bound ringing before unpremultiplication; transparent texels cannot add
    # colored fringes. Keep straight-alpha PNGs for the runtime's upload path.
    rgb = np.clip(rgb, 0.0, out_alpha[:, :, None])
    np.divide(rgb, out_alpha[:, :, None], out=rgb, where=out_alpha[:, :, None] > 1e-6)
    rgb[out_alpha <= 1e-6] = 0
    result = np.concatenate([rgb, out_alpha[:, :, None]], axis=2)
    return Image.fromarray(np.rint(result * 255).astype(np.uint8))


def build(source, output, factor):
    rows = json.loads((source / 'sources.json').read_text(encoding='utf-8'))
    validated = []
    for row in rows:
        name = row['file']
        if Path(name).name != name:
            raise ValueError('source filenames must not contain paths')
        with Image.open(source / name) as asset:
            image = asset.convert('RGBA')
        w, h = image.size
        expected = f'{w}x{h}-{fingerprint(image.tobytes()):016X}.png'
        if name != expected or (w, h) != (row['width'], row['height']):
            raise ValueError(f'original identity or dimensions changed: {name}')
        if w * h * factor * factor > 1024 * 1024:
            raise ValueError(f'{name}: exceeds runtime upload limit')
        validated.append((row, image))
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for row, image in validated:
        result = reconstruct(image, factor)
        path = output / row['file']
        result.save(path)
        manifest.append(dict(source=row, output_size=list(result.size),
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (output / 'pack.json').write_text(json.dumps(dict(
        method='premultiplied-alpha Lanczos; no AI; no new source detail',
        factor=factor, assets=manifest), indent=2), encoding='utf-8')
    print(f'Built {len(manifest)} faithful reconstruction textures in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--factor', type=int, choices=(2, 4, 8), default=4)
    args = parser.parse_args()
    build(args.sources, args.output, args.factor)
