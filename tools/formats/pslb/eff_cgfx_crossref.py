from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import csv
import hashlib
import re
import struct
import sys
import time


# -----------------------------
# EFF parsing
# -----------------------------

MODEL_REC = 0x5C
PARTICLE_REC = 0x54
TRIGGER_REC = 0x50

SECTION_RECORD_SIZE = {
    "effectModelData_": MODEL_REC,
    "effectParticleData_": PARTICLE_REC,
    "effectTriggerData_": TRIGGER_REC,
}

ASCII_Z_RE = re.compile(rb"([\x20-\x7E]{3,})\x00")


def align4(x: int) -> int:
    return (x + 3) & ~3


def u32(data: bytes | memoryview, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def read_cstr(data: bytes | memoryview, off: int) -> tuple[str, int]:
    end = off
    while end < len(data) and data[end] != 0:
        end += 1
    if end >= len(data):
        raise ValueError(f"unterminated section name at 0x{off:X}")
    raw = bytes(data[off:end])
    return raw.decode("ascii"), end + 1


def fixed_ascii(raw: bytes | memoryview) -> str:
    raw = bytes(raw)
    raw = raw.split(b"\x00", 1)[0]
    if not raw:
        return ""
    try:
        s = raw.decode("ascii")
    except UnicodeDecodeError:
        return ""
    if any(ord(c) < 0x20 or ord(c) > 0x7E for c in s):
        return ""
    return s


def parse_eff(data: bytes):
    if len(data) < 8:
        raise ValueError("too small")

    field0 = u32(data, 0)
    eff_type = u32(data, 4)

    if field0 != 0:
        raise ValueError(f"unexpected header field0={field0}")
    if eff_type not in (2, 3):
        raise ValueError(f"unexpected EFF type={eff_type}")

    off = 8
    sections = []

    while off < len(data):
        name, after_name = read_cstr(data, off)
        size_off = align4(after_name)

        if size_off + 4 > len(data):
            raise ValueError(f"truncated section size for {name!r}")

        size = u32(data, size_off)
        data_off = size_off + 4
        end = data_off + size

        if end > len(data):
            raise ValueError(f"section {name!r} exceeds file")

        sections.append((name, data_off, size))
        off = end

    if off != len(data):
        raise ValueError("parser did not end exactly at EOF")

    return eff_type, sections


def section_kind(name: str) -> str | None:
    for prefix in SECTION_RECORD_SIZE:
        if name.startswith(prefix):
            return prefix
    return None


def extract_eff_candidates(data: bytes, virtual_path: str):
    eff_type, sections = parse_eff(data)
    rows = []

    for section_name, data_off, size in sections:
        kind = section_kind(section_name)
        if kind is None:
            continue

        rec_size = SECTION_RECORD_SIZE[kind]
        if size % rec_size != 0:
            raise ValueError(
                f"{section_name}: size 0x{size:X} not divisible by 0x{rec_size:X}"
            )

        count = size // rec_size

        for i in range(count):
            rec_off = data_off + i * rec_size
            rec = memoryview(data)[rec_off:rec_off + rec_size]

            if kind == "effectModelData_":
                # +0x04 char[0x1C] is the strongest model/effect name-ish field.
                fields = [
                    ("model_name", 0x04, 0x1C),
                    ("model_s20", 0x20, 0x08),
                    ("model_s28", 0x28, 0x08),
                    ("model_s30", 0x30, 0x08),
                    ("model_s38", 0x38, 0x08),
                    ("model_s40", 0x40, 0x08),
                    ("model_s48", 0x48, 0x08),
                ]
                for field, start, length in fields:
                    value = fixed_ascii(rec[start:start+length])
                    if value:
                        rows.append({
                            "eff_path": virtual_path,
                            "eff_type": eff_type,
                            "section": section_name,
                            "record_kind": "model",
                            "record_index": i,
                            "field": field,
                            "value": value,
                        })

            elif kind == "effectParticleData_":
                fields = [
                    ("particle_name", 0x00, 0x20),
                    ("particle_mode", 0x20, 0x08),
                    ("particle_node", 0x2C, 0x14),
                ]
                for field, start, length in fields:
                    value = fixed_ascii(rec[start:start+length])
                    if value:
                        rows.append({
                            "eff_path": virtual_path,
                            "eff_type": eff_type,
                            "section": section_name,
                            "record_kind": "particle",
                            "record_index": i,
                            "field": field,
                            "value": value,
                        })

            elif kind == "effectTriggerData_":
                # Trigger target section reference at +0x2C char[0x20].
                value = fixed_ascii(rec[0x2C:0x4C])
                if value:
                    rows.append({
                        "eff_path": virtual_path,
                        "eff_type": eff_type,
                        "section": section_name,
                        "record_kind": "trigger",
                        "record_index": i,
                        "field": "trigger_target_section",
                        "value": value,
                    })

    return rows


# -----------------------------
# DARC / LZ11 traversal
# -----------------------------

def magic4(data) -> bytes:
    return bytes(data[:4]) if len(data) >= 4 else bytes(data)


def u16_mv(data, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32_mv(data, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def read_utf16z(data, off: int) -> str:
    if off < 0 or off >= len(data):
        raise ValueError(f"name offset out of range: 0x{off:X}")
    end = off
    while end + 1 < len(data):
        if data[end] == 0 and data[end + 1] == 0:
            return bytes(data[off:end]).decode("utf-16le")
        end += 2
    raise ValueError(f"unterminated UTF-16LE name at 0x{off:X}")


def iter_darc_files(data):
    if len(data) < 0x1C or magic4(data) != b"darc":
        raise ValueError("not DARC")
    if bytes(data[4:6]) != b"\xFF\xFE":
        raise ValueError("unsupported DARC BOM")

    table_offset = u32_mv(data, 0x10)
    table_length = u32_mv(data, 0x14)
    entry_count = u32_mv(data, table_offset + 8)

    entries_end = table_offset + entry_count * 12
    table_end = table_offset + table_length

    if entry_count <= 0 or entries_end > table_end or table_end > len(data):
        raise ValueError("invalid DARC table bounds")

    name_table_start = entries_end
    stack: list[tuple[int, str]] = []

    for index in range(1, entry_count):
        while stack and index >= stack[-1][0]:
            stack.pop()

        eoff = table_offset + index * 12
        name_flags = u32_mv(data, eoff)
        field1 = u32_mv(data, eoff + 4)
        field2 = u32_mv(data, eoff + 8)

        is_dir = bool(name_flags & 0x01000000)
        name_offset = name_flags & 0x00FFFFFF
        name = read_utf16z(data, name_table_start + name_offset)

        parent = [x[1] for x in stack]
        full = "/".join(parent + [name]) if parent else name

        if is_dir:
            if field2 <= index or field2 > entry_count:
                raise ValueError("invalid DARC subtree end")
            stack.append((field2, name))
            continue

        if field1 + field2 > len(data):
            raise ValueError("DARC file entry exceeds archive")

        yield full, field1, field2


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

    if out_size <= 0 or out_size > 512 * 1024 * 1024:
        raise ValueError("implausible LZ11 size")

    out = bytearray()

    while len(out) < out_size:
        if src >= len(data):
            raise ValueError("EOF reading flags")

        flags = data[src]
        src += 1

        for bit in range(8):
            if len(out) >= out_size:
                break

            if not (flags & (0x80 >> bit)):
                if src >= len(data):
                    raise ValueError("EOF literal")
                out.append(data[src])
                src += 1
                continue

            if src + 1 >= len(data):
                raise ValueError("EOF backref")

            b1 = data[src]
            b2 = data[src + 1]
            src += 2
            indicator = b1 >> 4

            if indicator == 0:
                if src >= len(data):
                    raise ValueError("EOF 3-byte ref")
                b3 = data[src]
                src += 1
                length = (((b1 & 0x0F) << 4) | (b2 >> 4)) + 0x11
                displacement = ((b2 & 0x0F) << 8) | b3

            elif indicator == 1:
                if src + 1 >= len(data):
                    raise ValueError("EOF 4-byte ref")
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

            pos = len(out) - displacement - 1
            if pos < 0:
                raise ValueError("invalid displacement")

            for _ in range(length):
                if len(out) >= out_size:
                    break
                out.append(out[pos])
                pos += 1

    return bytes(out)


# -----------------------------
# Cross-reference
# -----------------------------

def scan_cgfx_strings(romfs: Path, targets: set[str], max_depth: int):
    hits = []
    cgfx_count = 0
    false11 = 0
    errors = []

    def inspect(data, physical: Path, virtual: str, depth: int):
        nonlocal cgfx_count, false11

        if depth > max_depth:
            errors.append(f"{virtual}: max depth exceeded")
            return

        head = magic4(data)

        if head == b"CGFX":
            cgfx_count += 1
            blob = bytes(data)
            strings = {
                m.group(1).decode("ascii")
                for m in ASCII_Z_RE.finditer(blob)
            }
            found = strings & targets
            if found:
                sha1 = hashlib.sha1(blob).hexdigest()
                rel = physical.relative_to(romfs).as_posix()
                for value in found:
                    hits.append({
                        "value": value,
                        "physical_path": rel,
                        "cgfx_virtual_path": virtual,
                        "cgfx_sha1": sha1,
                        "cgfx_size": len(blob),
                    })
            return

        if head == b"darc":
            try:
                for name, off, size in iter_darc_files(data):
                    entry = memoryview(data)[off:off+size]
                    eh = magic4(entry)
                    if (
                        eh == b"CGFX"
                        or eh == b"darc"
                        or (len(entry) and entry[0] == 0x11)
                    ):
                        inspect(
                            entry,
                            physical,
                            virtual + "::" + name,
                            depth + 1,
                        )
            except Exception as exc:
                errors.append(f"{virtual}: DARC error: {exc}")
            return

        if len(data) and data[0] == 0x11:
            try:
                dec = lz11_decompress(data)
            except Exception:
                false11 += 1
                return
            inspect(dec, physical, virtual + "::[LZ11]", depth + 1)

    files = sorted(p for p in romfs.rglob("*") if p.is_file())
    started = time.perf_counter()

    for i, path in enumerate(files, 1):
        try:
            with path.open("rb") as f:
                head = f.read(4)

            if head == b"CGFX" or head == b"darc" or head[:1] == b"\x11":
                inspect(
                    path.read_bytes(),
                    path,
                    path.relative_to(romfs).as_posix(),
                    0,
                )

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            errors.append(f"{path}: {exc}")

        if i % 500 == 0 or i == len(files):
            elapsed = time.perf_counter() - started
            print(
                f"[CGFX {i}/{len(files)}] {elapsed:6.1f}s "
                f"resources={cgfx_count} matches={len(hits)} errors={len(errors)}",
                flush=True,
            )

    return hits, cgfx_count, false11, errors


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Extract structured strings from KIU eff_00.bin files and "
            "cross-reference them against strings inside CGFX resources."
        )
    )
    ap.add_argument("romfs", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("EFF_CGFX_CROSSREF"),
    )
    ap.add_argument("--max-depth", type=int, default=16)
    args = ap.parse_args()

    romfs = args.romfs.resolve()
    out = args.output.resolve()

    if not romfs.is_dir():
        print(f"ERROR: not a directory: {romfs}", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    eff_paths = sorted(
        p for p in romfs.rglob("eff_00.bin") if p.is_file()
    )

    print(f"Found {len(eff_paths)} eff_00.bin files")

    eff_rows = []
    eff_errors = []

    for path in eff_paths:
        try:
            rel = path.relative_to(romfs).as_posix()
            rows = extract_eff_candidates(path.read_bytes(), rel)
            eff_rows.extend(rows)
        except Exception as exc:
            eff_errors.append((str(path), str(exc)))

    candidate_counts = Counter(r["value"] for r in eff_rows)
    field_counts = Counter(r["field"] for r in eff_rows)

    # Skip obvious control tokens from CGFX target search.
    skip_values = {
        "follow",
        "none",
    }

    targets = {
        r["value"]
        for r in eff_rows
        if len(r["value"]) >= 3 and r["value"] not in skip_values
    }

    print(f"EFF candidate strings : {len(eff_rows)}")
    print(f"Unique target strings : {len(targets)}")
    print(f"EFF parse failures    : {len(eff_errors)}")
    print()

    hits, cgfx_count, false11, cgfx_errors = scan_cgfx_strings(
        romfs,
        targets,
        args.max_depth,
    )

    hits_by_value = defaultdict(list)
    for h in hits:
        hits_by_value[h["value"]].append(h)

    refs_csv = out / "eff_reference_strings.csv"
    with refs_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "eff_path",
                "eff_type",
                "section",
                "record_kind",
                "record_index",
                "field",
                "value",
            ],
        )
        w.writeheader()
        w.writerows(eff_rows)

    matches_csv = out / "eff_to_cgfx_matches.csv"
    match_rows = []

    with matches_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "eff_path",
            "eff_type",
            "section",
            "record_kind",
            "record_index",
            "field",
            "value",
            "cgfx_virtual_path",
            "cgfx_sha1",
            "cgfx_size",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        seen = set()

        for ref in eff_rows:
            for hit in hits_by_value.get(ref["value"], []):
                key = (
                    ref["eff_path"],
                    ref["section"],
                    ref["record_kind"],
                    ref["record_index"],
                    ref["field"],
                    ref["value"],
                    hit["cgfx_virtual_path"],
                    hit["cgfx_sha1"],
                )
                if key in seen:
                    continue
                seen.add(key)

                row = {
                    **ref,
                    "cgfx_virtual_path": hit["cgfx_virtual_path"],
                    "cgfx_sha1": hit["cgfx_sha1"],
                    "cgfx_size": hit["cgfx_size"],
                }
                w.writerow(row)
                match_rows.append(row)

    matched_values = set(hits_by_value)
    unmatched_values = sorted(targets - matched_values)

    unmatched_txt = out / "unmatched_eff_strings.txt"
    unmatched_txt.write_text(
        "\n".join(unmatched_values) + ("\n" if unmatched_values else ""),
        encoding="utf-8",
    )

    summary = out / "eff_cgfx_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("KIU EFF -> CGFX CROSS-REFERENCE\n")
        f.write("=" * 88 + "\n\n")

        f.write(f"EFF files found          : {len(eff_paths)}\n")
        f.write(f"EFF parse failures       : {len(eff_errors)}\n")
        f.write(f"EFF string occurrences   : {len(eff_rows)}\n")
        f.write(f"Unique EFF target strings: {len(targets)}\n")
        f.write(f"CGFX resources scanned   : {cgfx_count}\n")
        f.write(f"Values found in CGFX     : {len(matched_values)}\n")
        f.write(f"Values not found in CGFX : {len(unmatched_values)}\n")
        f.write(f"Expanded match rows      : {len(match_rows)}\n")
        f.write(f"0x11 false positives     : {false11}\n")
        f.write(f"CGFX scan errors         : {len(cgfx_errors)}\n\n")

        f.write("EFF FIELD COUNTS\n")
        f.write("-" * 88 + "\n")
        for field, count in field_counts.most_common():
            f.write(f"{field:24s} {count:8d}\n")

        f.write("\nMATCHED VALUES BY FIELD\n")
        f.write("-" * 88 + "\n")
        by_field = defaultdict(set)
        for row in match_rows:
            by_field[row["field"]].add(row["value"])
        for field in sorted(field_counts):
            f.write(
                f"{field:24s} "
                f"{len(by_field.get(field, set())):8d} unique matched values\n"
            )

        f.write("\nTOP MATCHED VALUES\n")
        f.write("-" * 88 + "\n")
        matched_counts = Counter(
            row["value"]
            for row in match_rows
        )
        for value, count in matched_counts.most_common(200):
            f.write(
                f"{count:8d} match rows | "
                f"{candidate_counts[value]:8d} EFF occurrences | "
                f"{value}\n"
            )

        if eff_errors:
            f.write("\nEFF PARSE FAILURES\n")
            f.write("-" * 88 + "\n")
            for path, err in eff_errors:
                f.write(f"{path}\n  {err}\n")

        if cgfx_errors:
            f.write("\nCGFX SCAN ERRORS\n")
            f.write("-" * 88 + "\n")
            for err in cgfx_errors:
                f.write(err + "\n")

    print()
    print("=" * 72)
    print("EFF -> CGFX CROSS-REFERENCE COMPLETE")
    print("=" * 72)
    print(f"EFF files        : {len(eff_paths)}")
    print(f"EFF failures     : {len(eff_errors)}")
    print(f"Unique strings   : {len(targets)}")
    print(f"CGFX scanned     : {cgfx_count}")
    print(f"Values matched   : {len(matched_values)}")
    print(f"Values unmatched : {len(unmatched_values)}")
    print(f"Match rows       : {len(match_rows)}")
    print(f"Scan errors      : {len(cgfx_errors)}")
    print()
    print(f"Summary : {summary}")
    print(f"Refs    : {refs_csv}")
    print(f"Matches : {matches_csv}")
    print(f"Missing : {unmatched_txt}")

    return 0 if not eff_errors and not cgfx_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
