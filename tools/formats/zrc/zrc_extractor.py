from pathlib import Path
import struct
import sys


# ============================================================
# LZ11
# ============================================================

def decompress_lz11(data):
    if len(data) < 4 or data[0] != 0x11:
        raise ValueError("Input is not Nintendo LZ11")

    out_size = data[1] | (data[2] << 8) | (data[3] << 16)
    src = 4

    if out_size == 0:
        out_size = int.from_bytes(data[4:8], "little")
        src = 8

    out = bytearray()

    while len(out) < out_size:
        flags = data[src]
        src += 1

        for bit in range(8):
            if len(out) >= out_size:
                break

            if not (flags & (0x80 >> bit)):
                out.append(data[src])
                src += 1
                continue

            b1 = data[src]
            src += 1

            indicator = b1 >> 4

            if indicator == 0:
                b2 = data[src]
                b3 = data[src + 1]
                src += 2

                length = (
                    ((b1 & 0x0F) << 4)
                    | (b2 >> 4)
                ) + 0x11

                distance = (
                    ((b2 & 0x0F) << 8)
                    | b3
                ) + 1

            elif indicator == 1:
                b2 = data[src]
                b3 = data[src + 1]
                b4 = data[src + 2]
                src += 3

                length = (
                    ((b1 & 0x0F) << 12)
                    | (b2 << 4)
                    | (b3 >> 4)
                ) + 0x111

                distance = (
                    ((b3 & 0x0F) << 8)
                    | b4
                ) + 1

            else:
                b2 = data[src]
                src += 1

                length = indicator + 1
                distance = (
                    ((b1 & 0x0F) << 8)
                    | b2
                ) + 1

            if distance > len(out):
                raise ValueError(
                    f"Invalid LZ11 distance {distance} "
                    f"at output 0x{len(out):X}"
                )

            for _ in range(length):
                if len(out) >= out_size:
                    break
                out.append(out[-distance])

    return bytes(out)


# ============================================================
# DARC
# ============================================================

def read_utf16(data, offset):
    chars = []

    while offset + 1 < len(data):
        c = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        if c == 0:
            break

        chars.append(chr(c))

    return "".join(chars)


def extract_darc(data, output_dir):
    if data[:4] != b"darc":
        raise ValueError("Decompressed data is not DARC")

    header_size = struct.unpack_from("<H", data, 6)[0]
    file_size = struct.unpack_from("<I", data, 0x0C)[0]
    table_offset = struct.unpack_from("<I", data, 0x10)[0]
    table_length = struct.unpack_from("<I", data, 0x14)[0]
    data_offset = struct.unpack_from("<I", data, 0x18)[0]

    print("\nDARC")
    print("------------------------------------------------")
    print(f"Header size : 0x{header_size:X}")
    print(f"Archive size: {file_size:,} bytes")
    print(f"Table       : 0x{table_offset:X}")
    print(f"Table size  : 0x{table_length:X}")
    print(f"Data        : 0x{data_offset:X}")

    # Root entry
    root_name, root_parent, entry_count = struct.unpack_from(
        "<III", data, table_offset
    )

    print(f"Entries     : {entry_count}")

    name_table = table_offset + entry_count * 12

    entries = []

    for i in range(entry_count):
        pos = table_offset + i * 12

        name_field, field1, field2 = struct.unpack_from(
            "<III", data, pos
        )

        is_dir = bool(name_field & 0x01000000)
        name_offset = name_field & 0x00FFFFFF

        name = read_utf16(
            data,
            name_table + name_offset
        )

        entries.append({
            "index": i,
            "name": name,
            "directory": is_dir,
            "field1": field1,
            "field2": field2,
        })

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build directory hierarchy recursively.
    def process_directory(index, path):
        entry = entries[index]

        # DARC directory:
        # field1 = parent index
        # field2 = index immediately after this directory's subtree

        child = index + 1
        end = entry["field2"]

        while child < end:
            e = entries[child]

            if e["directory"]:
                dirname = e["name"] or f"dir_{child}"

                new_path = path / dirname
                new_path.mkdir(parents=True, exist_ok=True)

                print(f"[DIR ] {new_path}")

                process_directory(child, new_path)

                # Skip its complete subtree.
                child = e["field2"]

            else:
                filename = e["name"] or f"file_{child}.bin"

                start = e["field1"]
                size = e["field2"]
                finish = start + size

                if finish > len(data):
                    raise ValueError(
                        f"{filename}: data outside archive "
                        f"(0x{start:X}+0x{size:X})"
                    )

                destination = path / filename
                destination.write_bytes(data[start:finish])

                print(
                    f"[FILE] {destination} "
                    f"(0x{start:X}, {size:,} bytes)"
                )

                child += 1

    process_directory(0, output_dir)


# ============================================================
# MAIN
# ============================================================

if len(sys.argv) < 2:
    print("Usage:")
    print("  python zrc_extractor.py file.zrc")
    sys.exit(1)

source = Path(sys.argv[1])

raw = source.read_bytes()

print(f"Input: {source}")
print(f"Compressed size: {len(raw):,} bytes")

print("\nDecompressing LZ11...")
decompressed = decompress_lz11(raw)

print(f"Decompressed: {len(decompressed):,} bytes")

output = source.parent / (source.stem + "_extracted")

print("\nExtracting DARC...")

extract_darc(decompressed, output)

print("\n================================================")
print("DONE")
print(f"Output: {output}")