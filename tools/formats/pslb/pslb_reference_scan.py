from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import csv
import hashlib
import sys

# Put this script next to pslb_tool.py, or make sure pslb_tool.py is importable.
try:
    import pslb_tool
except ImportError:
    print(
        "ERROR: could not import pslb_tool.py.\n"
        "Put pslb_reference_scan.py in the same folder as pslb_tool.py.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp932")
        except UnicodeDecodeError:
            return raw.decode("latin-1")


def classify_reference(key: str, value: str) -> str:
    k = key.lower()
    v = value.upper()

    # Strong prefix-based identifiers first.
    if v.startswith("CHID_"):
        return "character_id"
    if v.startswith("DEMOID_"):
        return "demo_id"
    if v.startswith("WPNID_"):
        return "weapon_id"
    if v.startswith("OBJECT_"):
        return "object_type"
    if v.startswith("DL_"):
        return "draw_layer"
    if v.startswith("DMT_"):
        return "model_type"

    # Key-name heuristics. These are hints, not guaranteed semantics.
    if "model" in k or "motif" in k:
        return "model_ref"
    if "motion" in k or "animation" in k or "anim" in k or "anm" in k:
        return "animation_ref"
    if "bone" in k or "node" in k:
        return "bone_or_node"
    if "effect" in k or k.startswith("eff") or "_eff" in k:
        return "effect_ref"
    if "sound" in k or "bgm" in k:
        return "sound_ref"
    if "stage" in k:
        return "stage_ref"
    if "demo" in k:
        return "demo_ref"
    if "char" in k:
        return "character_ref"
    if key == "@class":
        return "class_string"

    return "string"


