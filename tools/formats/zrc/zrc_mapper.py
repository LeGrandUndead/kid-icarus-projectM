from pathlib import Path
import struct

data = Path("a0100.zrc").read_bytes()

positions = []
pos = 0

while True:
    pos = data.find(b"darc", pos)
    if pos == -1:
        break
    positions.append(pos)
    pos += 1

print(f"Found {len(positions)} DARC markers")
print("=" * 80)

for n, pos in enumerate(positions):
    h = data[pos:pos + 0x1C]

    print(f"\nDARC #{n}")
    print(f"Offset: 0x{pos:X}")
    print(f"Raw:    {h.hex(' ')}")

    if len(h) < 0x1C:
        continue

    print("\nFields:")

    print("  magic      =", h[0:4])
    print("  endian     =", hex(struct.unpack_from("<H", h, 4)[0]))
    print("  headerSize =", hex(struct.unpack_from("<H", h, 6)[0]))

    print("  version LE =", hex(struct.unpack_from("<I", h, 8)[0]))
    print("  version BE =", hex(struct.unpack_from(">I", h, 8)[0]))

    print("  size LE    =", hex(struct.unpack_from("<I", h, 12)[0]))
    print("  size BE    =", hex(struct.unpack_from(">I", h, 12)[0]))

    print("  table LE   =", hex(struct.unpack_from("<I", h, 16)[0]))
    print("  table BE   =", hex(struct.unpack_from(">I", h, 16)[0]))

    print("  tableLenLE =", hex(struct.unpack_from("<I", h, 20)[0]))
    print("  tableLenBE =", hex(struct.unpack_from(">I", h, 20)[0]))

    print("  data LE    =", hex(struct.unpack_from("<I", h, 24)[0]))
    print("  data BE    =", hex(struct.unpack_from(">I", h, 24)[0]))

    print("\nNext 32 bytes:")
    print(data[pos + 0x1C:pos + 0x3C].hex(" "))