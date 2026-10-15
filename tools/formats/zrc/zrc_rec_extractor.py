from pathlib import Path
import struct
import sys


# ============================================================
# LZ11
# ============================================================

def decompress_lz11(data):
    if len(data) < 4 or data[0] != 0x11:
        first = f"{data[0]:02X}" if data else "none"
        raise ValueError(
            f"Not Nintendo LZ11 (first byte = {first})"
        )

    out_size = data[1] | (data[2] << 8) | (data[3] << 16)
    src = 4

    # Extended LZ11 size
    if out_size == 0:
        if len(data) < 8:
            raise ValueError("Truncated extended LZ11 header")

        out_size = int.from_bytes(data[4:8], "little")
        src = 8

    out = bytearray()

    while len(out) < out_size:

        if src >= len(data):
            raise ValueError(
                f"Unexpected EOF at compressed offset 0x{src:X}"
            )

        flags = data[src]
        src += 1

        for bit in range(8):

            if len(out) >= out_size:
                break

            # ------------------------------------------------
            # Literal
            # ------------------------------------------------

            if not (flags & (0x80 >> bit)):

                if src >= len(data):
                    raise ValueError("Unexpected EOF reading literal")

                out.append(data[src])
                src += 1
                continue

            # ------------------------------------------------
            # Back-reference
            # ------------------------------------------------

            if src >= len(data):
                raise ValueError("Unexpected EOF reading back-reference")

            b1 = data[src]
            src += 1

            indicator = b1 >> 4

            # ------------------------------------------------
            # 3-byte form
            # ------------------------------------------------

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

                distance = (
                    ((b2 & 0x0F) << 8)
                    | b3
                ) + 1

            # ------------------------------------------------
            # 4-byte form
            # ------------------------------------------------

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

                distance = (
                    ((b3 & 0x0F) << 8)
                    | b4
                ) + 1

            # ------------------------------------------------
            # Normal 2-byte form
            # ------------------------------------------------

            else:

                if src >= len(data):
                    raise ValueError("Truncated 2-byte back-reference")

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

            # LZ back-references may intentionally overlap.
            for _ in range(length):

                if len(out) >= out_size:
                    break

                out.append(out[-distance])

    # ========================================================
    # KIU ZRC alignment
    #
    # The LZ11 stream can finish before the physical end of
    # the ZRC. Observed files are padded to a 0x20 boundary.
    # ========================================================

    remaining = len(data) - src

    if remaining:

        expected_padding = (-src) % 0x20

        if remaining != expected_padding:
            raise ValueError(
                f"Unexpected trailing data: "
                f"LZ11 consumed {src:,}/{len(data):,} bytes; "
                f"{remaining} bytes remain; "
                f"expected {expected_padding} bytes "
                f"for 0x20 alignment"
            )

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

    if len(data) < 0x1C:
        raise ValueError("DARC is too small")

    if data[:4] != b"darc":
        raise ValueError(
            f"LZ11 output isn't DARC "
            f"(magic = {data[:4]!r})"
        )

    bom = data[4:6]

    if bom != b"\xFF\xFE":
        raise ValueError(
            f"Unsupported DARC byte order: {bom.hex(' ')}"
        )

    header_size = struct.unpack_from("<H", data, 6)[0]
    archive_size = struct.unpack_from("<I", data, 0x0C)[0]
    table_offset = struct.unpack_from("<I", data, 0x10)[0]
    table_length = struct.unpack_from("<I", data, 0x14)[0]
    data_offset = struct.unpack_from("<I", data, 0x18)[0]

    if header_size != 0x1C:
        raise ValueError(
            f"Unexpected DARC header size: 0x{header_size:X}"
        )

    if archive_size != len(data):
        raise ValueError(
            f"DARC size mismatch: "
            f"header=0x{archive_size:X}, "
            f"actual=0x{len(data):X}"
        )

    if table_offset + 12 > len(data):
        raise ValueError("DARC table is outside archive")

    # Root directory entry:
    #
    # name field
    # parent index
    # end index
    #
    _, _, entry_count = struct.unpack_from(
        "<III",
        data,
        table_offset
    )

    if entry_count <= 0:
        raise ValueError("DARC contains zero entries")

    table_entries_end = table_offset + entry_count * 12

    if table_entries_end > len(data):
        raise ValueError(
            "DARC entry table extends outside archive"
        )

    name_table = table_entries_end

    entries = []

    for i in range(entry_count):

        pos = table_offset + i * 12

        name_field, field1, field2 = struct.unpack_from(
            "<III",
            data,
            pos
        )

        is_dir = bool(name_field & 0x01000000)
        name_offset = name_field & 0x00FFFFFF

        name_pos = name_table + name_offset

        if name_pos >= len(data):
            raise ValueError(
                f"Entry {i}: invalid name offset "
                f"0x{name_offset:X}"
            )

        name = read_utf16(
            data,
            name_pos
        )

        entries.append({
            "index": i,
            "name": name,
            "directory": is_dir,
            "field1": field1,
            "field2": field2,
        })

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    files_written = 0

    # ========================================================
    # Directory tree
    # ========================================================

    def process_directory(index, path):

        nonlocal files_written

        entry = entries[index]

        child = index + 1
        end = entry["field2"]

        if end > len(entries):
            raise ValueError(
                f"Directory {index} subtree ends outside table"
            )

        while child < end:

            e = entries[child]

            # ------------------------------------------------
            # Directory
            # ------------------------------------------------

            if e["directory"]:

                dirname = (
                    e["name"]
                    or f"dir_{child}"
                )

                new_path = path / dirname

                new_path.mkdir(
                    parents=True,
                    exist_ok=True
                )

                process_directory(
                    child,
                    new_path
                )

                # Directory field2 points to the first entry
                # after its subtree.
                child = e["field2"]

            # ------------------------------------------------
            # File
            # ------------------------------------------------

            else:

                filename = (
                    e["name"]
                    or f"file_{child}.bin"
                )

                start = e["field1"]
                size = e["field2"]

                finish = start + size

                if start < data_offset:
                    raise ValueError(
                        f"{filename}: starts before "
                        f"DARC data section "
                        f"(0x{start:X} < 0x{data_offset:X})"
                    )

                if finish > len(data):
                    raise ValueError(
                        f"{filename}: extends outside archive "
                        f"(0x{start:X} + 0x{size:X})"
                    )

                destination = path / filename

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                destination.write_bytes(
                    data[start:finish]
                )

                files_written += 1
                child += 1

    process_directory(
        0,
        output_dir
    )

    return files_written


