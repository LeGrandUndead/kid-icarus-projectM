#!/usr/bin/env python3

"""
Kid Icarus: Uprising - BIN Structural Census
=============================================

Analyzes .bin files without modifying them.

Produces:

    bin_census.csv
        Detailed information for every .bin file.

    bin_groups.txt
        Human-readable structural summary.

    bin_strings.txt
        Extracted printable ASCII strings.

Usage:

    python bin_census.py "D:\\Games\\Kid icarus\\ROM\\gameFiles\\RomFS"

Optional:

    python bin_census.py "D:\\...\\RomFS" --output "D:\\...\\research"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re

from pathlib import Path
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HEADER_SIZE = 128
PREFIX_SIZE = 16
STRING_MIN_LENGTH = 4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_size(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value):,} {unit}"

            return f"{value:,.2f} {unit}"

        value /= 1024

    return f"{size:,} B"


def hex_bytes(data: bytes) -> str:
    return data.hex(" ").upper()


def ascii_preview(data: bytes) -> str:
    return "".join(
        chr(b) if 32 <= b <= 126 else "."
        for b in data
    )


def first_nonzero_offset(data: bytes):
    for i, value in enumerate(data):
        if value != 0:
            return i

    return None


def zero_prefix_length(data: bytes) -> int:
    """
    Number of consecutive zero bytes at the start of the file.
    """

    offset = first_nonzero_offset(data)

    if offset is None:
        return len(data)

    return offset


def trailing_zero_count(data: bytes) -> int:
    """
    Number of consecutive zero bytes at EOF.
    """

    count = 0

    for value in reversed(data):
        if value == 0:
            count += 1
        else:
            break

    return count


def shannon_entropy(data: bytes) -> float:
    """
    Shannon entropy in bits/byte.

    Rough interpretation:
        ~0       very repetitive
        ~8       high entropy
    """

    if not data:
        return 0.0

    counts = Counter(data)
    length = len(data)

    entropy = 0.0

    for count in counts.values():
        probability = count / length
        entropy -= probability * math.log2(probability)

    return entropy


def extract_ascii_strings(data: bytes, minimum=STRING_MIN_LENGTH):
    """
    Extract printable ASCII strings.
    """

    pattern = rb"[\x20-\x7E]{" + str(minimum).encode() + rb",}"

    return [
        match.decode("ascii", errors="replace")
        for match in re.findall(pattern, data)
    ]


def first_nonzero_bytes(data: bytes, count=16) -> bytes:
    """
    Return bytes starting at the first non-zero byte.
    """

    offset = first_nonzero_offset(data)

    if offset is None:
        return b""

    return data[offset:offset + count]


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def filename_family(path: Path) -> str:
    """
    Normalize numeric portions of filenames.

    Examples:

        eff_00.bin -> eff_#.bin
        eff_01.bin -> eff_#.bin
        demo123.bin -> demo#.bin

    This helps reveal naming families.
    """

    name = path.name.lower()

    return re.sub(r"\d+", "#", name)


def directory_family(relative: Path) -> str:
    """
    Normalize numeric path components.

    Example:

        us/demo/002/demo
        us/demo/003/demo

    both become:

        us/demo/#/demo
    """

    parts = []

    for part in relative.parent.parts:
        parts.append(re.sub(r"\d+", "#", part.lower()))

    return "/".join(parts)


# ---------------------------------------------------------------------------
# Individual analysis
# ---------------------------------------------------------------------------

def analyze_file(path: Path, root: Path):

    data = path.read_bytes()
    relative = path.relative_to(root)

    size = len(data)

    nonzero_offset = first_nonzero_offset(data)

    if nonzero_offset is None:
        nonzero_offset_text = "NONE"
    else:
        nonzero_offset_text = str(nonzero_offset)

    prefix = data[:PREFIX_SIZE]

    nonzero_prefix = first_nonzero_bytes(
        data,
        PREFIX_SIZE
    )

    strings = extract_ascii_strings(data)

    # First 128 bytes are useful for later manual inspection.
    header = data[:HEADER_SIZE]

    return {
        "path": str(relative),
        "filename": path.name,
        "filename_family": filename_family(path),
        "directory_family": directory_family(relative),

        "size": size,
        "size_hex": f"0x{size:X}",

        "size_mod_4": size % 4,
        "size_mod_16": size % 16,
        "size_mod_32": size % 32,

        "zero_prefix": zero_prefix_length(data),
        "first_nonzero_offset": nonzero_offset_text,

        "first_16_hex": hex_bytes(prefix),
        "first_nonzero_16_hex": hex_bytes(nonzero_prefix),

        "header_128_hex": hex_bytes(header),
        "header_ascii": ascii_preview(header),

        "trailing_zeros": trailing_zero_count(data),

        "entropy": round(shannon_entropy(data), 4),

        "ascii_string_count": len(strings),

        "sha1": sha1(data),

        "_strings": strings,
    }


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan(root: Path):

    files = sorted(
        (
            p for p in root.rglob("*")
            if p.is_file()
            and p.suffix.lower() == ".bin"
        ),
        key=lambda p: str(p).lower()
    )

    print()
    print("=" * 72)
    print("KID ICARUS: UPRISING - BIN STRUCTURAL CENSUS")
    print("=" * 72)
    print(f"Root      : {root}")
    print(f"BIN files : {len(files):,}")
    print()

    rows = []

    for index, path in enumerate(files, 1):

        try:
            rows.append(
                analyze_file(path, root)
            )

        except Exception as exc:
            print()
            print(f"[ERROR] {path}")
            print(f"        {exc}")

        if index % 50 == 0 or index == len(files):
            print(
                f"\rAnalyzing: {index:,}/{len(files):,}",
                end="",
                flush=True
            )

    print()
    print()

    return rows


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def write_csv(rows, output: Path):

    fields = [
        "path",
        "filename",
        "filename_family",
        "directory_family",

        "size",
        "size_hex",

        "size_mod_4",
        "size_mod_16",
        "size_mod_32",

        "zero_prefix",
        "first_nonzero_offset",

        "first_16_hex",
        "first_nonzero_16_hex",

        "header_128_hex",
        "header_ascii",

        "trailing_zeros",
        "entropy",

        "ascii_string_count",
        "sha1",
    ]

    with output.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        for row in rows:
            writer.writerow({
                field: row[field]
                for field in fields
            })


# ---------------------------------------------------------------------------
# Strings report
# ---------------------------------------------------------------------------

def write_strings(rows, output: Path):

    with output.open(
        "w",
        encoding="utf-8",
        errors="replace"
    ) as f:

        for row in rows:

            strings = row["_strings"]

            if not strings:
                continue

            f.write("=" * 78 + "\n")
            f.write(row["path"] + "\n")
            f.write(
                f"Size: {row['size']:,} bytes | "
                f"Strings: {len(strings):,}\n"
            )
            f.write("=" * 78 + "\n")

            for string in strings:
                f.write(string + "\n")

            f.write("\n")


# ---------------------------------------------------------------------------
# Human-readable structural report
# ---------------------------------------------------------------------------

def write_groups(rows, output: Path, root: Path):

    total_size = sum(row["size"] for row in rows)

    with output.open(
        "w",
        encoding="utf-8"
    ) as f:

        def out(text=""):
            f.write(text + "\n")

        out("=" * 78)
        out("KID ICARUS: UPRISING - BIN STRUCTURAL CENSUS")
        out("=" * 78)
        out()
        out(f"Root       : {root}")
        out(f"BIN files  : {len(rows):,}")
        out(f"Total size : {format_size(total_size)}")
        out()

        # ===============================================================
        # Filename families
        # ===============================================================

        out("=" * 78)
        out("FILENAME FAMILIES")
        out("=" * 78)
        out()

        families = defaultdict(list)

        for row in rows:
            families[row["filename_family"]].append(row)

        for family, group in sorted(
            families.items(),
            key=lambda item: len(item[1]),
            reverse=True
        ):

            group_size = sum(
                row["size"]
                for row in group
            )

            out(
                f"{len(group):>5,} files | "
                f"{format_size(group_size):>12} | "
                f"{family}"
            )

            for example in group[:5]:
                out(
                    f"        {example['path']}"
                )

            out()

        # ===============================================================
        # Directory families
        # ===============================================================

        out("=" * 78)
        out("DIRECTORY FAMILIES")
        out("=" * 78)
        out()

        directories = defaultdict(list)

        for row in rows:
            directories[row["directory_family"]].append(row)

        for directory, group in sorted(
            directories.items(),
            key=lambda item: len(item[1]),
            reverse=True
        ):

            out(
                f"{len(group):>5,} files | {directory}"
            )

            names = Counter(
                row["filename_family"]
                for row in group
            )

            for name, count in names.most_common(10):
                out(
                    f"        {count:>5,} x {name}"
                )

            out()

        # ===============================================================
        # Size groups
        # ===============================================================

        out("=" * 78)
        out("MOST COMMON EXACT FILE SIZES")
        out("=" * 78)
        out()

        sizes = defaultdict(list)

        for row in rows:
            sizes[row["size"]].append(row)

        repeated_sizes = [
            (size, group)
            for size, group in sizes.items()
            if len(group) > 1
        ]

        repeated_sizes.sort(
            key=lambda item: len(item[1]),
            reverse=True
        )

        for size, group in repeated_sizes[:100]:

            out(
                f"{len(group):>5,} files | "
                f"{size:>10,} bytes | "
                f"0x{size:X}"
            )

            for example in group[:5]:
                out(
                    f"        {example['path']}"
                )

            out()

        # ===============================================================
        # Zero-prefix distribution
        # ===============================================================

        out("=" * 78)
        out("ZERO-PREFIX LENGTHS")
        out("=" * 78)
        out()

        zero_prefixes = Counter(
            row["zero_prefix"]
            for row in rows
        )

        for length, count in zero_prefixes.most_common():

            out(
                f"{count:>5,} files | "
                f"first non-zero byte at 0x{length:X} "
                f"({length})"
            )

        out()

        # ===============================================================
        # First non-zero prefixes
        # ===============================================================

        out("=" * 78)
        out("FIRST NON-ZERO 16-BYTE PREFIXES")
        out("=" * 78)
        out()

        prefixes = defaultdict(list)

        for row in rows:
            prefixes[
                row["first_nonzero_16_hex"]
            ].append(row)

        sorted_prefixes = sorted(
            prefixes.items(),
            key=lambda item: len(item[1]),
            reverse=True
        )

        for prefix, group in sorted_prefixes[:200]:

            out(
                f"{len(group):>5,} files | "
                f"{prefix or '(all zero)'}"
            )

            for example in group[:5]:
                out(
                    f"        {example['path']}"
                )

            out()

        # ===============================================================
        # Entropy ranges
        # ===============================================================

        out("=" * 78)
        out("ENTROPY DISTRIBUTION")
        out("=" * 78)
        out()

        entropy_buckets = Counter()

        for row in rows:

            entropy = row["entropy"]

            if entropy < 1:
                bucket = "0.0 - 0.99"

            elif entropy < 2:
                bucket = "1.0 - 1.99"

            elif entropy < 3:
                bucket = "2.0 - 2.99"

            elif entropy < 4:
                bucket = "3.0 - 3.99"

            elif entropy < 5:
                bucket = "4.0 - 4.99"

            elif entropy < 6:
                bucket = "5.0 - 5.99"

            elif entropy < 7:
                bucket = "6.0 - 6.99"

            else:
                bucket = "7.0 - 8.0"

            entropy_buckets[bucket] += 1

        bucket_order = [
            "0.0 - 0.99",
            "1.0 - 1.99",
            "2.0 - 2.99",
            "3.0 - 3.99",
            "4.0 - 4.99",
            "5.0 - 5.99",
            "6.0 - 6.99",
            "7.0 - 8.0",
        ]

        for bucket in bucket_order:
            out(
                f"{bucket:<12} : "
                f"{entropy_buckets[bucket]:>5,} files"
            )

        out()

        # ===============================================================
        # String counts
        # ===============================================================

        out("=" * 78)
        out("FILES WITH MOST ASCII STRINGS")
        out("=" * 78)
        out()

        by_strings = sorted(
            rows,
            key=lambda row: row["ascii_string_count"],
            reverse=True
        )

        for row in by_strings[:50]:

            if row["ascii_string_count"] == 0:
                break

            out(
                f"{row['ascii_string_count']:>5,} strings | "
                f"{row['size']:>10,} bytes | "
                f"{row['path']}"
            )

        out()

        # ===============================================================
        # Exact duplicates
        # ===============================================================

        out("=" * 78)
        out("EXACT DUPLICATE FILES")
        out("=" * 78)
        out()

        hashes = defaultdict(list)

        for row in rows:
            hashes[row["sha1"]].append(row)

        duplicates = [
            (digest, group)
            for digest, group in hashes.items()
            if len(group) > 1
        ]

        duplicates.sort(
            key=lambda item: len(item[1]),
            reverse=True
        )

        if not duplicates:
            out("No exact duplicates found.")

        else:

            for digest, group in duplicates:

                out(
                    f"{len(group):>5,} identical files | "
                    f"{group[0]['size']:,} bytes"
                )

                out(
                    f"        SHA1 {digest}"
                )

                for row in group[:20]:
                    out(
                        f"        {row['path']}"
                    )

                if len(group) > 20:
                    out(
                        f"        ... "
                        f"{len(group) - 20:,} more"
                    )

                out()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Analyze structural patterns in "
            "Kid Icarus: Uprising .bin files."
        )
    )

    parser.add_argument(
        "root",
        help="Path to the original RomFS directory"
    )

    parser.add_argument(
        "--output",
        default=".",
        help="Output directory (default: current directory)"
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output).resolve()

    if not root.exists():
        raise SystemExit(
            f"Directory does not exist: {root}"
        )

    if not root.is_dir():
        raise SystemExit(
            f"Not a directory: {root}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    rows = scan(root)

    if not rows:
        raise SystemExit(
            "No .bin files found."
        )

    csv_path = output_dir / "bin_census.csv"
    groups_path = output_dir / "bin_groups.txt"
    strings_path = output_dir / "bin_strings.txt"

    write_csv(
        rows,
        csv_path
    )

    write_groups(
        rows,
        groups_path,
        root
    )

    write_strings(
        rows,
        strings_path
    )

    print("=" * 72)
    print("DONE")
    print("=" * 72)
    print(f"BIN files     : {len(rows):,}")
    print(
        f"Total size    : "
        f"{format_size(sum(r['size'] for r in rows))}"
    )
    print()
    print(f"CSV           : {csv_path}")
    print(f"Groups        : {groups_path}")
    print(f"Strings       : {strings_path}")
    print()


if __name__ == "__main__":
    main()