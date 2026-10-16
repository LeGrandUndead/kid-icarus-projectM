"""Build the PC HUD pack: the game's HUD atlases reconstructed for PC resolutions.

    python build_hud_pc_pack.py <sources folder> [--output build/texture-work/hud-pc]

<sources folder> holds the HUD atlases exported from your own ROM under their
runtime names (`256x256-<fingerprint>.png`). The pack is written next to a
manifest (`hud_asset_manifest.json`: every piece, the method chosen and its
fidelity numbers) and a validation report. Method details: hud_reconstruct.py
and doc/PC_HUD_ASSET_RECONSTRUCTION.md. The output is derived from the game:
it stays on your machine and is never committed.

The PC launcher uses build/texture-work/hud-pc automatically when it exists.
Needs: pip install potracer opencv-python pillow numpy
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import hud_reconstruct as hr
from export_texture_sources import fingerprint

ROOT = Path(__file__).resolve().parents[2]
GROUPS = json.loads(Path(__file__).with_name('hud_asset_groups.json').read_text())
GRID = {'mr': 32}   # the power-icon atlas is a grid of 32x32 cells


def validate(name, source, result, manifest):
    """Checks every generated atlas; returns a list of problems (empty = ok)."""
    problems = []
    src = np.asarray(source, dtype=np.float32) / 255
    out = np.asarray(result, dtype=np.float32) / 255
    if out.shape != (src.shape[0] * hr.FACTOR, src.shape[1] * hr.FACTOR, 4):
        problems.append(f'{name}: size {out.shape} is not {hr.FACTOR}x the source')
        return problems
    small = hr.shrink(out)
    # empty source pixels (several pixels away from any art) stay empty:
    # no background, no black box, transparent corners stay transparent
    import cv2
    empty = cv2.erode((src[..., 3] == 0).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    if empty.any() and small[..., 3][empty].max() > 0.02:
        problems.append(f'{name}: art appears where the source is empty')
    if (out[..., 3] > 0.99).mean() > (src[..., 3] > 0.99).mean() + 0.05:
        problems.append(f'{name}: more opaque than the source (background filled?)')
    # whole-atlas fidelity at source size
    pm = src.copy()
    pm[..., :3] *= pm[..., 3:4]
    error = float(np.abs(small - pm)[src[..., 3] > 0].mean())
    if error > 0.05:
        problems.append(f'{name}: differs from the source by {error:.3f} on average')
    for piece in manifest:
        last = piece['tried'][-1]
        if not last['passed'] and last['method'] != 'soft':
            problems.append(f"{name} {piece['rect']}: no method passed")
    return problems, round(error, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sources', type=Path)
    ap.add_argument('--output', type=Path, default=ROOT / 'build/texture-work/hud-pc')
    ap.add_argument('--replace', action='store_true', help='overwrite an existing output folder')
    args = ap.parse_args()

    jobs = []
    for atlas, hash_ in GROUPS['atlases'].items():
        path = args.sources / f'256x256-{hash_}.png'
        if not path.exists():
            print(f'missing {path.name} ({atlas}); skipped')
            continue
        image = Image.open(path).convert('RGBA')
        if f'{fingerprint(image.tobytes()):016X}' != hash_:
            sys.exit(f'{path.name}: pixels do not match the runtime fingerprint')
        jobs.append((atlas, path.name, image))
    if not jobs:
        sys.exit('no HUD atlas found')

    if args.output.exists():
        if not args.replace:
            sys.exit(f'{args.output} exists (use --replace)')
        shutil.rmtree(args.output)
    work = args.output.with_name(args.output.name + '.tmp')
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)

    manifest, report, failed = {}, {}, False
    for atlas, name, image in jobs:
        rgba = np.asarray(image, dtype=np.float32) / 255
        out, pieces = hr.reconstruct_atlas(rgba, grid=GRID.get(atlas))
        result = hr.to_image(out)
        # determinism: the same input gives the same pixels
        again = hr.to_image(hr.reconstruct_atlas(rgba, grid=GRID.get(atlas))[0])
        problems, error = validate(name, image, result, pieces)
        if hr.digest(again) != hr.digest(result):
            problems.append(f'{name}: output differs between two runs')
        result.save(work / name)
        counts = {m: sum(p['method'] == m for p in pieces) for m in hr.METHODS}
        manifest[atlas] = dict(file=name, factor=hr.FACTOR, sha256_16=hr.digest(result), pieces=pieces)
        report[atlas] = dict(methods=counts, mean_error=error, problems=problems, status='ok' if not problems else 'failed')
        failed |= bool(problems)
        print(f"{atlas}: {counts}, error {error}, {'ok' if not problems else problems}")

    (work / 'hud_asset_manifest.json').write_text(json.dumps(manifest, indent=1, default=float), encoding='utf-8')
    (work / 'validation.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    if failed:
        sys.exit(f'validation failed; nothing installed (see {work}/validation.json)')
    work.rename(args.output)
    print(f'PC HUD pack: {args.output}')


if __name__ == '__main__':
    main()
