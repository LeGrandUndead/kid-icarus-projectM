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


TARGET_KEYS = {"nID_", "effectID_"}


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


def scalar_value(node):
    if isinstance(node, pslb_tool.PslbInt):
        return ("int", int(node.value))
    if isinstance(node, pslb_tool.PslbByte):
        return ("byte", int(node.value))
    if isinstance(node, pslb_tool.PslbString):
        return ("string", node.text())
    if isinstance(node, pslb_tool.PslbFloat):
        return ("float", node.value)
    return None


def outer_scope(virtual_path: str) -> str:
    outer = virtual_path.replace("\\", "/").split("::", 1)[0]
    parts = outer.split("/")
    if len(parts) <= 1:
        return outer
    return "/".join(parts[:-1])


def source_category(path: str) -> str:
    outer = path.replace("\\", "/").split("::", 1)[0]
    parts = outer.split("/")
    if len(parts) >= 2 and parts[0] == "us":
        return parts[1]
    return "(other)"


# ------------------------------------------------------------
# EFF trigger IDs by folder
# ------------------------------------------------------------

def parse_eff_trigger_ids(path: Path, romfs: Path):
    data = path.read_bytes()

    if len(data) < 8:
        raise ValueError("too small")

    if u32(data, 0) != 0 or u32(data, 4) not in (2, 3):
        raise ValueError("unexpected EFF header")

    rel = path.relative_to(romfs).as_posix()
    scope = path.parent.relative_to(romfs).as_posix()

    off = 8
    rows = []

    while off < len(data):
        name, after = read_cstr(data, off)
        size_off = align4(after)
        if size_off + 4 > len(data):
            raise ValueError("truncated section size")

        size = u32(data, size_off)
        data_off = size_off + 4
        end = data_off + size

        if end > len(data):
            raise ValueError(f"section {name} exceeds EOF")

        if name.startswith("effectTriggerData_"):
            if size % 0x50:
                raise ValueError(f"{name}: invalid trigger section size")

            for i in range(size // 0x50):
                r = data_off + i * 0x50
                rows.append({
                    "eff_path": rel,
                    "eff_scope": scope,
                    "trigger_section": name,
                    "trigger_index": i,
                    "trigger_id": u32(data, r + 0x00),
                    "target_type": u32(data, r + 0x28),
                    "target_section": fixed_ascii(data[r + 0x2C:r + 0x4C]),
                    "target_index": data[r + 0x4F],
                })

        off = end

    return rows


def load_occurrence_map(path: Path):
    by_sha1 = defaultdict(list)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            by_sha1[row["sha1"]].append(row["virtual_path"])

    return by_sha1


# ------------------------------------------------------------
# PSLB map-context traversal
# ------------------------------------------------------------

def walk_maps(node, json_path: str, emit_map):
    if isinstance(node, pslb_tool.PslbMap):
        decoded_items = [(decode_key(k), v) for k, v in node.items]
        emit_map(json_path, decoded_items)

        for key, value in decoded_items:
            child = f"{json_path}.{key}" if json_path else key
            walk_maps(value, child, emit_map)
        return

    if isinstance(node, pslb_tool.PslbList):
        for i, value in enumerate(node.items):
            child = f"{json_path}[{i}]"
            walk_maps(value, child, emit_map)
        return

    # Scalars have no child maps.
    return


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Classify PSLB nID_/effectID_ references by sibling @class and "
            "map structure, then test exact same-folder matches against EFF "
            "trigger IDs."
        )
    )
    ap.add_argument("romfs", type=Path)
    ap.add_argument("pslb_folder", type=Path)
    ap.add_argument("pslb_occurrences", type=Path)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("PSLB_EFF_CLASS_CONTEXT"),
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
        print(f"ERROR: occurrence CSV not found: {args.pslb_occurrences}", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    # Build EFF lookup.
    local_eff = defaultdict(lambda: defaultdict(list))
    eff_rows = []

    for path in sorted(p for p in romfs.rglob("eff_00.bin") if p.is_file()):
        for row in parse_eff_trigger_ids(path, romfs):
            eff_rows.append(row)
            local_eff[row["eff_scope"]][row["trigger_id"]].append(row)

    occurrences = load_occurrence_map(args.pslb_occurrences)

    # Deduplicate PSLB payloads by SHA1.
    payloads = {}
    for path in sorted(p for p in pslb_folder.rglob("*") if p.is_file()):
        data = path.read_bytes()
        if data.startswith(b"PSLB"):
            sha1 = hashlib.sha1(data).hexdigest()
            payloads.setdefault(sha1, data)

    detail_rows = []
    failures = []

    for n, (sha1, data) in enumerate(payloads.items(), 1):
        try:
            pslb = pslb_tool.parse_pslb(data)
        except Exception as exc:
            failures.append((sha1, str(exc)))
            continue

        contexts = []

        def emit_map(json_path, items):
            scalar = {}
            keys = []

            for key, value in items:
                keys.append(key)
                sv = scalar_value(value)
                if sv is not None:
                    scalar[key] = sv

            class_value = None
            if "@class" in scalar and scalar["@class"][0] in ("int", "byte"):
                class_value = int(scalar["@class"][1])

            for target_key in TARGET_KEYS:
                if target_key not in scalar:
                    continue

                vtype, value = scalar[target_key]
                if vtype not in ("int", "byte"):
                    continue

                contexts.append({
                    "json_path": json_path,
                    "target_key": target_key,
                    "value_type": vtype,
                    "value": int(value),
                    "class_value": class_value,
                    "sibling_keys": ";".join(sorted(keys)),
                    "sModelName_": scalar.get("sModelName_", ("", ""))[1] if "sModelName_" in scalar else "",
                    "sBoneName_": scalar.get("sBoneName_", ("", ""))[1] if "sBoneName_" in scalar else "",
                    "charName_": scalar.get("charName_", ("", ""))[1] if "charName_" in scalar else "",
                    "modelType_": scalar.get("modelType_", ("", ""))[1] if "modelType_" in scalar else "",
                })

        walk_maps(pslb.root, "", emit_map)

        for source_path in occurrences.get(sha1, []):
            scope = outer_scope(source_path)
            cat = source_category(source_path)

            for ctx in contexts:
                hits = local_eff.get(scope, {}).get(ctx["value"], [])

                if hits:
                    for hit in hits:
                        detail_rows.append({
                            "pslb_virtual_path": source_path,
                            "pslb_sha1": sha1,
                            "category": cat,
                            **ctx,
                            "local_match": 1,
                            "eff_path": hit["eff_path"],
                            "trigger_section": hit["trigger_section"],
                            "trigger_index": hit["trigger_index"],
                            "target_type": hit["target_type"],
                            "target_section": hit["target_section"],
                            "target_index": hit["target_index"],
                        })
                else:
                    detail_rows.append({
                        "pslb_virtual_path": source_path,
                        "pslb_sha1": sha1,
                        "category": cat,
                        **ctx,
                        "local_match": 0,
                        "eff_path": "",
                        "trigger_section": "",
                        "trigger_index": "",
                        "target_type": "",
                        "target_section": "",
                        "target_index": "",
                    })

        if n % 250 == 0 or n == len(payloads):
            print(
                f"[{n}/{len(payloads)}] rows={len(detail_rows)} failures={len(failures)}",
                flush=True,
            )

    # Aggregate by target key + @class.
    stats = {}

    # Count one source reference once even if a trigger ID fans out to multiple
    # EFF records with the same ID.
    ref_groups = defaultdict(list)
    for row in detail_rows:
        ref_id = (
            row["pslb_virtual_path"],
            row["pslb_sha1"],
            row["json_path"],
            row["target_key"],
            row["value"],
        )
        ref_groups[ref_id].append(row)

    agg = defaultdict(lambda: {
        "references": 0,
        "local_matches": 0,
        "values": set(),
        "matched_values": set(),
        "source_paths": set(),
        "categories": Counter(),
        "signatures": Counter(),
        "target_types": Counter(),
    })

    for ref_id, rows in ref_groups.items():
        first = rows[0]
        cls = first["class_value"]
        key = first["target_key"]
        group_key = (key, cls)

        a = agg[group_key]
        a["references"] += 1
        a["values"].add(first["value"])
        a["source_paths"].add(first["pslb_virtual_path"])
        a["categories"][first["category"]] += 1
        a["signatures"][first["sibling_keys"]] += 1

        matched = any(r["local_match"] for r in rows)
        if matched:
            a["local_matches"] += 1
            a["matched_values"].add(first["value"])

            for r in rows:
                if r["local_match"] and r["target_type"] != "":
                    a["target_types"][str(r["target_type"])] += 1

    stat_rows = []

    for (key, cls), a in agg.items():
        rate = a["local_matches"] / a["references"] if a["references"] else 0.0

        stat_rows.append({
            "target_key": key,
            "class_value": "" if cls is None else cls,
            "class_hex": "" if cls is None else f"0x{cls & 0xFFFFFFFF:08X}",
            "references": a["references"],
            "local_matches": a["local_matches"],
            "match_rate": rate,
            "unique_values": len(a["values"]),
            "matched_unique_values": len(a["matched_values"]),
            "source_paths": len(a["source_paths"]),
            "categories": ";".join(
                f"{k}:{v}" for k, v in a["categories"].most_common()
            ),
            "target_types": ";".join(
                f"{k}:{v}" for k, v in a["target_types"].most_common()
            ),
            "top_sibling_signature": a["signatures"].most_common(1)[0][0],
        })

    stat_rows.sort(
        key=lambda r: (
            r["target_key"],
            -r["local_matches"],
            -r["match_rate"],
            -r["references"],
        )
    )

    detail_csv = out / "pslb_eff_class_context_detail.csv"
    with detail_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "pslb_virtual_path",
            "pslb_sha1",
            "category",
            "json_path",
            "target_key",
            "value_type",
            "value",
            "class_value",
            "sibling_keys",
            "sModelName_",
            "sBoneName_",
            "charName_",
            "modelType_",
            "local_match",
            "eff_path",
            "trigger_section",
            "trigger_index",
            "target_type",
            "target_section",
            "target_index",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(detail_rows)

    stats_csv = out / "pslb_eff_class_stats.csv"
    with stats_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "target_key",
            "class_value",
            "class_hex",
            "references",
            "local_matches",
            "match_rate",
            "unique_values",
            "matched_unique_values",
            "source_paths",
            "categories",
            "target_types",
            "top_sibling_signature",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(stat_rows)

    summary = out / "pslb_eff_class_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 96 + "\n")
        f.write("KIU PSLB -> EFF CLASS-CONTEXT ANALYSIS\n")
        f.write("=" * 96 + "\n\n")
        f.write(f"Unique PSLB payloads : {len(payloads)}\n")
        f.write(f"EFF trigger records  : {len(eff_rows)}\n")
        f.write(f"Context detail rows  : {len(detail_rows)}\n")
        f.write(f"PSLB failures        : {len(failures)}\n\n")

        f.write(
            "Goal: distinguish real nID_/effectID_ effect references from "
            "generic numeric fields by grouping them by sibling @class.\n\n"
        )

        for key in sorted(TARGET_KEYS):
            f.write(f"TOP CLASSES FOR {key}\n")
            f.write("-" * 96 + "\n")

            rows = [r for r in stat_rows if r["target_key"] == key]
            rows.sort(
                key=lambda r: (
                    -r["local_matches"],
                    -r["match_rate"],
                    -r["references"],
                )
            )

            for r in rows[:80]:
                f.write(
                    f"class={str(r['class_value']):>12s} "
                    f"{r['class_hex']:>10s} "
                    f"refs={r['references']:7d} "
                    f"local={r['local_matches']:7d} "
                    f"rate={r['match_rate']:.4f} "
                    f"uniq={r['unique_values']:5d} "
                    f"matched_uniq={r['matched_unique_values']:5d} "
                    f"paths={r['source_paths']:5d} "
                    f"cats={r['categories']}\n"
                )
                f.write(
                    f"    signature: {r['top_sibling_signature']}\n"
                )

            f.write("\n")

        f.write("SAMPLE MATCHED CONTEXTS\n")
        f.write("-" * 96 + "\n")

        shown = 0
        for row in detail_rows:
            if not row["local_match"]:
                continue
            f.write(
                f"{row['pslb_virtual_path']}\n"
                f"  {row['json_path']} | class={row['class_value']} "
                f"{row['target_key']}={row['value']}\n"
                f"  siblings={row['sibling_keys']}\n"
                f"  -> {row['eff_path']} "
                f"{row['trigger_section']}[{row['trigger_index']}]\n"
                f"     target={row['target_section']}[{row['target_index']}] "
                f"type={row['target_type']}\n\n"
            )
            shown += 1
            if shown >= 120:
                break

    print()
    print("=" * 72)
    print("PSLB -> EFF CLASS-CONTEXT ANALYSIS COMPLETE")
    print("=" * 72)
    print(f"Unique PSLBs : {len(payloads)}")
    print(f"Detail rows  : {len(detail_rows)}")
    print(f"Class groups : {len(stat_rows)}")
    print(f"Failures     : {len(failures)}")
    print()
    print(f"Summary : {summary}")
    print(f"Stats   : {stats_csv}")
    print(f"Detail  : {detail_csv}")

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
