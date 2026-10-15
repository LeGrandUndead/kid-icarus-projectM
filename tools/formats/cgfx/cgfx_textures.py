"""List CGFX (.bcres) image textures with their raw encoded bytes.

Minimal reader for the texture dictionary only (DATA entry 1). Works on the
user's extracted ROM files; produces nothing by itself.
"""
from __future__ import annotations
import struct

TXOB_IMAGE = 0x20000011


def _u32(d: bytes, o: int) -> int:
    return struct.unpack_from('<I', d, o)[0]


def _rel(d: bytes, o: int) -> int | None:
    v = _u32(d, o)
    return o + v if v else None


def _cstr(d: bytes, o: int) -> str:
    return d[o:d.index(b'\0', o)].decode('ascii', 'replace')


def textures(d: bytes):
    """Yield (name, width, height, pica_format, mip_levels, raw_bytes or None)."""
    if d[:4] != b'CGFX':
        raise ValueError('not a CGFX file')
    data = struct.unpack_from('<H', d, 6)[0]
    if d[data:data + 4] != b'DATA':
        raise ValueError('missing DATA block')
    count = _u32(d, data + 16)
    if not count:
        return
    at = _rel(d, data + 20)
    if d[at:at + 4] != b'DICT':
        raise ValueError('texture dictionary missing')
    for i in range(_u32(d, at + 8)):
        node = at + 0x1C + i * 16
        name = _cstr(d, _rel(d, node + 8))
        obj = _rel(d, node + 12)
        if d[obj + 4:obj + 8] != b'TXOB':
            raise ValueError(f'{name}: not a texture object')
        height, width = _u32(d, obj + 0x18), _u32(d, obj + 0x1C)
        mips, fmt = _u32(d, obj + 0x28), _u32(d, obj + 0x34)
        raw = None
        if _u32(d, obj) == TXOB_IMAGE:
            size, buf = _u32(d, obj + 0x44), _rel(d, obj + 0x48)
            raw = d[buf:buf + size]
        yield name, width, height, fmt, mips, raw
