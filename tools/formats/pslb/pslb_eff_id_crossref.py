from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import csv
import hashlib
import struct
import sys

try:
    import pslb_tool
except ImportError:
    print(
        "ERROR: could not import pslb_tool.py.\n"
        "Put this script in the same folder as pslb_tool.py.",
        file=sys.stderr,
    )
    raise SystemExit(2)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def align4(x: int) -> int:
    return (x + 3) & ~3


def read_cstr(data: bytes, off: int) -> tuple[str, int]:
    end = data.find(b"\x00", off)
    if end < 0:
        raise ValueError(f"unterminated C string at 0x{off:X}")
    return data[off:end].decode("ascii"), end + 1


def fixed_ascii(raw: bytes) -> str:
    raw = raw.split(b"\x00", 1)[0]
    if not raw:
        return ""
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return ""


def decode_key(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp932")
        except UnicodeDecodeError:
            return raw.decode("latin-1")


def outer_scope(virtual_path: str) -> str:
    """
    us/demo/003/demo/json.arc::json/00.json
      -> us/demo/003/demo

    us/player/a0/character/json.arc::json/00.json
      -> us/player/a0/character
    """
    outer = virtual_path.replace("\\", "/").split("::", 1)[0]
    parts = outer.split("/")
    if len(parts) <= 1:
        return outer
    return "/".join(parts[:-1])


# ------------------------------------------------------------
# EFF trigger extraction
# ------------------------------------------------------------

def parse_eff_trigger_rows(path: Path, romfs: Path):
    data = path.read_bytes()

    if len(data) < 8:
        raise ValueError("too small")

    field0 = u32(data, 0)
    eff_type = u32(data, 4)

    if field0 != 0 or eff_type not in (2, 3):
        raise ValueError(
            f"unexpected EFF header field0={field0} type={eff_type}"
        )

    rel = path.relative_to(romfs).as_posix()
    scope = path.parent.relative_to(romfs).as_posix()

    off = 8
    rows = []

    while off < len(data):
        section_name, after_name = read_cstr(data, off)
        size_off = align4(after_name)

        if size_off + 4 > len(data):
            raise ValueError(f"truncated size for {section_name!r}")

        section_size = u32(data, size_off)
        section_data = size_off + 4
        section_end = section_data + section_size

        if section_end > len(data):
            raise ValueError(f"section {section_name!r} exceeds file")

        if section_name.startswith("effectTriggerData_"):
            rec_size = 0x50

            if section_size % rec_size:
                raise ValueError(
                    f"{section_name}: size 0x{section_size:X} "
                    f"not divisible by 0x50"
                )

            count = section_size // rec_size

            for i in range(count):
                r = section_data + i * rec_size

                trigger_id = u32(data, r + 0x00)
                target_type = u32(data, r + 0x28)
                target_section = fixed_ascii(data[r + 0x2C:r + 0x4C])
                target_index = data[r + 0x4F]

                rows.append({
                    "eff_path": rel,
                    "eff_scope": scope,
                    "eff_type": eff_type,
                    "trigger_section": section_name,
                    "trigger_index": i,
                    "trigger_id": trigger_id,
                    "target_type": target_type,
                    "target_section": target_section,
                    "target_index": target_index,
                })

        off = section_end

    if off != len(data):
        raise ValueError("EFF parse did not end at EOF")

    return rows


# ------------------------------------------------------------
# PSLB integer extraction
# ------------------------------------------------------------

def walk_pslb(node, path: str, current_key: str, emit_int):
    if isinstance(node, pslb_tool.PslbInt):
        emit_int(path, current_key, node.value, "int32")
        return

    if isinstance(node, pslb_tool.PslbByte):
        emit_int(path, current_key, node.value, "byte")
        return

    if isinstance(node, pslb_tool.PslbString):
        return

    if isinstance(node, pslb_tool.PslbFloat):
        return

    if isinstance(node, pslb_tool.PslbMap):
        for raw_key, value in node.items:
            key = decode_key(raw_key)
            child_path = f"{path}.{key}" if path else key
            walk_pslb(value, child_path, key, emit_int)
        return

    if isinstance(node, pslb_tool.PslbList):
        for i, value in enumerate(node.items):
            child_path = f"{path}[{i}]"
            walk_pslb(value, child_path, current_key, emit_int)
        return

    raise TypeError(f"Unhandled PSLB node: {type(node)!r}")


def load_occurrence_map(path: Path):
    by_sha1 = defaultdict(list)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {"sha1", "virtual_path"}
        missing = required - set(r.fieldnames or [])
        if missing:
            raise ValueError(
                f"occurrence CSV missing columns: {sorted(missing)}"
            )

        for row in r:
            by_sha1[row["sha1"]].append(row["virtual_path"])

    return by_sha1


# ------------------------------------------------------------
# Main analysis
# ------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Discover PSLB integer fields that overlap KIU EFF trigger IDs. "
            "Exact same-folder matches are reported separately from global "
            "numeric overlaps so we do not mistake common numbers for links."
        )
    )
    ap.add_argument("romfs", type=Path)
    ap.add_argument("pslb_folder", type=Path)
    ap.add_argument("pslb_occurrences", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("PSLB_EFF_ID_ANALYSIS"),
    )
    args = ap.parse_args()

    romfs = args.romfs.resolve()
    pslb_folder = args.pslb_folder.resolve()
    out = args.output.resolve()

    if not romfs.is_dir():
        print(f"ERROR: RomFS not found: {romfs}", file=sys.stderr)
        return 1
    if not pslb_folder.is_dir():
        print(f"ERROR: PSLB folder not found: {pslb_folder}", file=sys.stderr)
        return 1
    if not args.pslb_occurrences.is_file():
        print(
            f"ERROR: occurrence CSV not found: {args.pslb_occurrences}",
            file=sys.stderr,
        )
        return 1

    out.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # Parse all EFF trigger IDs
    # -------------------------

    eff_paths = sorted(
        p for p in romfs.rglob("eff_00.bin") if p.is_file()
    )

    eff_rows = []
    eff_failures = []

    for path in eff_paths:
        try:
            eff_rows.extend(parse_eff_trigger_rows(path, romfs))
        except Exception as exc:
            eff_failures.append((str(path), str(exc)))

    global_eff_ids = defaultdict(list)
    local_eff_ids = defaultdict(lambda: defaultdict(list))

    for row in eff_rows:
        tid = int(row["trigger_id"])
        global_eff_ids[tid].append(row)
        local_eff_ids[row["eff_scope"]][tid].append(row)

    print(f"EFF files              : {len(eff_paths)}")
    print(f"EFF trigger records    : {len(eff_rows)}")
    print(f"Unique EFF trigger IDs : {len(global_eff_ids)}")
    print(f"EFF failures           : {len(eff_failures)}")
    print()

    # -------------------------
    # Parse unique PSLB payloads
    # -------------------------

    occurrence_map = load_occurrence_map(args.pslb_occurrences)

    payload_by_sha1 = {}
    for path in sorted(p for p in pslb_folder.rglob("*") if p.is_file()):
        data = path.read_bytes()
        if not data.startswith(b"PSLB"):
            continue
        sha1 = hashlib.sha1(data).hexdigest()
        payload_by_sha1.setdefault(sha1, data)

    print(f"Unique PSLB payloads on disk: {len(payload_by_sha1)}")

    key_stats = defaultdict(lambda: {
        "occurrences": 0,
        "unique_values": set(),
        "global_matches": 0,
        "global_match_values": set(),
        "local_matches": 0,
        "local_match_values": set(),
        "local_source_paths": set(),
    })

    local_edges = []
    global_overlap_rows = []
    pslb_failures = []

    for n, (sha1, data) in enumerate(payload_by_sha1.items(), 1):
        try:
            pslb = pslb_tool.parse_pslb(data)
        except Exception as exc:
            pslb_failures.append((sha1, str(exc)))
            continue

        source_paths = occurrence_map.get(sha1, [])

        raw_ints = []

        def emit_int(json_path: str, key: str, value: int, value_type: str):
            raw_ints.append((json_path, key, int(value), value_type))

        walk_pslb(pslb.root, "", "", emit_int)

        for source_path in source_paths:
            scope = outer_scope(source_path)
            local_ids_for_scope = local_eff_ids.get(scope, {})

            for json_path, key, value, value_type in raw_ints:
                s = key_stats[key]
                s["occurrences"] += 1
                s["unique_values"].add(value)

                global_hits = global_eff_ids.get(value, [])
                if global_hits:
                    s["global_matches"] += 1
                    s["global_match_values"].add(value)

                    global_overlap_rows.append({
                        "pslb_virtual_path": source_path,
                        "pslb_sha1": sha1,
                        "json_path": json_path,
                        "key": key,
                        "value_type": value_type,
                        "value": value,
                        "global_eff_hit_count": len(global_hits),
                    })

                local_hits = local_ids_for_scope.get(value, [])
                if local_hits:
                    s["local_matches"] += 1
                    s["local_match_values"].add(value)
                    s["local_source_paths"].add(source_path)

                    for hit in local_hits:
                        local_edges.append({
                            "pslb_virtual_path": source_path,
                            "pslb_sha1": sha1,
                            "json_path": json_path,
                            "key": key,
                            "value_type": value_type,
                            "value": value,
                            "eff_path": hit["eff_path"],
                            "trigger_section": hit["trigger_section"],
                            "trigger_index": hit["trigger_index"],
                            "trigger_id": hit["trigger_id"],
                            "target_type": hit["target_type"],
                            "target_section": hit["target_section"],
                            "target_index": hit["target_index"],
                        })

        if n % 250 == 0 or n == len(payload_by_sha1):
            print(
                f"[PSLB {n}/{len(payload_by_sha1)}] "
                f"local_edges={len(local_edges)} "
                f"failed={len(pslb_failures)}",
                flush=True,
            )

    # -------------------------
    # Rank integer keys
    # -------------------------

    ranked = []

    for key, s in key_stats.items():
        occ = s["occurrences"]
        local = s["local_matches"]
        glob = s["global_matches"]

        ranked.append({
            "key": key,
            "occurrences": occ,
            "unique_values": len(s["unique_values"]),
            "global_match_occurrences": glob,
            "global_match_unique_values": len(s["global_match_values"]),
            "global_match_rate": (glob / occ) if occ else 0.0,
            "local_match_occurrences": local,
            "local_match_unique_values": len(s["local_match_values"]),
            "local_match_rate": (local / occ) if occ else 0.0,
            "local_source_paths": len(s["local_source_paths"]),
        })

    ranked.sort(
        key=lambda r: (
            -r["local_match_occurrences"],
            -r["local_match_rate"],
            -r["global_match_occurrences"],
            r["key"],
        )
    )

    # -------------------------
    # Outputs
    # -------------------------

    trigger_csv = out / "eff_trigger_ids.csv"
    with trigger_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "eff_path",
            "eff_scope",
            "eff_type",
            "trigger_section",
            "trigger_index",
            "trigger_id",
            "target_type",
            "target_section",
            "target_index",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(eff_rows)

    keys_csv = out / "pslb_integer_key_overlap.csv"
    with keys_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "key",
            "occurrences",
            "unique_values",
            "global_match_occurrences",
            "global_match_unique_values",
            "global_match_rate",
            "local_match_occurrences",
            "local_match_unique_values",
            "local_match_rate",
            "local_source_paths",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(ranked)

    local_csv = out / "candidate_local_pslb_to_eff_edges.csv"
    with local_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "pslb_virtual_path",
            "pslb_sha1",
            "json_path",
            "key",
            "value_type",
            "value",
            "eff_path",
            "trigger_section",
            "trigger_index",
            "trigger_id",
            "target_type",
            "target_section",
            "target_index",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(local_edges)

    global_csv = out / "global_numeric_overlaps.csv"
    with global_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "pslb_virtual_path",
            "pslb_sha1",
            "json_path",
            "key",
            "value_type",
            "value",
            "global_eff_hit_count",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(global_overlap_rows)

    summary = out / "pslb_eff_id_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 92 + "\n")
        f.write("KIU PSLB INTEGER -> EFF TRIGGER-ID DISCOVERY\n")
        f.write("=" * 92 + "\n\n")

        f.write(f"EFF files                 : {len(eff_paths)}\n")
        f.write(f"EFF trigger records       : {len(eff_rows)}\n")
        f.write(f"Unique EFF trigger IDs    : {len(global_eff_ids)}\n")
        f.write(f"EFF parse failures        : {len(eff_failures)}\n")
        f.write(f"Unique PSLB payloads      : {len(payload_by_sha1)}\n")
        f.write(f"PSLB parse failures       : {len(pslb_failures)}\n")
        f.write(f"Local exact-match rows    : {len(local_edges)}\n")
        f.write(f"Global numeric-overlap rows: {len(global_overlap_rows)}\n\n")

        f.write(
            "IMPORTANT: numeric equality alone is not proof of an effect link. "
            "The useful signal is a key with repeated SAME-FOLDER matches to "
            "that folder's eff_00.bin trigger IDs.\n\n"
        )

        f.write("TOP INTEGER KEYS BY SAME-FOLDER EFF-ID OVERLAP\n")
        f.write("-" * 92 + "\n")
        for r in ranked[:120]:
            f.write(
                f"{r['key']:32s} "
                f"occ={r['occurrences']:8d} "
                f"uniq={r['unique_values']:6d} "
                f"local={r['local_match_occurrences']:7d} "
                f"local_uniq={r['local_match_unique_values']:5d} "
                f"rate={r['local_match_rate']:.4f} "
                f"global={r['global_match_occurrences']:7d}\n"
            )

        f.write("\nSAMPLE LOCAL EXACT MATCHES\n")
        f.write("-" * 92 + "\n")
        for row in local_edges[:150]:
            f.write(
                f"{row['pslb_virtual_path']}\n"
                f"  {row['json_path']} | {row['key']}={row['value']}\n"
                f"  -> {row['eff_path']} "
                f"{row['trigger_section']}[{row['trigger_index']}]\n"
                f"     target={row['target_section']}[{row['target_index']}] "
                f"type={row['target_type']}\n\n"
            )

        if eff_failures:
            f.write("\nEFF FAILURES\n")
            f.write("-" * 92 + "\n")
            for path, err in eff_failures:
                f.write(f"{path}\n  {err}\n")

        if pslb_failures:
            f.write("\nPSLB FAILURES\n")
            f.write("-" * 92 + "\n")
            for sha1, err in pslb_failures:
                f.write(f"{sha1}: {err}\n")

    print()
    print("=" * 72)
    print("PSLB -> EFF ID DISCOVERY COMPLETE")
    print("=" * 72)
    print(f"EFF triggers        : {len(eff_rows)}")
    print(f"Unique trigger IDs  : {len(global_eff_ids)}")
    print(f"Unique PSLBs        : {len(payload_by_sha1)}")
    print(f"Local match rows    : {len(local_edges)}")
    print(f"Global overlap rows : {len(global_overlap_rows)}")
    print(f"Failures            : {len(eff_failures) + len(pslb_failures)}")
    print()
    print(f"Summary : {summary}")
    print(f"Keys    : {keys_csv}")
    print(f"Local   : {local_csv}")
    print(f"Global  : {global_csv}")
    print(f"Triggers: {trigger_csv}")

    return 0 if not eff_failures and not pslb_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
