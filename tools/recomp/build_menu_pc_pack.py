"""Build the PC menu art pack: the menu screens' textures rebuilt from your ROM.

    python tools/recomp/build_menu_pc_pack.py [--romfs ROM/gameFiles/RomFS] [--output build/texture-work/menu-pc]

Every texture of every menu screen (`us/menu/*/menu/bind.arc`) and the
system icons (`imsg`) is read from your extracted ROM and:

- art with a shape (transparent edges, or a luminance mask the game uses as
  one: the save select's speech bubble, the cloud buttons, "How to Play") is
  reconstructed at 4x (2x for the large atlases) with the HUD method
  (hud_reconstruct.py): smooth traced outlines, colours and shading only
  enlarged, every piece checked against its source;
- opaque painted art (backgrounds, the books' covers) is left as it is;
- 3DS-only art is removed and a few things are restyled for one PC screen
  (menu_pc_changes.json: the battery and wireless icons, the HOME button,
  the save select's lower-screen backdrop).

Files are named like the runtime looks them up, `<w>x<h>-<fingerprint>.png`,
the fingerprint being the one of the texture's encoded ROM bytes (the UI
catalog's identity). The launcher uses build/texture-work/menu-pc when it
exists (--menu-art original to compare). The output is derived from the
game: it stays on your machine and is never committed.

Needs: pip install potracer opencv-python pillow numpy
"""
import argparse
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools/formats/cgfx'), str(ROOT / 'tools/formats/darc'), str(Path(__file__).parent)]
from cgfx_textures import textures  # noqa: E402
from darc_tool_fixed import parse_darc  # noqa: E402
from export_texture_sources import fingerprint  # noqa: E402
import pica_texture  # noqa: E402

CHANGES = json.loads(Path(__file__).with_name('menu_pc_changes.json').read_text(encoding='utf-8'))
MAX_PIXELS = 1024 * 1024   # the runtime's limit per replacement


def cgfx_in(data, prefix):
    """(label, cgfx bytes) of every CGFX in a DARC archive, nested ones too."""
    for entry in parse_darc(data).entries:
        if entry.is_dir or entry.data_offset is None:
            continue
        blob = data[entry.data_offset:entry.data_offset + entry.size]
        if blob[:4] == b'darc':
            yield from cgfx_in(blob, prefix)
        elif blob[:4] == b'CGFX':
            yield prefix, blob


def sources(romfs):
    """(label, name, width, height, format, raw) of every texture to consider."""
    for arc in sorted((romfs / 'us/menu').glob('*/menu/bind.arc')):
        for label, blob in cgfx_in(arc.read_bytes(), f'menu{arc.parent.parent.name}'):
            for name, w, h, fmt, mips, raw in textures(blob):
                yield label, name, w, h, fmt, mips, raw
    # the system icons (battery, wireless...) are resident, and copied into
    # every chapter's interface
    resident = romfs / 'us/00.arc'
    if resident.is_file():
        for label, blob in cgfx_in(resident.read_bytes(), 'resident'):
            for item in textures(blob):
                if item[0] == 'imsg':
                    yield (label,) + item
    for bcres in sorted((romfs / 'us/info').glob('*/info/00.bcres')):
        for item in textures(bcres.read_bytes()):
            if item[0] == 'imsg':
                yield ('info',) + item


def kind(rgba):
    """'shape' (has transparent edges), 'mask' (grey art the game uses as a
    coverage mask, white on black) or 'painted' (opaque colour art)."""
    if (rgba[..., 3] < 250).any():
        return 'shape'
    rgb = rgba[..., :3].astype(np.int16)
    grey = np.abs(rgb[..., 0] - rgb[..., 1]).max() <= 2 and np.abs(rgb[..., 1] - rgb[..., 2]).max() <= 2
    if grey and (rgb[..., 0] < 16).mean() > 0.05:
        return 'mask'
    return 'painted'


def change_for(label, name):
    return [c for c in CHANGES['changes'] if c['texture'] in (name, f'{label}/{name}')]


