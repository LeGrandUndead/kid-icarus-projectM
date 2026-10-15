from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import csv
import hashlib
import re
import struct
import sys


ASCII_RE = re.compile(rb"[ -~]{4,}")


@dataclass
class PslbHit:
    hit_id: int
    physical_path: str
    virtual_path: str
    size: int
    sha1: str
    first_32_hex: str
    ascii_string_count: int
    extracted_name: str


def read_u16_le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32_le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def lz11_decompress(data: bytes) -> bytes:
    if not data or data[0] != 0x11:
        raise ValueError("Not Nintendo LZ11 data")

    if len(data) < 4:
        raise ValueError("Truncated LZ11 header")

    out_size = int.from_bytes(data[1:4], "little")
    src = 4

    # Extended-size form (rare, but valid Nintendo LZ11)
    if out_size == 0:
        if len(data) < 8:
            raise ValueError("Truncated extended LZ11 header")
        out_size = int.from_bytes(data[4:8], "little")
        src = 8

    out = bytearray()

    while len(out) < out_size:
        if src >= len(data):
            raise ValueError("Unexpected EOF while reading LZ11 flags")

        flags = data[src]
        src += 1

        for bit in range(8):
            if len(out) >= out_size:
                break

            compressed = flags & (0x80 >> bit)

            if not compressed:
                if src >= len(data):
                    raise ValueError("Unexpected EOF in LZ11 literal")
                out.append(data[src])
                src += 1
                continue

            if src + 1 >= len(data):
                raise ValueError("Unexpected EOF in LZ11 back-reference")

            b1 = data[src]
            b2 = data[src + 1]
            src += 2

            indicator = b1 >> 4

            if indicator == 0:
                if src >= len(data):
                    raise ValueError("Unexpected EOF in LZ11 3-byte reference")
                b3 = data[src]
                src += 1

                length = (((b1 & 0x0F) << 4) | (b2 >> 4)) + 0x11
                displacement = ((b2 & 0x0F) << 8) | b3

            elif indicator == 1:
                if src + 1 >= len(data):
                    raise ValueError("Unexpected EOF in LZ11 4-byte reference")
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
                raise ValueError("Invalid LZ11 displacement")

            for _ in range(length):
                if len(out) >= out_size:
                    break
                out.append(out[copy_pos])
                copy_pos += 1

    return bytes(out)


def read_utf16_name(data: bytes, name_table_start: int, name_offset_units: int) -> str:
    pos = name_table_start + name_offset_units * 2

    if pos < 0 or pos >= len(data):
        raise ValueError("DARC name offset outside archive")

    chars = bytearray()

    while pos + 1 < len(data):
        pair = data[pos:pos + 2]
        pos += 2

        if pair == b"\x00\x00":
            break

        chars += pair

    return chars.decode("utf-16le", errors="replace")


def iter_darc_files(data: bytes):
    if len(data) < 0x1C or data[:4] != b"darc":
        raise ValueError("Not a DARC archive")

    bom = data[4:6]
    if bom != b"\xff\xfe":
        raise ValueError(f"Unsupported DARC BOM: {bom.hex(' ')}")

    header_size = read_u16_le(data, 0x06)
    archive_size = read_u32_le(data, 0x0C)
    table_offset = read_u32_le(data, 0x10)
    table_length = read_u32_le(data, 0x14)

    if header_size < 0x1C:
        raise ValueError(f"Unexpected DARC header size: {header_size:#x}")

    if archive_size > len(data):
        raise ValueError(
            f"DARC declares {archive_size:#x} bytes, "
            f"but only {len(data):#x} are available"
        )

    if table_offset + 12 > len(data):
        raise ValueError("Truncated DARC root entry")

    # Root entry field 2 is the total number of entries.
    entry_count = read_u32_le(data, table_offset + 8)

    if entry_count <= 0:
        raise ValueError("Invalid DARC entry count")

    entries_end = table_offset + entry_count * 12
    table_end = table_offset + table_length

    if entries_end > len(data) or entries_end > table_end:
        raise ValueError("DARC entry table exceeds declared table bounds")

    name_table_start = entries_end

    # stack = [(subtree_end_index, directory_name), ...]
    stack: list[tuple[int, str]] = []

    for index in range(1, entry_count):
        while stack and index >= stack[-1][0]:
            stack.pop()

        entry_off = table_offset + index * 12

        name_flags = read_u32_le(data, entry_off)
        field1 = read_u32_le(data, entry_off + 4)
        field2 = read_u32_le(data, entry_off + 8)

        is_dir = (name_flags & 0xFF000000) != 0
        name_offset_units = name_flags & 0x00FFFFFF
        name = read_utf16_name(data, name_table_start, name_offset_units)

        path_parts = [item[1] for item in stack]

        if is_dir:
            subtree_end = field2

            if subtree_end <= index or subtree_end > entry_count:
                raise ValueError(
                    f"Invalid DARC directory subtree end at entry {index}: {subtree_end}"
                )

            stack.append((subtree_end, name))
            continue

        file_offset = field1
        file_size = field2
        file_end = file_offset + file_size

        if file_end > len(data):
            raise ValueError(
                f"DARC file entry {index} ({name}) exceeds archive bounds"
            )

        virtual_name = "/".join(path_parts + [name])
        yield virtual_name, data[file_offset:file_end]