# ============================================================
# ONE ZRC
# ============================================================

def extract_zrc(source, destination):

    raw = source.read_bytes()

    decompressed = decompress_lz11(raw)

    files = extract_darc(
        decompressed,
        destination
    )

    return {
        "compressed": len(raw),
        "decompressed": len(decompressed),
        "files": files,
    }


# ============================================================
# BATCH EXTRACTION
# ============================================================

def batch_extract(root):

    root = root.resolve()

    if not root.exists():
        raise FileNotFoundError(root)

    # ========================================================
    # Single ZRC
    # ========================================================

    if root.is_file():

        if root.suffix.lower() != ".zrc":
            raise ValueError(
                "Input file is not .zrc"
            )

        destination = (
            root.parent
            / "zrc_extracted"
            / root.stem
        )

        print()
        print(f"[ZRC] {root.name}")

        info = extract_zrc(
            root,
            destination
        )

        print(
            f"      {info['compressed']:,} -> "
            f"{info['decompressed']:,} bytes"
        )

        print(
            f"      {info['files']} files"
        )

        print(
            f"      -> {destination}"
        )

        return

    # ========================================================
    # Directory / recursive search
    # ========================================================

    zrc_files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() == ".zrc"
        and "zrc_extracted" not in p.parts
    )

    if not zrc_files:
        print("No .zrc files found.")
        return

    output_root = (
        root
        / "zrc_extracted"
    )

    print("=" * 70)
    print("KID ICARUS: UPRISING ZRC EXTRACTOR")
    print("=" * 70)

    print(f"Root   : {root}")
    print(f"Output : {output_root}")
    print(f"Found  : {len(zrc_files)} ZRC files")
    print()

    successes = []
    failures = []

    # ========================================================
    # Process all ZRC files
    # ========================================================

    for number, source in enumerate(
        zrc_files,
        1
    ):

        relative = source.relative_to(root)

        destination = (
            output_root
            / relative.parent
            / source.stem
        )

        print(
            f"[{number:4}/{len(zrc_files)}] "
            f"{relative}"
        )

        try:

            info = extract_zrc(
                source,
                destination
            )

            successes.append(
                (relative, info)
            )

            ratio = (
                info["compressed"]
                / info["decompressed"]
                * 100
            )

            print(
                f"       OK | "
                f"{info['compressed']:,} -> "
                f"{info['decompressed']:,} bytes | "
                f"{ratio:.1f}% | "
                f"{info['files']} files"
            )

        except Exception as exc:

            failures.append(
                (relative, str(exc))
            )

            print(
                f"       FAILED: {exc}"
            )

    # ========================================================
    # Final report
    # ========================================================

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        f"ZRC found : {len(zrc_files)}"
    )

    print(
        f"Extracted : {len(successes)}"
    )

    print(
        f"Failed    : {len(failures)}"
    )

    total_compressed = sum(
        info["compressed"]
        for _, info in successes
    )

    total_decompressed = sum(
        info["decompressed"]
        for _, info in successes
    )

    total_files = sum(
        info["files"]
        for _, info in successes
    )

    print(
        f"Input     : {total_compressed:,} bytes"
    )

    print(
        f"Expanded  : {total_decompressed:,} bytes"
    )

    print(
        f"Files     : {total_files:,}"
    )

    # ========================================================
    # Failure report
    # ========================================================

    if failures:

        print()
        print("FAILED FILES")
        print("-" * 70)

        for filename, error in failures:

            print(filename)
            print(f"    {error}")

        report = (
            output_root
            / "_failures.txt"
        )

        report.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with report.open(
            "w",
            encoding="utf-8"
        ) as f:

            for filename, error in failures:

                f.write(
                    f"{filename}\n"
                    f"    {error}\n\n"
                )

        print()
        print(
            f"Failure report: {report}"
        )

    print()
    print(
        f"Output: {output_root}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "Kid Icarus: Uprising ZRC Extractor"
        )

        print()

        print("Single file:")
        print(
            "  python zrc_extractor.py a0100.zrc"
        )

        print()

        print("Whole directory:")
        print(
            "  python zrc_extractor.py stage"
        )

        print()

        print("Current directory:")
        print(
            "  python zrc_extractor.py ."
        )

        sys.exit(1)

    batch_extract(
        Path(sys.argv[1])
    )