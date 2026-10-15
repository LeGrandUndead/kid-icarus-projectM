"""Install Azahar's open-source shared font from its verified archive header.

Usage: python tools/recomp/install_open_font.py build/font-source/shared_font.app.romfs.h
See doc/FONT_SOURCE.md for provenance. Never overwrites a different installed font.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/formats/pslb'))
from pslb_census import lz11_decompress

HEADER_SHA256 = '316a05284c0746bcd1b5623c54ff770f2db736bdb90a592c2eda176e2c3ac6c1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('header', type=Path)
    args = parser.parse_args()
    source = args.header.read_bytes()
    if hashlib.sha256(source).hexdigest() != HEADER_SHA256:
        parser.error('Header does not match the verified open-source font archive')
    archive = bytes(int(x, 16) for x in re.findall(rb'0x([0-9a-fA-F]{2})', source))
    metadata, data_start = struct.unpack_from('<I', archive, 0x1C)[0], struct.unpack_from('<I', archive, 0x24)[0]
    offset, size = struct.unpack_from('<QQ', archive, metadata + 8)
    name_size = struct.unpack_from('<I', archive, metadata + 28)[0]
    name = archive[metadata + 32:metadata + 32 + name_size].decode('utf-16le')
    if name != 'cbf_std.bcfnt.lz':
        raise ValueError('Unexpected font archive entry')
    compressed = archive[data_start + offset:data_start + offset + size]
    if len(compressed) != size or compressed[0] != 0x11:
        raise ValueError('Truncated or invalid compressed font')
    expected = int.from_bytes(compressed[1:4], 'little')
    if not 0 < expected < 4 * 1024 * 1024:
        raise ValueError('Unexpected font size')
    font = bytearray(lz11_decompress(compressed))
    if len(font) != expected or font[:4] != b'CFNT' or struct.unpack_from('<I', font, 12)[0] != len(font):
        raise ValueError('Invalid decoded font')
    # Zakuro relocates section offsets when it maps the shared block. CFNU
    # tells the guest that those pointers have already been relocated.
    font[:4] = b'CFNU'
    block = bytearray(0x80)
    struct.pack_into('<III', block, 0, 2, 1, len(font))
    block += font
    target = ROOT / 'build/user-data/kiu/sysdata/shared_font.bin'
    if target.exists() and target.read_bytes() != block:
        parser.error('A different shared font is already installed; preserve it before replacing')
    notices = [args.header.parent / name for name in
               ('Montserrat-OFL.txt', 'Unifont-notice.txt', 'generator-license.txt')]
    if not all(path.is_file() for path in notices):
        parser.error('Keep the font license notices beside the archive header; see doc/FONT_SOURCE.md')
    target.parent.mkdir(parents=True, exist_ok=True)
    licenses = target.parent / 'font-licenses'
    licenses.mkdir(exist_ok=True)
    for path in notices:
        shutil.copyfile(path, licenses / path.name)
    target.write_bytes(block)
    record = dict(source_header_sha256=HEADER_SHA256, archive_entry=name,
                  output_sha256=hashlib.sha256(block).hexdigest(), bytes=len(block),
                  generator_revision='848af476fb2fad4144962dfb2548bd7841f1b72a')
    target.with_suffix('.source.json').write_text(json.dumps(record, indent=2) + '\n')
    print(target)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