def ascii_strings(data: bytes) -> list[str]:
    return [
        match.group().decode("ascii", errors="replace")
        for match in ASCII_RE.finditer(data)
    ]


def safe_name(text: str) -> str:
    text = text.replace("\\", "/")
    text = text.replace("::", "__IN__")
    text = re.sub(r"[^A-Za-z0-9._-]+", "__", text)
    text = text.strip("._")
    return text[:160] or "pslb"


def classify_magic(data: bytes) -> str:
    if data.startswith(b"PSLB"):
        return "PSLB"
    if data.startswith(b"darc"):
        return "DARC"
    if data[:1] == b"\x11":
        return "LZ11"
    return "OTHER"


class Scanner:
    def __init__(self, root: Path, output: Path, max_depth: int = 16):
        self.root = root
        self.output = output
        self.max_depth = max_depth

        self.pslb_dir = output / "pslb_files"
        self.pslb_dir.mkdir(parents=True, exist_ok=True)

        self.hits: list[PslbHit] = []
        self.hit_strings: dict[int, list[str]] = {}

        self.darc_count = 0
        self.lz11_count = 0
        self.container_errors: list[str] = []

    def record_pslb(self, data: bytes, physical_path: Path, virtual_path: str):
        hit_id = len(self.hits) + 1
        strings = ascii_strings(data)
        digest = hashlib.sha1(data).hexdigest()

        base = Path(virtual_path.split("::")[-1]).name
        if not base:
            base = "pslb.bin"

        extracted_name = (
            f"{hit_id:04d}__"
            f"{safe_name(virtual_path)}"
        )

        if "." not in Path(extracted_name).name:
            extracted_name += ".pslb"

        out_path = self.pslb_dir / extracted_name
        out_path.write_bytes(data)

        try:
            physical_display = str(physical_path.relative_to(self.root))
        except ValueError:
            physical_display = str(physical_path)

        self.hits.append(
            PslbHit(
                hit_id=hit_id,
                physical_path=physical_display,
                virtual_path=virtual_path,
                size=len(data),
                sha1=digest,
                first_32_hex=data[:32].hex(" ").upper(),
                ascii_string_count=len(strings),
                extracted_name=extracted_name,
            )
        )
        self.hit_strings[hit_id] = strings

    def inspect_blob(
        self,
        data: bytes,
        physical_path: Path,
        virtual_path: str,
        depth: int,
    ):
        if depth > self.max_depth:
            self.container_errors.append(
                f"{virtual_path}: exceeded max recursion depth {self.max_depth}"
            )
            return

        kind = classify_magic(data)

        if kind == "PSLB":
            self.record_pslb(data, physical_path, virtual_path)
            return

        if kind == "LZ11":
            self.lz11_count += 1
            try:
                decompressed = lz11_decompress(data)
            except Exception as exc:
                self.container_errors.append(
                    f"{virtual_path}: LZ11 error: {exc}"
                )
                return

            self.inspect_blob(
                decompressed,
                physical_path,
                virtual_path + "::[LZ11]",
                depth + 1,
            )
            return

        if kind == "DARC":
            self.darc_count += 1

            try:
                entries = list(iter_darc_files(data))
            except Exception as exc:
                self.container_errors.append(
                    f"{virtual_path}: DARC error: {exc}"
                )
                return

            for inner_name, inner_data in entries:
                self.inspect_blob(
                    inner_data,
                    physical_path,
                    virtual_path + "::" + inner_name,
                    depth + 1,
                )

    def scan(self):
        files = sorted(path for path in self.root.rglob("*") if path.is_file())

        print(f"Scanning {len(files)} filesystem files...")

        for i, path in enumerate(files, 1):
            try:
                with path.open("rb") as f:
                    header = f.read(4)

                interesting = (
                    header == b"PSLB"
                    or header == b"darc"
                    or header[:1] == b"\x11"
                )

                if interesting:
                    data = path.read_bytes()
                    rel = path.relative_to(self.root).as_posix()
                    self.inspect_blob(data, path, rel, 0)

            except Exception as exc:
                self.container_errors.append(
                    f"{path}: filesystem read/scan error: {exc}"
                )

            if i % 250 == 0 or i == len(files):
                print(
                    f"[{i}/{len(files)}] "
                    f"PSLB={len(self.hits)} "
                    f"DARC={self.darc_count} "
                    f"LZ11={self.lz11_count}"
                )

    def write_reports(self):
        self.output.mkdir(parents=True, exist_ok=True)

        csv_path = self.output / "pslb_census.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "physical_path",
                "virtual_path",
                "size",
                "sha1",
                "first_32_hex",
                "ascii_string_count",
                "extracted_name",
            ])

            for hit in self.hits:
                writer.writerow([
                    hit.hit_id,
                    hit.physical_path,
                    hit.virtual_path,
                    hit.size,
                    hit.sha1,
                    hit.first_32_hex,
                    hit.ascii_string_count,
                    hit.extracted_name,
                ])

        strings_path = self.output / "pslb_strings.txt"
        with strings_path.open("w", encoding="utf-8") as f:
            for hit in self.hits:
                f.write("=" * 88 + "\n")
                f.write(
                    f"[{hit.hit_id:04d}] {hit.virtual_path}\n"
                    f"size={hit.size} sha1={hit.sha1}\n"
                )
                f.write("=" * 88 + "\n")

                for s in self.hit_strings.get(hit.hit_id, []):
                    f.write(s + "\n")

                f.write("\n")

        summary_path = self.output / "pslb_summary.txt"

        by_sha1: dict[str, list[PslbHit]] = {}
        for hit in self.hits:
            by_sha1.setdefault(hit.sha1, []).append(hit)

        sizes: dict[int, int] = {}
        for hit in self.hits:
            sizes[hit.size] = sizes.get(hit.size, 0) + 1

        with summary_path.open("w", encoding="utf-8") as f:
            f.write("=" * 88 + "\n")
            f.write("KID ICARUS: UPRISING - PSLB CENSUS\n")
            f.write("=" * 88 + "\n\n")
            f.write(f"Root                  : {self.root}\n")
            f.write(f"PSLB occurrences      : {len(self.hits)}\n")
            f.write(f"Unique PSLB SHA1s     : {len(by_sha1)}\n")
            f.write(f"DARC containers seen  : {self.darc_count}\n")
            f.write(f"LZ11 streams seen     : {self.lz11_count}\n")
            f.write(f"Container errors      : {len(self.container_errors)}\n\n")

            f.write("MOST COMMON PSLB SIZES\n")
            f.write("-" * 88 + "\n")
            for size, count in sorted(sizes.items(), key=lambda x: (-x[1], x[0]))[:50]:
                f.write(f"{count:6d} x {size:10d} bytes | 0x{size:X}\n")

            f.write("\nDUPLICATE GROUPS\n")
            f.write("-" * 88 + "\n")

            duplicate_groups = [
                group for group in by_sha1.values() if len(group) > 1
            ]
            duplicate_groups.sort(key=lambda g: (-len(g), g[0].sha1))

            if not duplicate_groups:
                f.write("No exact duplicates found.\n")
            else:
                for group in duplicate_groups:
                    f.write(
                        f"\n{len(group)} identical files | "
                        f"{group[0].size} bytes | SHA1 {group[0].sha1}\n"
                    )
                    for hit in group[:12]:
                        f.write(f"    {hit.virtual_path}\n")
                    if len(group) > 12:
                        f.write(f"    ... {len(group) - 12} more\n")

            f.write("\nSAMPLE PSLB LOCATIONS\n")
            f.write("-" * 88 + "\n")
            for hit in self.hits[:100]:
                f.write(
                    f"[{hit.hit_id:04d}] "
                    f"{hit.size:8d} bytes | "
                    f"{hit.virtual_path}\n"
                )

            if self.container_errors:
                f.write("\nCONTAINER / PARSE ERRORS\n")
                f.write("-" * 88 + "\n")
                for error in self.container_errors:
                    f.write(error + "\n")

        print()
        print("=" * 72)
        print("PSLB CENSUS COMPLETE")
        print("=" * 72)
        print(f"PSLB occurrences : {len(self.hits)}")
        print(f"Unique SHA1s     : {len(by_sha1)}")
        print(f"DARC seen        : {self.darc_count}")
        print(f"LZ11 seen        : {self.lz11_count}")
        print(f"Errors           : {len(self.container_errors)}")
        print()
        print(f"Summary : {summary_path}")
        print(f"CSV     : {csv_path}")
        print(f"Strings : {strings_path}")
        print(f"Files   : {self.pslb_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively census KIU PSLB data from a RomFS, including "
            "PSLBs nested inside DARC archives and LZ11-compressed containers."
        )
    )
    parser.add_argument("root", type=Path, help="RomFS root directory")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pslb_research"),
        help="Output directory (default: ./pslb_research)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=16,
        help="Maximum nested container depth (default: 16)",
    )

    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"ERROR: not a directory: {args.root}")
        return 1

    scanner = Scanner(
        root=args.root.resolve(),
        output=args.output.resolve(),
        max_depth=args.max_depth,
    )

    scanner.scan()
    scanner.write_reports()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
