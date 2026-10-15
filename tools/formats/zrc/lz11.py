from pathlib import Path

def decompress_lz11(data):
    if len(data) < 4 or data[0] != 0x11:
        raise ValueError("Not an LZ11 stream")

    out_size = data[1] | (data[2] << 8) | (data[3] << 16)
    src = 4

    # LZ11 also supports a 32-bit size when the 24-bit field is zero.
    if out_size == 0:
        if len(data) < 8:
            raise ValueError("Truncated extended LZ11 header")
        out_size = int.from_bytes(data[4:8], "little")
        src = 8

    print(f"Expected decompressed size: {out_size:,} bytes")
    print(f"Expected size: 0x{out_size:X}")

    out = bytearray()

    while len(out) < out_size:
        if src >= len(data):
            raise ValueError(
                f"Unexpected EOF reading flags at input 0x{src:X}"
            )

        flags = data[src]
        src += 1

        for bit in range(8):
            if len(out) >= out_size:
                break

            compressed = flags & (0x80 >> bit)

            if not compressed:
                if src >= len(data):
                    raise ValueError("Unexpected EOF reading literal")

                out.append(data[src])
                src += 1
                continue

            if src >= len(data):
                raise ValueError("Unexpected EOF reading back-reference")

            b1 = data[src]
            src += 1

            indicator = b1 >> 4

            # -------------------------------------------
            # Form 1:
            # indicator == 0
            # 3-byte back-reference
            # length = 0x11 .. 0x110
            # -------------------------------------------
            if indicator == 0:
                if src + 2 > len(data):
                    raise ValueError("Truncated 3-byte back-reference")

                b2 = data[src]
                b3 = data[src + 1]
                src += 2

                length = (
                    ((b1 & 0x0F) << 4)
                    | (b2 >> 4)
                ) + 0x11

                disp = (
                    ((b2 & 0x0F) << 8)
                    | b3
                ) + 1

            # -------------------------------------------
            # Form 2:
            # indicator == 1
            # 4-byte back-reference
            # length = 0x111+
            # -------------------------------------------
            elif indicator == 1:
                if src + 3 > len(data):
                    raise ValueError("Truncated 4-byte back-reference")

                b2 = data[src]
                b3 = data[src + 1]
                b4 = data[src + 2]
                src += 3

                length = (
                    ((b1 & 0x0F) << 12)
                    | (b2 << 4)
                    | (b3 >> 4)
                ) + 0x111

                disp = (
                    ((b3 & 0x0F) << 8)
                    | b4
                ) + 1

            # -------------------------------------------
            # Form 3:
            # indicator >= 2
            # normal 2-byte back-reference
            # -------------------------------------------
            else:
                if src >= len(data):
                    raise ValueError("Truncated 2-byte back-reference")

                b2 = data[src]
                src += 1

                length = indicator + 1

                disp = (
                    ((b1 & 0x0F) << 8)
                    | b2
                ) + 1

            if disp > len(out):
                raise ValueError(
                    f"Invalid displacement at input 0x{src:X}: "
                    f"disp={disp}, output_size={len(out)}"
                )

            # Overlapping copies are intentional in LZ compression.
            for _ in range(length):
                if len(out) >= out_size:
                    break

                out.append(out[-disp])

    print(f"Actual output: {len(out):,} bytes")
    print(f"Compressed consumed: {src:,} / {len(data):,} bytes")
    print(f"Remaining input: {len(data) - src:,} bytes")

    return bytes(out)


src_path = Path("a0100.zrc")
dst_path = Path("a0100.decompressed")

data = src_path.read_bytes()
output = decompress_lz11(data)

dst_path.write_bytes(output)

print(f"\nWrote: {dst_path}")