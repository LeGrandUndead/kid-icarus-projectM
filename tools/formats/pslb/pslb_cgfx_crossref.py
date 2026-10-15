from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import argparse
import csv
import hashlib
import re
import struct
import sys
import time


# These are the PSLB keys we currently consider useful enough for a first
# graphics cross-reference pass. They are deliberately exact-key based rather
# than using the earlier broad heuristic categories.
GRAPHICS_KEYS = {
    "motifModelName_",
    "motionName_",
    "sModelName_",
    "modelName",
}


ASCII_Z_RE = re.compile(rb"([\x20-\x7E]{3,})\x00")


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

    # Correct semantics: byte offset into the UTF-16LE name table.
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


def load_pslb_references(path: Path):
    """
    Returns:
      targets: set[str]
      target_keys: value -> set(keys)
      refs: list of dicts with sha1/json_path/key/value
    """
    targets = set()
    target_keys = defaultdict(set)
    refs = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        required = {"sha1", "json_path", "key", "value"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"{path} is missing required columns: {sorted(missing)}"
            )

        for row in reader:
            key = row["key"]
            value = row["value"]

            if key not in GRAPHICS_KEYS:
                continue
            if not value:
                continue

            # CGFX names in this corpus are overwhelmingly ASCII.
            try:
                value.encode("ascii")
            except UnicodeEncodeError:
                continue

            targets.add(value)
            target_keys[value].add(key)
            refs.append({
                "sha1": row["sha1"],
                "json_path": row["json_path"],
                "key": key,
                "value": value,
            })

    return targets, target_keys, refs


def load_occurrences(path: Path):
    by_sha1 = defaultdict(list)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        required = {"sha1", "virtual_path"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"{path} is missing required columns: {sorted(missing)}"
            )

        for row in reader:
            by_sha1[row["sha1"]].append(row["virtual_path"])

    return by_sha1