def walk(node, path: str, current_key: str, emit_string, emit_class, emit_key):
    if isinstance(node, pslb_tool.PslbString):
        emit_string(path, current_key, node.text())
        return

    if isinstance(node, pslb_tool.PslbInt):
        if current_key == "@class":
            emit_class(path, node.value)
        return

    if isinstance(node, pslb_tool.PslbFloat):
        return

    if isinstance(node, pslb_tool.PslbByte):
        return

    if isinstance(node, pslb_tool.PslbMap):
        for raw_key, value in node.items:
            key = decode(raw_key)
            emit_key(key)
            child_path = f"{path}.{key}" if path else key
            walk(value, child_path, key, emit_string, emit_class, emit_key)
        return

    if isinstance(node, pslb_tool.PslbList):
        for i, value in enumerate(node.items):
            child_path = f"{path}[{i}]"
            walk(value, child_path, current_key, emit_string, emit_class, emit_key)
        return

    raise TypeError(f"Unhandled PSLB node type: {type(node)!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine KIU PSLB files for strings, IDs, @class values, and key usage."
    )
    parser.add_argument(
        "pslb_folder",
        type=Path,
        help="Folder containing extracted PSLB files (for example PSLB_RESEARCH\\pslb_files)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pslb_reference_analysis"),
        help="Output folder",
    )
    args = parser.parse_args()

    root = args.pslb_folder
    out = args.output

    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 1

    files = sorted(p for p in root.rglob("*") if p.is_file())
    if not files:
        print("ERROR: no files found", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    string_rows = []
    class_rows = []

    key_occurrences = Counter()
    class_occurrences = Counter()
    category_occurrences = Counter()
    value_occurrences = Counter()

    value_files = defaultdict(set)
    category_values = defaultdict(Counter)
    class_files = defaultdict(set)

    payload_hashes = Counter()
    parsed = 0
    failed = []

    for i, path in enumerate(files, 1):
        try:
            data = path.read_bytes()
            if not data.startswith(b"PSLB"):
                continue

            sha1 = hashlib.sha1(data).hexdigest()
            payload_hashes[sha1] += 1

            pslb = pslb_tool.parse_pslb(data)
            rel = path.relative_to(root).as_posix()

            def emit_string(json_path: str, key: str, value: str):
                category = classify_reference(key, value)

                string_rows.append(
                    (rel, sha1, json_path, key, category, value)
                )

                category_occurrences[category] += 1
                value_occurrences[value] += 1
                value_files[value].add(rel)
                category_values[category][value] += 1

            def emit_class(json_path: str, value: int):
                class_rows.append((rel, sha1, json_path, value))
                class_occurrences[value] += 1
                class_files[value].add(rel)

            def emit_key(key: str):
                key_occurrences[key] += 1

            walk(
                pslb.root,
                "",
                "",
                emit_string,
                emit_class,
                emit_key,
            )

            parsed += 1

        except Exception as exc:
            failed.append((str(path), str(exc)))

        if i % 500 == 0 or i == len(files):
            print(
                f"checked={i}/{len(files)} parsed={parsed} failed={len(failed)}",
                flush=True,
            )

    strings_csv = out / "pslb_string_refs.csv"
    with strings_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "file",
            "sha1",
            "json_path",
            "key",
            "category",
            "value",
        ])
        w.writerows(string_rows)

    classes_csv = out / "pslb_class_refs.csv"
    with classes_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "sha1", "json_path", "class_value"])
        w.writerows(class_rows)

    keys_csv = out / "pslb_key_counts.csv"
    with keys_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["key", "occurrences"])
        for key, count in key_occurrences.most_common():
            w.writerow([key, count])

    value_csv = out / "pslb_value_counts.csv"
    with value_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["value", "occurrences", "files"])
        for value, count in value_occurrences.most_common():
            w.writerow([value, count, len(value_files[value])])

    summary = out / "pslb_reference_summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("KIU PSLB REFERENCE ANALYSIS\n")
        f.write("=" * 88 + "\n\n")

        f.write(f"Files checked       : {len(files)}\n")
        f.write(f"PSLB files parsed   : {parsed}\n")
        f.write(f"Unique payload SHA1 : {len(payload_hashes)}\n")
        f.write(f"Failures            : {len(failed)}\n")
        f.write(f"String values       : {len(string_rows)}\n")
        f.write(f"@class occurrences  : {len(class_rows)}\n")
        f.write(f"Unique @class values: {len(class_occurrences)}\n\n")

        f.write("STRING CATEGORIES\n")
        f.write("-" * 88 + "\n")
        for category, count in category_occurrences.most_common():
            f.write(f"{category:22s} {count:8d}\n")

        f.write("\nTOP KEYS\n")
        f.write("-" * 88 + "\n")
        for key, count in key_occurrences.most_common(100):
            f.write(f"{count:8d}  {key}\n")

        f.write("\nTOP @class VALUES\n")
        f.write("-" * 88 + "\n")
        for value, count in class_occurrences.most_common(100):
            f.write(
                f"{count:8d} occurrences | "
                f"{len(class_files[value]):6d} files | "
                f"{value:12d} | 0x{value & 0xFFFFFFFF:08X}\n"
            )

        interesting_categories = [
            "character_id",
            "demo_id",
            "weapon_id",
            "model_ref",
            "animation_ref",
            "effect_ref",
            "sound_ref",
            "stage_ref",
            "bone_or_node",
            "character_ref",
        ]

        for category in interesting_categories:
            f.write(f"\nTOP VALUES: {category}\n")
            f.write("-" * 88 + "\n")
            values = category_values.get(category)
            if not values:
                f.write("(none)\n")
                continue

            for value, count in values.most_common(100):
                f.write(
                    f"{count:8d} occurrences | "
                    f"{len(value_files[value]):6d} files | "
                    f"{value}\n"
                )

        if failed:
            f.write("\nFAILURES\n")
            f.write("-" * 88 + "\n")
            for path, error in failed:
                f.write(f"{path}\n  {error}\n")

    print()
    print("=" * 72)
    print("PSLB REFERENCE ANALYSIS COMPLETE")
    print("=" * 72)
    print(f"Parsed             : {parsed}")
    print(f"Unique payloads    : {len(payload_hashes)}")
    print(f"String values      : {len(string_rows)}")
    print(f"Unique @class vals : {len(class_occurrences)}")
    print(f"Failures           : {len(failed)}")
    print()
    print(f"Summary : {summary}")
    print(f"Strings : {strings_csv}")
    print(f"Classes : {classes_csv}")
    print(f"Keys    : {keys_csv}")
    print(f"Values  : {value_csv}")

    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
