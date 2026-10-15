"""Catalog original bottom-screen UI textures for the PC interface adapter.

Reads the user's extracted ROM (`ROM/gameFiles/RomFS/us/info/*/info/00.bcres`)
and writes `build/native-ui/ui-sources.tsv`: one line per distinct encoded
texture, `fingerprint<TAB>role<TAB>name<TAB>source`. Only identities and names
are written; no image data. The runtime only relocates draws that sample a
catalogued texture, so an uncatalogued draw stays on the original screen.

Roles: portrait (FB_* dialogue art), insert (pictures the dialogue refers to:
CI_* gag/cutaway art, SP_* special pictures, BL_/BR_* boss and rival title
cards), hud (gameplay HUD atlases), menu (pause panel atlas, used only as
evidence of the pause menu), decor (known art that is intentionally not
relocated: backgrounds, chapter titles, results, loading).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools/formats/cgfx'), str(ROOT / 'tools/recomp')]
from cgfx_textures import textures  # noqa: E402
from export_texture_sources import fingerprint  # noqa: E402

# common/info atlases, by what their art is (see doc/PC_SINGLE_SCREEN_AUDIT.md)
COMMON = {
    'gc_00': 'hud',   # air special orb, heart counters, item/power art
    'gm_00': 'hud',   # digits, button glyphs
    'gm_02': 'hud',   # frames, palette tab, arrows
    'gm_03': 'hud',   # ring frame
    'ie_00': 'hud',   # item icons
    'mr': 'hud',      # Power Palette icons
    'tgt': 'hud',     # weapon icons, digits
    'imsg': 'hud',    # system icons
    'gm_01': 'menu',  # pause panel words: Resume, Retreat, Paused, Options...
    'gc_01': 'decor', # control diagrams (tutorial)
    'bg': 'decor',    # lower-screen background swirls
}
MULTI = 'hud'


def role_for(folder: str, name: str) -> str | None:
    if re.fullmatch(r'FB_[0-9]+', name):
        return 'portrait'
    if folder == 'common':
        return COMMON.get(name)
    if folder == 'multi':
        return MULTI
    if re.fullmatch(r'(CI|SP|BL|BR)_[0-9]+', name):
        return 'insert'
    return 'decor'


def build(romfs: Path, legacy_portraits: Path | None):
    rows: dict[str, tuple[str, str, str]] = {}
    for bcres in sorted((romfs / 'us/info').glob('*/info/00.bcres')):
        folder = bcres.parent.parent.name
        for name, width, height, fmt, mips, raw in textures(bcres.read_bytes()):
            role = role_for(folder, name)
            if role is None or raw is None:
                continue
            key = f'{fingerprint(raw):016X}'
            # a texture shared by several chapters keeps its first, most specific role
            rows.setdefault(key, (role, name, f'{folder}/info/00.bcres'))
    if legacy_portraits and legacy_portraits.is_file():
        for line in legacy_portraits.read_text().split():
            rows.setdefault(line.strip().upper(), ('portrait', '', 'portrait-hashes.txt'))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--romfs', type=Path, default=ROOT / 'ROM/gameFiles/RomFS')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/native-ui/ui-sources.tsv')
    parser.add_argument('--legacy-portraits', type=Path, default=ROOT / 'build/native-ui/dialogue-sources/portrait-hashes.txt')
    args = parser.parse_args()
    if not (args.romfs / 'us/info').is_dir():
        parser.error('extracted USA info resources are missing')
    rows = build(args.romfs, args.legacy_portraits)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# fingerprint\trole\tname\tsource (local ROM identities only; do not redistribute)']
    lines += [f'{k}\t{r}\t{n}\t{s}' for k, (r, n, s) in sorted(rows.items())]
    args.output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    counts = {}
    for r, _, _ in rows.values():
        counts[r] = counts.get(r, 0) + 1
    print(f'{len(rows)} original UI textures: ' + ', '.join(f'{v} {k}' for k, v in sorted(counts.items())))


if __name__ == '__main__':
    main()
