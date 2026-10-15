from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib
import struct
import sys
import time


def u16(data, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def magic4(data) -> bytes:
    return bytes(data[:4]) if len(data) >= 4 else bytes(data)


def read_utf16z(data, off: int) -> str:
    if off < 0 or off >= len(data):
        raise ValueError(f"name offset out of range: 0x{off:X}")

    end = off
    while end + 1 < len(data):
        if data[end] == 0 and data[end + 1] == 0:
            return bytes(data[off:end]).decode("utf-16le", errors="strict")
        end += 2

    raise ValueError(f"unterminated UTF-16LE name at 0x{off:X}")


def iter_darc_files(data):
    if len(data) < 0x1C or magic4(data) != b"darc":
        raise ValueError("not DARC")

    if bytes(data[4:6]) != b"\xFF\xFE":
        raise ValueError(f"unsupported DARC BOM: {bytes(data[4:6]).hex(' ')}")

    table_offset = u32(data, 0x10)
    table_length = u32(data, 0x14)

    if table_offset + 12 > len(data):
        raise ValueError("truncated DARC root entry")

    entry_count = u32(data, table_offset + 8)
    if entry_count <= 0:
        raise ValueError("invalid DARC entry count")

    entries_end = table_offset + entry_count * 12
    table_end = table_offset + table_length

    if entries_end > table_end or table_end > len(data):
        raise ValueError("DARC table bounds invalid")

    # Correct DARC semantics:
    # low 24 bits = BYTE offset into the UTF-16LE name table.
    name_table_start = entries_end

    stack: list[tuple[int, str]] = []

    for index in range(1, entry_count):
        while stack and index >= stack[-1][0]:
            stack.pop()

        entry_off = table_offset + index * 12
        name_flags = u32(data, entry_off)
        field1 = u32(data, entry_off + 4)
        field2 = u32(data, entry_off + 8)

        is_dir = bool(name_flags & 0x01000000)
        name_offset = name_flags & 0x00FFFFFF
        name = read_utf16z(data, name_table_start + name_offset)

        parent = [x[1] for x in stack]
        full_name = "/".join(parent + [name]) if parent else name

        if is_dir:
            subtree_end = field2
            if subtree_end <= index or subtree_end > entry_count:
                raise ValueError(
                    f"directory entry {index} has invalid subtree end {subtree_end}"
                )
            stack.append((subtree_end, name))
            continue

        file_offset = field1
        file_size = field2
        file_end = file_offset + file_size

        if file_end > len(data):
            raise ValueError(
                f"file entry {index} ({full_name}) exceeds archive bounds"
            )

        yield full_name, file_offset, file_size


def lz11_decompress(data) -> bytes:
    if len(data) < 4 or data[0] != 0x11:
        raise ValueError("not LZ11")

    out_size = int.from_bytes(bytes(data[1:4]), "little")
    src = 4

    if out_size == 0:
        if len(data) < 8:
            raise ValueError("truncated extended LZ11 header")
        out_size = int.from_bytes(bytes(data[4:8]), "little")
        src = 8

    # Basic sanity limit: KIU assets should never need absurd allocations.
    if out_size <= 0 or out_size > 512 * 1024 * 1024:
        raise ValueError(f"implausible LZ11 output size: {out_size}")

    out = bytearray()

    while len(out) < out_size:
        if src >= len(data):
            raise ValueError("unexpected EOF reading LZ11 flags")

        flags = data[src]
        src += 1

        for bit in range(8):
            if len(out) >= out_size:
                break

            if not (flags & (0x80 >> bit)):
                if src >= len(data):
                    raise ValueError("unexpected EOF in LZ11 literal")
                out.append(data[src])
                src += 1
                continue

            if src + 1 >= len(data):
                raise ValueError("unexpected EOF in LZ11 reference")

            b1 = data[src]
            b2 = data[src + 1]
            src += 2
            indicator = b1 >> 4

            if indicator == 0:
                if src >= len(data):
                    raise ValueError("unexpected EOF in LZ11 3-byte reference")
                b3 = data[src]
                src += 1
                length = (((b1 & 0x0F) << 4) | (b2 >> 4)) + 0x11
                displacement = ((b2 & 0x0F) << 8) | b3

            elif indicator == 1:
                if src + 1 >= len(data):
                    raise ValueError("unexpected EOF in LZ11 4-byte reference")
                b3 = data[src]
                b4 = data[src + 1]
                src += 2
                length = (
                    ((b1 & 0x0F) << 12)
                    | (b2 << 4)
                    | (b3 >> 4)
                ) + 0x111
                displacement = ((b3 & 0x0F) << 8) | b4

            else:
                length = indicator + 1
                displacement = ((b1 & 0x0F) << 8) | b2

            copy_pos = len(out) - displacement - 1
            if copy_pos < 0:
                raise ValueError("invalid LZ11 displacement")

            for _ in range(length):
                if len(out) >= out_size:
                    break
                out.append(out[copy_pos])
                copy_pos += 1

    return bytes(out)


class Mapper:
    def __init__(self, root: Path, max_depth: int):
        self.root = root
        self.max_depth = max_depth

        self.rows = []
        self.darc_seen = 0
        self.lz11_ok = 0
        self.lz11_false_positive = 0
        self.errors = []

    def add_pslb(self, data, physical_path: Path, virtual_path: str, depth: int):
        blob = bytes(data)
        self.rows.append({
            "physical_path": physical_path.relative_to(self.root).as_posix(),
            "virtual_path": virtual_path,
            "size": len(blob),
            "sha1": hashlib.sha1(blob).hexdigest(),
            "depth": depth,
        })

    def inspect(self, data, physical_path: Path, virtual_path: str, depth: int):
        if depth > self.max_depth:
            self.errors.append(f"{virtual_path}: max depth exceeded")
            return

        head = magic4(data)

        if head == b"PSLB":
            self.add_pslb(data, physical_path, virtual_path, depth)
            return

        if head == b"darc":
            self.darc_seen += 1
            try:
                for name, off, size in iter_darc_files(data):
                    entry = memoryview(data)[off:off + size]
                    entry_head = magic4(entry)

                    if (
                        entry_head == b"PSLB"
                        or entry_head == b"darc"
                        or (len(entry) >= 1 and entry[0] == 0x11)
                    ):
                        self.inspect(
                            entry,
                            physical_path,
                            virtual_path + "::" + name,
                            depth + 1,
                        )
            except Exception as exc:
                self.errors.append(f"{virtual_path}: DARC error: {exc}")
            return

        # 0x11 alone is only a candidate. If decompression fails, treat it as
        # a false positive, not as a damaged asset.
        if len(data) >= 1 and data[0] == 0x11:
            try:
                dec = lz11_decompress(data)
            except Exception:
                self.lz11_false_positive += 1
                return

            self.lz11_ok += 1
            self.inspect(
                dec,
                physical_path,
                virtual_path + "::[LZ11]",
                depth + 1,
            )

    def run(self):
        files = sorted(p for p in self.root.rglob("*") if p.is_file())
        total = len(files)
        started = time.perf_counter()

        print(f"Scanning {total} filesystem files...", flush=True)

        for i, path in enumerate(files, 1):
            try:
                with path.open("rb") as f:
                    head = f.read(4)

                if (
                    head == b"PSLB"
                    or head == b"darc"
                    or head[:1] == b"\x11"
                ):
                    data = path.read_bytes()
                    self.inspect(
                        data,
                        path,
                        path.relative_to(self.root).as_posix(),
                        0,
                    )

            except KeyboardInterrupt:
                raise
            except Exception as exc:
                self.errors.append(f"{path}: {exc}")

            if i % 250 == 0 or i == total:
                elapsed = time.perf_counter() - started
                print(
                    f"[{i}/{total}] {elapsed:7.1f}s | "
                    f"PSLB={len(self.rows)} "
                    f"DARC={self.darc_seen} "
                    f"LZ11={self.lz11_ok} "
                    f"false11={self.lz11_false_positive} "
                    f"errors={len(self.errors)}",
                    flush=True,
                )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Build a correct PSLB occurrence/path map from KIU RomFS. "
            "This does not decode PSLB contents; it maps payload SHA1s "
            "to trustworthy physical/virtual archive paths."
        )
    )
    ap.add_argument("romfs", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("pslb_occurrence_map"),
    )
    ap.add_argument("--max-depth", type=int, default=16)
    args = ap.parse_args()

    root = args.romfs.resolve()
    out = args.output.resolve()

    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    mapper = Mapper(root, args.max_depth)

    try:
        mapper.run()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130

    csv_path = out / "pslb_occurrences_fixed.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "physical_path",
                "virtual_path",
                "size",
                "sha1",
                "depth",
            ],
        )
        w.writeheader()
        w.writerows(mapper.rows)

    unique_sha1 = len({row["sha1"] for row in mapper.rows})

    summary_path = out / "pslb_occurrence_summary.txt"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("KIU PSLB OCCURRENCE / PATH MAP\n")
        f.write("=" * 88 + "\n\n")
        f.write(f"Occurrences             : {len(mapper.rows)}\n")
        f.write(f"Unique SHA1             : {unique_sha1}\n")
        f.write(f"DARC containers seen    : {mapper.darc_seen}\n")
        f.write(f"Valid LZ11 streams      : {mapper.lz11_ok}\n")
        f.write(f"0x11 false positives    : {mapper.lz11_false_positive}\n")
        f.write(f"Actual scan errors      : {len(mapper.errors)}\n\n")

        f.write("SAMPLE PATHS\n")
        f.write("-" * 88 + "\n")
        for row in mapper.rows[:200]:
            f.write(
                f"{row['sha1']} | {row['size']:8d} | {row['virtual_path']}\n"
            )

        if mapper.errors:
            f.write("\nERRORS\n")
            f.write("-" * 88 + "\n")
            for error in mapper.errors:
                f.write(error + "\n")

    print()
    print("=" * 72)
    print("PSLB PATH MAP COMPLETE")
    print("=" * 72)
    print(f"Occurrences          : {len(mapper.rows)}")
    print(f"Unique SHA1          : {unique_sha1}")
    print(f"DARC seen            : {mapper.darc_seen}")
    print(f"Valid LZ11           : {mapper.lz11_ok}")
    print(f"0x11 false positives : {mapper.lz11_false_positive}")
    print(f"Actual errors        : {len(mapper.errors)}")
    print()
    print(f"CSV     : {csv_path}")
    print(f"Summary : {summary_path}")

    return 0 if not mapper.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
