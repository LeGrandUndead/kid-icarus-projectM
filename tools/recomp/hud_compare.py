"""Comparison sheets for the HUD reconstruction (local only: they show game art).

    python hud_compare.py <sources> <out folder> Label=<pack folder> ...

For every group in hud_asset_groups.json: the original at 1:1, then each
version at about its 1080p size (4.5 screen pixels per atlas pixel for the
top HUD), on a checkerboard, a dark and a light background.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCALE_1080 = 4.5
GROUPS = json.loads((Path(__file__).with_name('hud_asset_groups.json')).read_text())


def backgrounds(size):
    w, h = size
    checker = Image.new('RGBA', size, (200, 200, 200, 255))
    d = ImageDraw.Draw(checker)
    for y in range(0, h, 12):
        for x in range(0, w, 12):
            if (x // 12 + y // 12) % 2:
                d.rectangle((x, y, x + 11, y + 11), fill=(150, 150, 150, 255))
    return [checker, Image.new('RGBA', size, (24, 24, 34, 255)), Image.new('RGBA', size, (235, 232, 222, 255))]


def font(size):
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf', size)
    except OSError:
        return ImageFont.load_default()


def main():
    sources, out = Path(sys.argv[1]), Path(sys.argv[2])
    packs = [arg.split('=', 1) for arg in sys.argv[3:]]
    out.mkdir(parents=True, exist_ok=True)
    for group, regions in GROUPS['groups'].items():
        tiles = []
        for atlas, rect in regions:
            name = f"256x256-{GROUPS['atlases'][atlas]}.png"
            original = Image.open(sources / name).convert('RGBA').crop(rect)
            w, h = original.size
            target = (round(w * SCALE_1080), round(h * SCALE_1080))
            column = [('original 1:1', original), ('original at 1080p', original.resize(target, Image.BILINEAR))]
            for label, folder in packs:
                path = Path(folder) / name
                if not path.exists():
                    continue
                big = Image.open(path).convert('RGBA')
                f = big.width // 256
                column.append((label, big.crop([v * f for v in rect]).resize(target, Image.LANCZOS)))
            tiles.append(column)
        width = max(sum(im.width for _, im in col) + 20 * len(col) for col in tiles) + 40
        height = sum(max(im.height for _, im in col) * 3 + 90 for col in tiles) + 60
        sheet = Image.new('RGBA', (width, height), (12, 12, 16, 255))
        d = ImageDraw.Draw(sheet)
        d.text((20, 15), group, font=font(28), fill='white')
        y = 60
        for col in tiles:
            row_h = max(im.height for _, im in col)
            x = 20
            for label, im in col:
                d.text((x, y), label, font=font(16), fill=(220, 220, 220))
                for i, bg in enumerate(backgrounds(im.size)):
                    tile = bg.copy()
                    tile.alpha_composite(im)
                    sheet.paste(tile, (x, y + 24 + i * (row_h + 8)))
                x += im.width + 20
            y += row_h * 3 + 90
        sheet.convert('RGB').save(out / f"{group.replace(' ', '-')}.png")
        print(out / f"{group.replace(' ', '-')}.png")


if __name__ == '__main__':
    main()
