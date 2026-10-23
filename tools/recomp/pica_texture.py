"""Decode the base level of a 3DS (PICA200) texture to RGBA.

    decode(raw, width, height, pica_format) -> numpy uint8 array (height, width, 4)

Rows come out in the order the texture stores them, the order the runtime
decodes them in (and the order `cgfx_textures.py` names): the PC packs are
matched against the runtime's own texels, so they must use the same order.
Formats: 0 RGBA8, 1 RGB8, 2 RGBA5551, 3 RGB565, 4 RGBA4, 5 LA8, 6 HILO8,
7 L8, 8 A8, 9 LA4, 10 L4, 11 A4, 12 ETC1, 13 ETC1A4.
"""
import numpy as np

BITS = {0: 32, 1: 24, 2: 16, 3: 16, 4: 16, 5: 16, 6: 16, 7: 8, 8: 8, 9: 8, 10: 4, 11: 4, 12: 4, 13: 8}

# position of each of the 64 texels of an 8x8 tile in the tile's storage
# order (Z order: x and y bits interleaved, x first)
_MORTON = np.array([[(x & 1) | ((y & 1) << 1) | ((x & 2) << 1) | ((y & 2) << 2) | ((x & 4) << 2) | ((y & 4) << 3)
                     for x in range(8)] for y in range(8)])


def size(width, height, pica_format):
    """Bytes of the base level."""
    return width * height * BITS[pica_format] // 8


def _untile(texels, width, height):
    """texels: (tiles * 64, 4) in storage order -> (height, width, 4)."""
    tiles = texels.reshape(height // 8, width // 8, 64, 4)
    return tiles[:, :, _MORTON, :].transpose(0, 2, 1, 3, 4).reshape(height, width, 4)


def _expand(v, bits):
    return (v.astype(np.uint32) * 255 // ((1 << bits) - 1)).astype(np.uint8)


def _plain(raw, width, height, fmt):
    n = width * height
    b = np.frombuffer(raw, np.uint8, count=size(width, height, fmt))
    out = np.zeros((n, 4), np.uint8)
    if fmt == 0:
        p = b.reshape(n, 4)
        out[:] = p[:, ::-1]                       # stored A B G R
    elif fmt == 1:
        p = b.reshape(n, 3)
        out[:, :3] = p[:, ::-1]; out[:, 3] = 255  # stored B G R
    elif fmt in (2, 3, 4):
        v = b.view('<u2').astype(np.uint32)
        if fmt == 2:
            out[:, 0] = _expand(v >> 11 & 31, 5); out[:, 1] = _expand(v >> 6 & 31, 5)
            out[:, 2] = _expand(v >> 1 & 31, 5); out[:, 3] = (v & 1) * 255
        elif fmt == 3:
            out[:, 0] = _expand(v >> 11 & 31, 5); out[:, 1] = _expand(v >> 5 & 63, 6)
            out[:, 2] = _expand(v & 31, 5); out[:, 3] = 255
        else:
            for i, shift in enumerate((12, 8, 4, 0)):
                out[:, i] = _expand(v >> shift & 15, 4)
    elif fmt == 5:
        p = b.reshape(n, 2)
        out[:, :3] = p[:, 1:2]; out[:, 3] = p[:, 0]
    elif fmt == 6:
        p = b.reshape(n, 2)
        out[:, 0] = p[:, 1]; out[:, 1] = p[:, 0]; out[:, 3] = 255
    elif fmt == 7:
        out[:, :3] = b[:, None]; out[:, 3] = 255
    elif fmt == 8:
        out[:, :3] = 255; out[:, 3] = b
    elif fmt == 9:
        out[:, :3] = _expand(b >> 4, 4)[:, None]; out[:, 3] = _expand(b & 15, 4)
    elif fmt in (10, 11):
        nib = np.empty(n, np.uint8); nib[0::2] = b & 15; nib[1::2] = b >> 4
        if fmt == 10:
            out[:, :3] = _expand(nib, 4)[:, None]; out[:, 3] = 255
        else:
            out[:, :3] = 255; out[:, 3] = _expand(nib, 4)
    return _untile(out, width, height)


_ETC_TABLES = np.array([[2, 8], [5, 17], [9, 29], [13, 42], [18, 60], [24, 80], [33, 106], [47, 183]])
_ETC_SIGNED = np.array([[2, 8, -2, -8], [5, 17, -5, -17], [9, 29, -9, -29], [13, 42, -13, -42],
                        [18, 60, -18, -60], [24, 80, -24, -80], [33, 106, -33, -106], [47, 183, -47, -183]])


def _etc1_block(word):
    """One 4x4 ETC1 block (64-bit, as the 3DS stores it) -> (4, 4, 3) [y][x]."""
    diff = word >> 33 & 1
    flip = word >> 32 & 1
    tables = (word >> 37 & 7, word >> 34 & 7)
    if diff:
        def channel(shift):
            base = word >> shift & 31
            delta = (word >> (shift - 3) & 7)
            delta = delta - 8 if delta >= 4 else delta
            other = (base + delta) & 31
            return [(c << 3) | (c >> 2) for c in (base, other)]
        r, g, b = channel(59), channel(51), channel(43)
    else:
        def channel(shift):
            hi, lo = word >> shift & 15, word >> (shift - 4) & 15
            return [hi * 17, lo * 17]
        r, g, b = channel(60), channel(52), channel(44)
    out = np.zeros((4, 4, 3), np.int32)
    for x in range(4):
        for y in range(4):
            sub = (y >= 2) if flip else (x >= 2)
            i = x * 4 + y
            # index bits: msb from the high half, lsb from the low half
            index = ((word >> (i + 16) & 1) << 1) | (word >> i & 1)
            modifier = [_ETC_TABLES[tables[sub]][0], _ETC_TABLES[tables[sub]][1],
                        -_ETC_TABLES[tables[sub]][0], -_ETC_TABLES[tables[sub]][1]][index]
            out[y, x] = [r[sub] + modifier, g[sub] + modifier, b[sub] + modifier]
    return np.clip(out, 0, 255).astype(np.uint8)


def _etc1(raw, width, height, alpha):
    step = 16 if alpha else 8
    img = np.zeros((height, width, 4), np.uint8)
    at = 0
    for ty in range(0, height, 8):
        for tx in range(0, width, 8):
            for by, bx in ((0, 0), (0, 4), (4, 0), (4, 4)):
                if alpha:
                    a = int.from_bytes(raw[at:at + 8], 'little')
                word = int.from_bytes(raw[at + step - 8:at + step], 'little')
                at += step
                block = _etc1_block(word)
                img[ty + by:ty + by + 4, tx + bx:tx + bx + 4, :3] = block
                if alpha:
                    for x in range(4):
                        for y in range(4):
                            v = a >> ((x * 4 + y) * 4) & 15
                            img[ty + by + y, tx + bx + x, 3] = v * 17
                else:
                    img[ty + by:ty + by + 4, tx + bx:tx + bx + 4, 3] = 255
    return img


def decode(raw, width, height, pica_format):
    if pica_format in (12, 13):
        return _etc1(raw, width, height, pica_format == 13)
    return _plain(raw, width, height, pica_format)
