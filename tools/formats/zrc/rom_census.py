#!/usr/bin/env python3

"""
Kid Icarus: Uprising - ROM Format Census
=========================================

Recursively scans a directory and produces:

    rom_census.csv
        One row per file.

    rom_signatures.txt
        Human-readable summary grouped by extension and detected format.

Usage:
    python rom_census.py "D:\\Games\\Kid icarus\\ROM\\gameFiles\\RomFS"

The scanner DOES NOT modify any scanned files.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# Known signatures
# ---------------------------------------------------------------------------

# Exact magic at offset 0.
MAGICS = {
    b"darc": "DARC archive",
    b"CGFX": "CGFX / BCRES graphics",
    b"CSAR": "CTR Sound Archive (BCSAR/CSAR)",
    b"CSTM": "CTR Stream Audio (BCSTM)",
    b"CWAV": "CTR Wave Audio (BCWAV)",
    b"CBMD": "CTR Banner Model Data",
    b"CLIM": "CTR Image (BCLIM)",
    b"FLIM": "CTR Image (BFLIM)",
    b"CTPK": "CTR Texture Package",
    b"SARC": "SARC archive",
    b"Yaz0": "Yaz0 compressed data",
    b"PSLB": "PSLB (KIU structured data)",
    b"FRES": "Binary Cafe Resource (BFRES)",
    b"DVLB": "CTR shader binary",
}


def detect_format(header: bytes, extension: str) -> str:
    """
    Guess a file format from its header.

    This deliberately stays conservative:
    unknown data remains unknown instead of being guessed.
    """

    if not header:
        return "Empty file"

    # Exact known 4-byte signatures
    if len(header) >= 4:
        magic4 = header[:4]

        if magic4 in MAGICS:
            return MAGICS[magic4]

    # Nintendo LZ compression types.
    #
    # 0x10 = LZ10
    # 0x11 = LZ11
    #
    # We already established that KIU .zrc files use LZ11,
    # but don't automatically call every LZ11 file a ZRC.
    if header[0] == 0x10:
        return "Nintendo LZ10 compressed data"

    if header[0] == 0x11:
        return "Nintendo LZ11 compressed data"

    return "Unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_extension(path: Path) -> str:
    ext = path.suffix.lower()

    if not ext:
        return "(no extension)"

    return ext


def printable_ascii(data: bytes) -> str:
    """
    Show printable bytes as ASCII and everything else as dots.
    """

    return "".join(
        chr(b) if 32 <= b <= 126 else "."
        for b in data
    )


def format_size(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value):,} {unit}"
            return f"{value:,.2f} {unit}"

        value /= 1024

    return f"{size:,} B"


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan(root: Path):
    rows = []

    files = sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: str(p).lower()
    )

    total = len(files)

    print()
    print("=" * 72)
    print("KID ICARUS: UPRISING - ROM FORMAT CENSUS")
    print("=" * 72)
    print(f"Root  : {root}")
    print(f"Files : {total:,}")
    print()

    for index, path in enumerate(files, 1):

        try:
            size = path.stat().st_size

            with path.open("rb") as f:
                header = f.read(32)

            relative = path.relative_to(root)
            extension = get_extension(path)
            detected = detect_format(header, extension)

            rows.append({
                "path": str(relative),
                "extension": extension,
                "size": size,
                "magic_hex": header[:4].hex(" ").upper(),
                "header_32_hex": header.hex(" ").upper(),
                "header_ascii": printable_ascii(header),
                "detected_format": detected,
            })

            if index % 250 == 0 or index == total:
                print(
                    f"\rScanning: {index:,}/{total:,}",
                    end="",
                    flush=True
                )

        except Exception as exc:
            print()
            print(f"[ERROR] {path}")
            print(f"        {exc}")

            rows.append({
                "path": str(path.relative_to(root)),
                "extension": get_extension(path),
                "size": "",
                "magic_hex": "",
                "header_32_hex": "",
                "header_ascii": "",
                "detected_format": f"ERROR: {exc}",
            })

    print()
    print()

    return rows


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def write_csv(rows, output: Path):

    fields = [
        "path",
        "extension",
        "size",
        "magic_hex",
        "header_32_hex",
        "header_ascii",
        "detected_format",
    ]

    with output.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def write_summary(rows, output: Path, root: Path):

    extension_groups = defaultdict(list)

    for row in rows:
        extension_groups[row["extension"]].append(row)

    total_files = len(rows)

    total_bytes = sum(
        row["size"]
        for row in rows
        if isinstance(row["size"], int)
    )

    # Sort extensions by total bytes, largest first.
    extension_order = sorted(
        extension_groups,
        key=lambda ext: sum(
            r["size"]
            for r in extension_groups[ext]
            if isinstance(r["size"], int)
        ),
        reverse=True
    )

    with output.open("w", encoding="utf-8") as f:

        def out(text=""):
            f.write(text + "\n")

        out("=" * 78)
        out("KID ICARUS: UPRISING - ROM FORMAT CENSUS")
        out("=" * 78)
        out()
        out(f"Root       : {root}")
        out(f"Total files: {total_files:,}")
        out(f"Total size : {format_size(total_bytes)}")
        out()

        # ---------------------------------------------------------------
        # Global detected formats
        # ---------------------------------------------------------------

        out("=" * 78)
        out("DETECTED FORMATS")
        out("=" * 78)
        out()

        detected_counter = Counter(
            row["detected_format"]
            for row in rows
        )

        for detected, count in detected_counter.most_common():

            bytes_for_type = sum(
                row["size"]
                for row in rows
                if row["detected_format"] == detected
                and isinstance(row["size"], int)
            )

            out(
                f"{count:>7,} files | "
                f"{format_size(bytes_for_type):>12} | "
                f"{detected}"
            )

        out()

        # ---------------------------------------------------------------
        # Extension groups
        # ---------------------------------------------------------------

        out("=" * 78)
        out("BY EXTENSION")
        out("=" * 78)
        out()

        for extension in extension_order:

            group = extension_groups[extension]

            group_size = sum(
                row["size"]
                for row in group
                if isinstance(row["size"], int)
            )

            out("-" * 78)
            out(
                f"{extension} | "
                f"{len(group):,} files | "
                f"{format_size(group_size)}"
            )
            out("-" * 78)

            # Group by exact first four bytes AND detected format.
            signature_groups = defaultdict(list)

            for row in group:
                key = (
                    row["magic_hex"],
                    row["detected_format"],
                )
                signature_groups[key].append(row)

            sorted_signatures = sorted(
                signature_groups.items(),
                key=lambda item: len(item[1]),
                reverse=True
            )

            for (magic_hex, detected), signature_rows in sorted_signatures:

                magic_display = magic_hex or "(none)"

                out()
                out(
                    f"  {len(signature_rows):>6,} x "
                    f"{magic_display:<11} "
                    f"{detected}"
                )

                # Up to 3 example paths for each signature.
                for example in signature_rows[:3]:
                    out(f"           e.g. {example['path']}")

            out()

        # ---------------------------------------------------------------
        # Unknown signatures
        # ---------------------------------------------------------------

        out("=" * 78)
        out("UNKNOWN SIGNATURE GROUPS")
        out("=" * 78)
        out()

        unknown_groups = defaultdict(list)

        for row in rows:
            if row["detected_format"] == "Unknown":
                unknown_groups[row["magic_hex"]].append(row)

        sorted_unknown = sorted(
            unknown_groups.items(),
            key=lambda item: len(item[1]),
            reverse=True
        )

        if not sorted_unknown:
            out("No unknown signatures.")
        else:

            for magic, group in sorted_unknown:

                total_group_size = sum(
                    row["size"]
                    for row in group
                    if isinstance(row["size"], int)
                )

                extensions = Counter(
                    row["extension"]
                    for row in group
                )

                ext_text = ", ".join(
                    f"{ext}={count}"
                    for ext, count in extensions.most_common()
                )

                out(
                    f"{len(group):>6,} files | "
                    f"{format_size(total_group_size):>12} | "
                    f"{magic or '(none)':<11} | "
                    f"{ext_text}"
                )

                for example in group[:3]:
                    out(
                        f"         {example['path']}"
                    )

                out()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Scan a Kid Icarus: Uprising RomFS and classify file signatures."
    )

    parser.add_argument(
        "root",
        help="Path to the RomFS directory"
    )

    parser.add_argument(
        "--output",
        help="Output directory (default: current directory)",
        default="."
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output).resolve()

    if not root.exists():
        raise SystemExit(f"Directory does not exist: {root}")

    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = scan(root)

    csv_path = output_dir / "rom_census.csv"
    summary_path = output_dir / "rom_signatures.txt"

    write_csv(rows, csv_path)
    write_summary(rows, summary_path, root)

    total_bytes = sum(
        row["size"]
        for row in rows
        if isinstance(row["size"], int)
    )

    print("=" * 72)
    print("DONE")
    print("=" * 72)
    print(f"Files scanned : {len(rows):,}")
    print(f"Data scanned  : {format_size(total_bytes)}")
    print()
    print(f"CSV           : {csv_path}")
    print(f"Summary       : {summary_path}")
    print()


if __name__ == "__main__":
    main()