"""Export selected local captured RGBA assets under runtime replacement names.

This converts the captured format; it does not upscale or claim HD detail.
Explicit IDs are required because captures also contain changing framebuffers.
"""
from pathlib import Path
import argparse
import csv
import json
from PIL import Image


def fingerprint(data: bytes) -> int:
    mask = (1 << 64) - 1
    def step(h, word):
        return ((((h << 5) | (h >> 59)) & mask) ^ word) * 0x517CC1B727220A95 & mask
    lanes = [len(data), 1, 2, 3]
    end = len(data) // 32 * 32
    for offset in range(0, end, 32):
        for lane in range(4):
            at = offset + lane * 8
            lanes[lane] = step(lanes[lane], int.from_bytes(data[at:at+8], 'little'))
    value = 0
    for lane in lanes:
        value = step(value, lane)
    for byte in data[end:]:
        value = step(value, byte)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ids', required=True, help='comma-separated reviewed static texture IDs')
    args = parser.parse_args()
    wanted = {int(value) for value in args.ids.split(',')}
    with (args.capture / 'textures.csv').open(newline='') as stream:
        rows = {int(row['id']): row for row in csv.DictReader(stream)}
    if not wanted.issubset(rows):
        parser.error('one or more texture IDs do not exist')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for number in sorted(wanted):
        row = rows[number]
        w, h = int(row['width']), int(row['height'])
        rgba = (args.capture / f'texture-{number:04}.rgba').read_bytes()
        if len(rgba) != w * h * 4:
            raise ValueError(f'texture {number}: unexpected RGBA length')
        name = f'{w}x{h}-{fingerprint(rgba):016X}.png'
        Image.frombytes('RGBA', (w, h), rgba).save(args.output / name)
        manifest.append(dict(id=number, file=name, width=w, height=h, source=str(args.capture.resolve())))
    (args.output / 'sources.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Exported {len(manifest)} original-resolution source assets. No HD replacements generated.')


if __name__ == '__main__':
    main()