def apply_changes(image, changes, factor):
    """menu_pc_changes.json edits, at the output's scale."""
    out = np.asarray(image).copy()
    for change in changes:
        for x0, y0, x1, y1 in change.get('clear', []):
            out[y0 * factor:y1 * factor, x0 * factor:x1 * factor] = 0
        if 'tint' in change:
            # a new colour for a painted backdrop, keeping its own shading
            r, g, b = change['tint']
            light = out[..., :3].astype(np.float32).mean(axis=2, keepdims=True) / 255
            light = 0.82 + 0.18 * (light - light.mean()) / max(1e-3, light.std() * 3)
            out[..., :3] = np.clip(np.array([r, g, b], np.float32) * light, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def build_one(job):
    label, name, w, h, fmt, raw, changes = job
    import hud_reconstruct as hr
    rgba = pica_texture.decode(raw, w, h, fmt)
    what = kind(rgba)
    factor = 4 if w * h * 16 <= MAX_PIXELS else 2
    if w * h * factor * factor > MAX_PIXELS:
        return dict(label=label, name=name, skipped='too large')
    if what == 'painted' and not changes:
        return dict(label=label, name=name, kind=what, skipped='painted art is kept as it is')
    info = dict(label=label, name=name, kind=what, factor=factor)
    if what == 'painted':
        out = Image.fromarray(rgba).resize((w * factor, h * factor), Image.LANCZOS)
        info['method'] = 'enlarged'
    else:
        src = rgba.astype(np.float32) / 255
        if what == 'mask':
            src = np.dstack([np.ones((h, w, 3), np.float32), src[..., :1]])
        result, pieces = hr.reconstruct_atlas(src)
        if what == 'mask':
            cover = np.clip(result[..., 3:4], 0, 1)
            result = np.dstack([cover, cover, cover, np.ones_like(cover)])
        out = hr.to_image(result)
        if factor != hr.FACTOR:
            out = out.resize((w * factor, h * factor), Image.LANCZOS)
        info['methods'] = {m: sum(p['method'] == m for p in pieces) for m in hr.METHODS}
        # shrunk back, it must still be the source (premultiplied, 0..1)
        small = np.asarray(out.resize((w, h), Image.BOX), np.float32) / 255
        ref = rgba.astype(np.float32) / 255
        small[..., :3] *= small[..., 3:4]
        ref[..., :3] *= ref[..., 3:4]
        info['error'] = round(float(np.abs(small - ref).mean()), 4)
        if info['error'] > 0.04:
            return dict(info, skipped='differs from the source')
    if changes:
        out = apply_changes(out, changes, factor)
        info['changes'] = [c['why'] for c in changes]
    info['png'] = out
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--romfs', type=Path, default=ROOT / 'ROM/gameFiles/RomFS')
    ap.add_argument('--output', type=Path, default=ROOT / 'build/texture-work/menu-pc')
    ap.add_argument('--only', help='only menus whose label contains this (e.g. menu020), for trials')
    args = ap.parse_args()
    if not (args.romfs / 'us/menu').is_dir():
        sys.exit(f'extracted menus missing under {args.romfs}')

    jobs, seen = [], set()
    for label, name, w, h, fmt, mips, raw in sources(args.romfs):
        if raw is None or (args.only and args.only not in label):
            continue
        key = f'{w}x{h}-{fingerprint(raw):016X}.png'
        if key in seen or fmt not in pica_texture.BITS or len(raw) < pica_texture.size(w, h, fmt):
            continue
        seen.add(key)
        jobs.append((key, (label, name, w, h, fmt, bytes(raw[:pica_texture.size(w, h, fmt)]), change_for(label, name))))
    print(f'{len(jobs)} distinct menu textures')

    work = args.output.with_name(args.output.name + '.tmp')
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    manifest, written = {}, 0
    with ProcessPoolExecutor() as pool:
        for (key, _), info in zip(jobs, pool.map(build_one, [j for _, j in jobs], chunksize=4)):
            png = info.pop('png', None)
            if png is not None:
                png.save(work / key, optimize=False, compress_level=6)
                written += 1
            manifest[key] = info
    (work / 'menu_manifest.json').write_text(json.dumps(manifest, indent=1, default=float), encoding='utf-8')
    changed = [k for k, v in manifest.items() if v.get('changes')]
    print(f'{written} textures written, {len(changed)} changed for PC: ' +
          ', '.join(f"{manifest[k]['name']}" for k in changed))
    if args.output.exists():
        # the previous pack is kept in archive/, never deleted
        stamp = __import__('datetime').datetime.now().strftime('%Y-%m-%d-%H%M%S')
        archive = ROOT / 'archive' / f'{stamp}-menu-pc-before'
        archive.parent.mkdir(exist_ok=True)
        args.output.rename(archive)
    work.rename(args.output)
    print(f'PC menu pack: {args.output}')


if __name__ == '__main__':
    main()
