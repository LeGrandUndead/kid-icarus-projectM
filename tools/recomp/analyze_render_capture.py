"""Summarize a local render capture and make an indexed texture contact sheet."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    root = args.capture.resolve()
    with (root / 'draw-states.csv').open() as f:
        states = list(csv.DictReader(f))
    with (root / 'textures.csv').open() as f:
        textures = list(csv.DictReader(f))
    procedural = [s['id'] for s in states if s['proctex_enabled'] == '1']
    report = dict(unique_fragment_states=len(states), procedural_enabled_states=procedural,
                  captured_textures=len(textures), formats=dict(Counter(t['format'] for t in textures)),
                  limits='2048 fragment states, 256 texture versions, 128 MiB texture output',
                  note='Enabled does not prove a combiner uses Texture3. Render-target-backed textures are not dumped. '
                       'RGB previews omit alpha; .rgba files retain it. Counts are unique states, not draw frequency.')
    (root / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    for page in range((len(textures) + 47) // 48):
        rows = textures[page * 48:(page + 1) * 48]
        sheet = Image.new('RGB', (960, ((len(rows) + 5) // 6) * 148), '#242424')
        draw = ImageDraw.Draw(sheet)
        for i, row in enumerate(rows):
            path = root / f"texture-{int(row['id']):04}.ppm"
            with Image.open(path) as im:
                im.thumbnail((154, 116))
                x, y = (i % 6) * 160, (i // 6) * 148
                sheet.paste(im, (x, y))
            draw.text((x + 2, y + 118), f"{row['id']}: {row['format']}", fill='white')
            draw.text((x + 2, y + 132), f"{row['width']}x{row['height']}", fill='white')
        sheet.save(root / f'textures-{page + 1}.png')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
