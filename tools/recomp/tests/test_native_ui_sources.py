"""Catalog generator checks on a synthetic CGFX file; no ROM data involved."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools/formats/cgfx'), str(ROOT / 'tools/recomp')]
spec = importlib.util.spec_from_file_location('prep', Path(__file__).parents[1] / 'prepare_native_ui_sources.py')
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)
from cgfx_textures import textures  # noqa: E402
from export_texture_sources import fingerprint  # noqa: E402


def synthetic_cgfx(entries):
    """CGFX with a texture dictionary of (name, width, height, fmt, raw)."""
    data = 0x14
    dict_at = data + 8 + 16 * 8
    nodes = dict_at + 0x1C
    objs = nodes + 16 * len(entries)
    out = bytearray(objs + 0x50 * len(entries))
    strings, blobs = bytearray(), bytearray()
    tail = len(out)
    names_at, blobs_at = [], []
    for name, *_ in entries:
        names_at.append(tail + len(strings)); strings += name.encode() + b'\0'
    tail += len(strings)
    for *_, raw in entries:
        blobs_at.append(tail + len(blobs)); blobs += raw
    out += strings + blobs
    out[0:4] = b'CGFX'; struct.pack_into('<HH', out, 4, 0xFEFF, 0x14)
    out[data:data + 4] = b'DATA'
    struct.pack_into('<II', out, data + 16, len(entries), dict_at - (data + 20))
    out[dict_at:dict_at + 4] = b'DICT'; struct.pack_into('<I', out, dict_at + 8, len(entries))
    for i, (name, w, h, fmt, raw) in enumerate(entries):
        node, obj = nodes + i * 16, objs + i * 0x50
        struct.pack_into('<II', out, node + 8, names_at[i] - (node + 8), obj - (node + 12))
        struct.pack_into('<I', out, obj, 0x20000011); out[obj + 4:obj + 8] = b'TXOB'
        struct.pack_into('<II', out, obj + 0x18, h, w)
        struct.pack_into('<I', out, obj + 0x28, 1); struct.pack_into('<I', out, obj + 0x34, fmt)
        struct.pack_into('<II', out, obj + 0x44, len(raw), blobs_at[i] - (obj + 0x48))
    return bytes(out)


class NativeUiSources(unittest.TestCase):
    def test_reads_textures_and_assigns_roles(self):
        gc, gm, fb, bg = (bytes([n]) * 64 for n in (1, 2, 3, 4))
        common = synthetic_cgfx([('gc_00', 8, 8, 13, gc), ('gm_01', 8, 8, 9, gm), ('bg', 8, 8, 10, bg), ('xx', 8, 8, 9, bytes(64))])
        gag = bytes([9]) * 64
        chapter = synthetic_cgfx([('FB_001', 8, 8, 12, fb), ('CP_000', 8, 8, 10, bytes([7]) * 64), ('CI_000', 8, 8, 3, gag)])
        parsed = list(textures(common))
        self.assertEqual([p[0] for p in parsed], ['gc_00', 'gm_01', 'bg', 'xx'])
        self.assertEqual(parsed[0][1:5], (8, 8, 13, 1))
        self.assertEqual(parsed[0][5], gc)
        with tempfile.TemporaryDirectory() as d:
            romfs = Path(d)
            for folder, blob in (('common', common), ('a010', chapter)):
                p = romfs / 'us/info' / folder / 'info/00.bcres'
                p.parent.mkdir(parents=True); p.write_bytes(blob)
            legacy = romfs / 'portrait-hashes.txt'
            legacy.write_text('00000000000000AA\n')
            rows = prep.build(romfs, legacy)
        key = lambda raw: f'{fingerprint(raw):016X}'
        self.assertEqual(rows[key(gc)][:2], ('hud', 'gc_00'))
        self.assertEqual(rows[key(gm)][:2], ('menu', 'gm_01'))
        self.assertEqual(rows[key(bg)][0], 'decor')
        self.assertEqual(rows[key(fb)][:2], ('portrait', 'FB_001'))
        self.assertEqual(rows[key(gag)][:2], ('insert', 'CI_000'))
        self.assertEqual(rows[key(bytes([7]) * 64)][0], 'decor')
        self.assertEqual(rows['00000000000000AA'][0], 'portrait')
        self.assertNotIn(key(bytes(64)), rows)  # unknown common atlas is not relocated

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            list(textures(b'darc' + bytes(64)))


if __name__ == '__main__':
    unittest.main()