class CgfxScanner:
    def __init__(self, root: Path, targets: set[str], max_depth: int):
        self.root = root
        self.targets = targets
        self.max_depth = max_depth

        self.cgfx_count = 0
        self.matches = []
        self.errors = []
        self.false_lz11 = 0

    def inspect_cgfx(self, data, physical_path: Path, virtual_path: str):
        self.cgfx_count += 1
        blob = bytes(data)

        # Extract null-terminated printable ASCII strings once, then intersect
        # with the PSLB reference values. This is far cheaper than searching
        # hundreds of names independently through every CGFX blob.
        strings = {
            m.group(1).decode("ascii")
            for m in ASCII_Z_RE.finditer(blob)
        }

        found = strings & self.targets
        if not found:
            return

        cgfx_sha1 = hashlib.sha1(blob).hexdigest()
        physical_rel = physical_path.relative_to(self.root).as_posix()

        for value in sorted(found):
            self.matches.append({
                "value": value,
                "physical_path": physical_rel,
                "cgfx_virtual_path": virtual_path,
                "cgfx_sha1": cgfx_sha1,
                "cgfx_size": len(blob),
            })

    def inspect(self, data, physical_path: Path, virtual_path: str, depth: int):
        if depth > self.max_depth:
            self.errors.append(f"{virtual_path}: max depth exceeded")
            return

        head = magic4(data)

        if head == b"CGFX":
            self.inspect_cgfx(data, physical_path, virtual_path)
            return

        if head == b"darc":
            try:
                for name, off, size in iter_darc_files(data):
                    entry = memoryview(data)[off:off + size]
                    entry_head = magic4(entry)

                    if (
                        entry_head == b"CGFX"
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

        if len(data) >= 1 and data[0] == 0x11:
            try:
                dec = lz11_decompress(data)
            except Exception:
                self.false_lz11 += 1
                return

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

        print(
            f"Scanning {total} filesystem files for CGFX "
            f"against {len(self.targets)} PSLB target names...",
            flush=True,
        )

        for i, path in enumerate(files, 1):
            try:
                with path.open("rb") as f:
                    head = f.read(4)

                if (
                    head == b"CGFX"
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
                    f"CGFX={self.cgfx_count} "
                    f"matches={len(self.matches)} "
                    f"errors={len(self.errors)}",
                    flush=True,
                )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Cross-reference exact PSLB model/animation names against strings "
            "inside KIU CGFX/BCRES/BCTEX resources."
        )
    )
    ap.add_argument("romfs", type=Path)
    ap.add_argument("pslb_string_refs", type=Path)
    ap.add_argument("pslb_occurrences", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("PSLB_CGFX_CROSSREF"),
    )
    ap.add_argument("--max-depth", type=int, default=16)
    args = ap.parse_args()

    root = args.romfs.resolve()
    out = args.output.resolve()

    if not root.is_dir():
        print(f"ERROR: RomFS is not a directory: {root}", file=sys.stderr)
        return 1
    if not args.pslb_string_refs.is_file():
        print(f"ERROR: missing file: {args.pslb_string_refs}", file=sys.stderr)
        return 1
    if not args.pslb_occurrences.is_file():
        print(f"ERROR: missing file: {args.pslb_occurrences}", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    targets, target_keys, refs = load_pslb_references(args.pslb_string_refs)
    occurrences = load_occurrences(args.pslb_occurrences)

    print("Exact PSLB reference keys:")
    for key in sorted(GRAPHICS_KEYS):
        print(f"  {key}")
    print(f"Unique target values: {len(targets)}")
    print()

    scanner = CgfxScanner(root, targets, args.max_depth)

    try:
        scanner.run()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130

    # value -> list of CGFX hits
    cgfx_by_value = defaultdict(list)
    for row in scanner.matches:
        cgfx_by_value[row["value"]].append(row)

    # Normalized table: each unique target -> CGFX resource hit.
    match_csv = out / "cgfx_name_matches.csv"
    with match_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "value",
            "pslb_keys",
            "physical_path",
            "cgfx_virtual_path",
            "cgfx_sha1",
            "cgfx_size",
        ])

        seen = set()
        for row in scanner.matches:
            key = (
                row["value"],
                row["cgfx_virtual_path"],
                row["cgfx_sha1"],
            )
            if key in seen:
                continue
            seen.add(key)

            w.writerow([
                row["value"],
                ";".join(sorted(target_keys[row["value"]])),
                row["physical_path"],
                row["cgfx_virtual_path"],
                row["cgfx_sha1"],
                row["cgfx_size"],
            ])

    # Expanded graph edges:
    # correct PSLB occurrence -> exact key/value -> matching CGFX resource.
    edges_csv = out / "pslb_to_cgfx_edges.csv"
    edge_count = 0

    with edges_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "pslb_virtual_path",
            "pslb_sha1",
            "json_path",
            "pslb_key",
            "value",
            "cgfx_virtual_path",
            "cgfx_sha1",
            "cgfx_size",
        ])

        seen = set()

        for ref in refs:
            hits = cgfx_by_value.get(ref["value"])
            if not hits:
                continue

            source_paths = occurrences.get(ref["sha1"], [])
            if not source_paths:
                source_paths = ["(no corrected occurrence path found)"]

            for source_path in source_paths:
                for hit in hits:
                    edge = (
                        source_path,
                        ref["sha1"],
                        ref["json_path"],
                        ref["key"],
                        ref["value"],
                        hit["cgfx_virtual_path"],
                        hit["cgfx_sha1"],
                    )
                    if edge in seen:
                        continue
                    seen.add(edge)

                    w.writerow([
                        source_path,
                        ref["sha1"],
                        ref["json_path"],
                        ref["key"],
                        ref["value"],
                        hit["cgfx_virtual_path"],
                        hit["cgfx_sha1"],
                        hit["cgfx_size"],
                    ])
                    edge_count += 1

    matched_values = set(cgfx_by_value)
    unmatched = sorted(targets - matched_values)

    unmatched_txt = out / "unmatched_pslb_graphics_names.txt"
    unmatched_txt.write_text("\n".join(unmatched) + ("\n" if unmatched else ""), encoding="utf-8")

    summary = out / "pslb_cgfx_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("KIU PSLB -> CGFX CROSS-REFERENCE\n")
        f.write("=" * 88 + "\n\n")

        f.write(f"PSLB exact-key target values : {len(targets)}\n")
        f.write(f"CGFX resources scanned       : {scanner.cgfx_count}\n")
        f.write(f"Values found in CGFX         : {len(matched_values)}\n")
        f.write(f"Values not found in CGFX     : {len(unmatched)}\n")
        f.write(f"Expanded graph edges         : {edge_count}\n")
        f.write(f"0x11 false positives         : {scanner.false_lz11}\n")
        f.write(f"Actual scan errors           : {len(scanner.errors)}\n\n")

        f.write("MATCHED VALUES (first 300)\n")
        f.write("-" * 88 + "\n")
        for value in sorted(matched_values)[:300]:
            hits = cgfx_by_value[value]
            f.write(
                f"{value} | keys={','.join(sorted(target_keys[value]))} | "
                f"cgfx_hits={len(hits)}\n"
            )
            for hit in hits[:5]:
                f.write(f"    {hit['cgfx_virtual_path']}\n")
            if len(hits) > 5:
                f.write(f"    ... {len(hits)-5} more\n")

        f.write("\nUNMATCHED VALUES (first 300)\n")
        f.write("-" * 88 + "\n")
        for value in unmatched[:300]:
            f.write(
                f"{value} | keys={','.join(sorted(target_keys[value]))}\n"
            )

        if scanner.errors:
            f.write("\nERRORS\n")
            f.write("-" * 88 + "\n")
            for error in scanner.errors:
                f.write(error + "\n")

    print()
    print("=" * 72)
    print("PSLB -> CGFX CROSS-REFERENCE COMPLETE")
    print("=" * 72)
    print(f"Target values : {len(targets)}")
    print(f"CGFX scanned  : {scanner.cgfx_count}")
    print(f"Values matched: {len(matched_values)}")
    print(f"Unmatched     : {len(unmatched)}")
    print(f"Graph edges   : {edge_count}")
    print(f"Errors        : {len(scanner.errors)}")
    print()
    print(f"Summary : {summary}")
    print(f"Matches : {match_csv}")
    print(f"Edges   : {edges_csv}")
    print(f"Missing : {unmatched_txt}")

    return 0 if not scanner.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
