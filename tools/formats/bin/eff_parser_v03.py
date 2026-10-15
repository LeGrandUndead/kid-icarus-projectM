#!/usr/bin/env python3
"""
Kid Icarus: Uprising eff_00.bin parser (research / v0.3 trigger resolution)

Empirically validated against the 700 eff_00.bin files in the supplied corpus:
  type 2: Particle section + Trigger section
  type 3: Model section + Particle section + Trigger section

Known record sizes:
  Model    0x5C bytes
  Particle 0x54 bytes
  Trigger  0x50 bytes

Unknown fields are intentionally kept as field_XX instead of guessing semantics.

Trigger records now resolve their target section/index/name. Corpus-wide evidence
from the supplied 700-file set supports:
  trigger +0x28: 0 = particle target, 1 = model target
  trigger +0x2C: section reference (section name without .gd)
  trigger +0x4C..0x4E: zero/reserved bytes
  trigger +0x4F: target record index
The +0x00 value is displayed as "trigger_id?" because that semantic name is
still an inference rather than a proven engine symbol.

Directory mode can write parsed text both beside each original file and to a
second directory outside the ROM tree.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

MODEL_RECORD_SIZE = 0x5C
PARTICLE_RECORD_SIZE = 0x54
TRIGGER_RECORD_SIZE = 0x50

EXPECTED_LAYOUTS = {
    2: ("particle", "trigger"),
    3: ("model", "particle", "trigger"),
}


class EFFError(Exception):
    pass


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def s32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def f32(data: bytes, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def be_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def fixed_ascii(data: bytes) -> str:
    raw = data.split(b"\x00", 1)[0]
    return raw.decode("ascii", errors="replace")


def read_aligned_cstring(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        raise EFFError(f"String offset 0x{offset:X} is past EOF")

    try:
        end = data.index(0, offset)
    except ValueError as exc:
        raise EFFError(f"Unterminated ASCII string at 0x{offset:X}") from exc

    raw = data[offset:end]
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise EFFError(f"Non-ASCII section name at 0x{offset:X}") from exc

    next_offset = end + 1
    next_offset = (next_offset + 3) & ~3  # pad to next 4-byte boundary
    return text, next_offset


def safe_float(value: float) -> float | str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return value


def section_kind(name: str) -> str:
    if name.startswith("effectModelData"):
        return "model"
    if name.startswith("effectParticleData"):
        return "particle"
    if name.startswith("effectTriggerData"):
        return "trigger"
    return "unknown"


@dataclass
class Section:
    name: str
    kind: str
    header_offset: int
    data_offset: int
    size: int
    records: list[dict[str, Any]]


@dataclass
class EFFFile:
    path: str
    file_size: int
    field_00: int
    type: int
    sections: list[Section]


def parse_model_record(record: bytes, index: int, file_offset: int) -> dict[str, Any]:
    if len(record) != MODEL_RECORD_SIZE:
        raise EFFError("Bad model record size")

    return {
        "index": index,
        "file_offset": file_offset,
        "raw_hex": record.hex(" ").upper(),
        "field_00_u32": u32(record, 0x00),
        "name_04": fixed_ascii(record[0x04:0x20]),       # 28 bytes
        "field_20": fixed_ascii(record[0x20:0x28]),     # 8 bytes
        "field_28": fixed_ascii(record[0x28:0x30]),
        "field_30": fixed_ascii(record[0x30:0x38]),
        "field_38": fixed_ascii(record[0x38:0x40]),
        "field_40": fixed_ascii(record[0x40:0x48]),
        "field_48": fixed_ascii(record[0x48:0x50]),
        "field_50_u32": u32(record, 0x50),
        "field_54_f32": safe_float(f32(record, 0x54)),
        "field_58_f32": safe_float(f32(record, 0x58)),
    }


def parse_particle_record(record: bytes, index: int, file_offset: int) -> dict[str, Any]:
    if len(record) != PARTICLE_RECORD_SIZE:
        raise EFFError("Bad particle record size")

    return {
        "index": index,
        "file_offset": file_offset,
        "raw_hex": record.hex(" ").upper(),
        "name_00": fixed_ascii(record[0x00:0x20]),       # 32 bytes
        "field_20": fixed_ascii(record[0x20:0x28]),     # observed: follow / none
        "field_28_u32": u32(record, 0x28),
        "field_2C": fixed_ascii(record[0x2C:0x40]),     # 20 bytes
        "field_40_f32": safe_float(f32(record, 0x40)),
        "field_44_f32": safe_float(f32(record, 0x44)),
        "field_48_f32": safe_float(f32(record, 0x48)),
        "field_4C_f32": safe_float(f32(record, 0x4C)),
        "field_50_f32": safe_float(f32(record, 0x50)),
    }


def parse_trigger_record(record: bytes, index: int, file_offset: int) -> dict[str, Any]:
    if len(record) != TRIGGER_RECORD_SIZE:
        raise EFFError("Bad trigger record size")

    fields: dict[str, Any] = {
        "index": index,
        "file_offset": file_offset,
        "raw_hex": record.hex(" ").upper(),
    }

    # Keep complete raw/numeric views for the still-unknown 32-bit fields.
    for off in range(0x00, 0x2C, 4):
        fields[f"field_{off:02X}_hex"] = record[off:off + 4].hex(" ").upper()
        fields[f"field_{off:02X}_u32"] = u32(record, off)
        fields[f"field_{off:02X}_s32"] = s32(record, off)
        fields[f"field_{off:02X}_f32"] = safe_float(f32(record, off))

    # Named interpretations supported by the full supplied corpus.
    # +0x00 is *probably* an event/trigger ID; keep the question mark in text output.
    fields["trigger_id_candidate"] = u32(record, 0x00)

    target_type = u32(record, 0x28)
    fields["target_type"] = target_type
    fields["target_type_name"] = {0: "particle", 1: "model"}.get(
        target_type, f"unknown({target_type})"
    )

    fields["target_reference"] = fixed_ascii(record[0x2C:0x4C])
    # Compatibility alias used by older dumps/scripts.
    fields["reference_2C"] = fields["target_reference"]

    fields["reserved_4C_4E"] = record[0x4C:0x4F].hex(" ").upper()
    fields["reserved_4C_4E_is_zero"] = record[0x4C:0x4F] == b"\x00\x00\x00"
    fields["target_index"] = record[0x4F]

    # Retain the old raw integer views as well. In the known corpus, BE u32 is
    # numerically equal to target_index because the preceding three bytes are zero.
    fields["field_4C_raw"] = record[0x4C:0x50].hex(" ").upper()
    fields["field_4C_be_u32"] = be_u32(record, 0x4C)
    fields["field_4C_le_u32"] = u32(record, 0x4C)

    # Filled after the entire file has been parsed.
    fields["target_section"] = None
    fields["target_name"] = None
    fields["target_file_offset"] = None
    fields["target_reference_matches_section"] = False
    fields["target_resolved"] = False
    fields["target_resolution_error"] = None
    return fields


def section_reference_name(name: str) -> str:
    """Trigger references use the section name without the trailing '.gd'."""
    return name[:-3] if name.lower().endswith(".gd") else name


def resolve_trigger_targets(eff: EFFFile) -> None:
    """Resolve every trigger to the model/particle record it references."""
    sections_by_kind = {section.kind: section for section in eff.sections}
    trigger_section = sections_by_kind.get("trigger")
    if trigger_section is None:
        return

    for rec in trigger_section.records:
        kind = rec["target_type_name"]
        if kind not in ("particle", "model"):
            rec["target_resolution_error"] = f"unknown target type {rec['target_type']}"
            continue

        target_section = sections_by_kind.get(kind)
        if target_section is None:
            rec["target_resolution_error"] = f"file has no {kind} section"
            continue

        rec["target_section"] = target_section.name
        expected_ref = section_reference_name(target_section.name)
        rec["target_reference_matches_section"] = rec["target_reference"] == expected_ref
        if not rec["target_reference_matches_section"]:
            rec["target_resolution_error"] = (
                f"reference {rec['target_reference']!r} != expected {expected_ref!r}"
            )
            continue

        target_index = rec["target_index"]
        if target_index >= len(target_section.records):
            rec["target_resolution_error"] = (
                f"target index {target_index} outside {kind} record count "
                f"{len(target_section.records)}"
            )
            continue

        target = target_section.records[target_index]
        rec["target_file_offset"] = target["file_offset"]
        rec["target_name"] = (
            target.get("name_00") if kind == "particle" else target.get("name_04")
        )
        rec["target_resolved"] = True


def parse_records(kind: str, data: bytes, data_offset: int) -> list[dict[str, Any]]:
    if kind == "model":
        record_size = MODEL_RECORD_SIZE
        parser = parse_model_record
    elif kind == "particle":
        record_size = PARTICLE_RECORD_SIZE
        parser = parse_particle_record
    elif kind == "trigger":
        record_size = TRIGGER_RECORD_SIZE
        parser = parse_trigger_record
    else:
        return []

    if len(data) % record_size != 0:
        raise EFFError(
            f"{kind} section size 0x{len(data):X} is not divisible by record size 0x{record_size:X}"
        )

    records = []
    for i in range(len(data) // record_size):
        start = i * record_size
        record = data[start:start + record_size]
        records.append(parser(record, i, data_offset + start))
    return records


def parse_eff_bytes(data: bytes, path: str = "<memory>") -> EFFFile:
    if len(data) < 8:
        raise EFFError("File is smaller than the 8-byte header")

    field_00 = u32(data, 0x00)
    eff_type = u32(data, 0x04)

    if field_00 != 0:
        raise EFFError(f"Unexpected field_00 value: 0x{field_00:08X} (expected 0)")

    if eff_type not in EXPECTED_LAYOUTS:
        raise EFFError(f"Unknown EFF type {eff_type}; expected 2 or 3")

    offset = 0x08
    sections: list[Section] = []

    while offset < len(data):
        section_header = offset
        name, size_offset = read_aligned_cstring(data, offset)

        if size_offset + 4 > len(data):
            raise EFFError(f"Missing section size after {name!r}")

        size = u32(data, size_offset)
        data_offset = size_offset + 4
        end = data_offset + size

        if end > len(data):
            raise EFFError(
                f"Section {name!r} claims 0x{size:X} bytes, ending at 0x{end:X}, past EOF 0x{len(data):X}"
            )

        kind = section_kind(name)
        payload = data[data_offset:end]
        records = parse_records(kind, payload, data_offset)

        sections.append(
            Section(
                name=name,
                kind=kind,
                header_offset=section_header,
                data_offset=data_offset,
                size=size,
                records=records,
            )
        )
        offset = end

    if offset != len(data):
        raise EFFError(f"Parser stopped at 0x{offset:X}; EOF is 0x{len(data):X}")

    actual_layout = tuple(section.kind for section in sections)
    expected_layout = EXPECTED_LAYOUTS[eff_type]
    if actual_layout != expected_layout:
        raise EFFError(
            f"Type {eff_type} section order is {actual_layout}, expected {expected_layout}"
        )

    eff = EFFFile(
        path=path,
        file_size=len(data),
        field_00=field_00,
        type=eff_type,
        sections=sections,
    )
    resolve_trigger_targets(eff)
    return eff


def parse_eff_file(path: Path) -> EFFFile:
    return parse_eff_bytes(path.read_bytes(), str(path))


def record_count(eff: EFFFile, kind: str) -> int:
    for section in eff.sections:
        if section.kind == kind:
            return len(section.records)
    return 0


def format_float(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.9g}"
    return str(value)


def format_eff(eff: EFFFile, include_raw: bool = False) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append(f"File      : {eff.path}")
    lines.append(f"Size      : {eff.file_size} bytes (0x{eff.file_size:X})")
    lines.append(f"field_00  : 0x{eff.field_00:08X}")
    lines.append(f"Type      : {eff.type}")
    lines.append("=" * 78)

    for section in eff.sections:
        record_size = {
            "model": MODEL_RECORD_SIZE,
            "particle": PARTICLE_RECORD_SIZE,
            "trigger": TRIGGER_RECORD_SIZE,
        }.get(section.kind)

        lines.append("")
        lines.append(f"[{section.kind.upper()}] {section.name}")
        lines.append(f"  header offset : 0x{section.header_offset:X}")
        lines.append(f"  data offset   : 0x{section.data_offset:X}")
        lines.append(f"  data size     : {section.size} bytes (0x{section.size:X})")
        lines.append(f"  records       : {len(section.records)}")
        if record_size is not None:
            lines.append(f"  record size   : 0x{record_size:X}")

        for rec in section.records:
            lines.append("")
            lines.append(f"  Record {rec['index']} @ file+0x{rec['file_offset']:X}")

            if section.kind == "model":
                lines.append(f"    field_00_u32 : {rec['field_00_u32']}")
                lines.append(f"    name_04      : {rec['name_04']!r}")
                for off in ("20", "28", "30", "38", "40", "48"):
                    lines.append(f"    field_{off}     : {rec[f'field_{off}']!r}")
                lines.append(f"    field_50_u32 : {rec['field_50_u32']}")
                lines.append(f"    field_54_f32 : {format_float(rec['field_54_f32'])}")
                lines.append(f"    field_58_f32 : {format_float(rec['field_58_f32'])}")

            elif section.kind == "particle":
                lines.append(f"    name_00      : {rec['name_00']!r}")
                lines.append(f"    field_20     : {rec['field_20']!r}")
                lines.append(f"    field_28_u32 : {rec['field_28_u32']}")
                lines.append(f"    field_2C     : {rec['field_2C']!r}")
                for off in ("40", "44", "48", "4C", "50"):
                    lines.append(f"    field_{off}_f32 : {format_float(rec[f'field_{off}_f32'])}")

            elif section.kind == "trigger":
                lines.append(
                    f"    trigger_id?   : {rec['trigger_id_candidate']} "
                    f"(field +0x00; semantic name inferred)"
                )
                lines.append(
                    f"    target_type   : {rec['target_type']} "
                    f"({rec['target_type_name']})"
                )
                lines.append(f"    target_ref    : {rec['target_reference']!r}")
                lines.append(f"    target_section: {rec['target_section']!r}")
                lines.append(f"    target_index  : {rec['target_index']}")
                lines.append(f"    target_name   : {rec['target_name']!r}")
                if rec["target_file_offset"] is not None:
                    lines.append(f"    target_offset : file+0x{rec['target_file_offset']:X}")
                lines.append(
                    f"    reserved_4C-4E: {rec['reserved_4C_4E']} "
                    f"({'zero' if rec['reserved_4C_4E_is_zero'] else 'NONZERO'})"
                )
                lines.append(
                    f"    resolved      : {'yes' if rec['target_resolved'] else 'NO'}"
                )
                if rec["target_resolution_error"]:
                    lines.append(
                        f"    resolve error : {rec['target_resolution_error']}"
                    )

                # Unknown 32-bit fields. +0x00 and +0x28 are shown above with
                # their current best interpretations, so omit them here.
                for off in range(0x04, 0x28, 4):
                    key = f"field_{off:02X}"
                    lines.append(
                        f"    unknown_{off:02X}   : {rec[key + '_hex']}"
                        f" | u32={rec[key + '_u32']}"
                        f" | s32={rec[key + '_s32']}"
                        f" | f32={format_float(rec[key + '_f32'])}"
                    )

            if include_raw:
                lines.append(f"    raw          : {rec['raw_hex']}")

    return "\n".join(lines)


def eff_to_dict(eff: EFFFile) -> dict[str, Any]:
    return asdict(eff)


def find_eff_files(root: Path) -> list[Path]:
    """Find only the original KIU effect definition files."""
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.name.lower() == "eff_00.bin"
    )


def analyse_directory(root: Path) -> tuple[list[EFFFile], list[tuple[Path, str]]]:
    parsed: list[EFFFile] = []
    failures: list[tuple[Path, str]] = []

    for path in find_eff_files(root):
        try:
            parsed.append(parse_eff_file(path))
        except Exception as exc:
            failures.append((path, str(exc)))

    return parsed, failures


def print_corpus_summary(parsed: list[EFFFile], failures: list[tuple[Path, str]]) -> None:
    print("=" * 78)
    print("KIU EFF CORPUS SUMMARY")
    print("=" * 78)
    print(f"Parsed successfully : {len(parsed)}")
    print(f"Failed              : {len(failures)}")

    type_counts = Counter(eff.type for eff in parsed)
    print("\nTypes:")
    for typ, count in sorted(type_counts.items()):
        print(f"  type {typ}: {count}")

    layouts = Counter(tuple(section.kind for section in eff.sections) for eff in parsed)
    print("\nSection layouts:")
    for layout, count in layouts.most_common():
        print(f"  {count:4d} x {' -> '.join(layout)}")

    for kind in ("model", "particle", "trigger"):
        counts = [record_count(eff, kind) for eff in parsed if any(s.kind == kind for s in eff.sections)]
        if counts:
            print(
                f"\n{kind.capitalize()} records: "
                f"files={len(counts)}, total={sum(counts)}, min={min(counts)}, max={max(counts)}"
            )

    trigger_records = [
        rec
        for eff in parsed
        for section in eff.sections
        if section.kind == "trigger"
        for rec in section.records
    ]
    if trigger_records:
        resolved = sum(bool(rec.get("target_resolved")) for rec in trigger_records)
        refs_match = sum(
            bool(rec.get("target_reference_matches_section")) for rec in trigger_records
        )
        zero_reserved = sum(
            bool(rec.get("reserved_4C_4E_is_zero")) for rec in trigger_records
        )
        target_counts = Counter(rec.get("target_type_name") for rec in trigger_records)
        print("\nTrigger target resolution:")
        print(f"  resolved targets : {resolved}/{len(trigger_records)}")
        print(f"  section refs OK  : {refs_match}/{len(trigger_records)}")
        print(f"  reserved 4C-4E=0: {zero_reserved}/{len(trigger_records)}")
        for kind, count in sorted(target_counts.items()):
            print(f"  {kind:9s} targets: {count}")

    if failures:
        print("\nFailures:")
        for path, error in failures:
            print(f"  {path}: {error}")


def sidecar_path(src: Path) -> Path:
    """eff_00.bin -> eff_00.bin.txt in the original directory."""
    return src.with_name(src.name + ".txt")


def write_in_place_dumps(parsed: list[EFFFile], include_raw: bool) -> int:
    """Write one parsed text dump next to every original eff_00.bin."""
    written = 0
    for eff in parsed:
        src = Path(eff.path)
        out = sidecar_path(src)
        out.write_text(format_eff(eff, include_raw=include_raw), encoding="utf-8")
        written += 1
    return written


def write_external_dumps(
    parsed: list[EFFFile],
    rom_root: Path,
    external_dir: Path,
    include_raw: bool,
    flat: bool = False,
) -> int:
    """
    Write a second copy outside the ROM tree.

    By default the original directory structure is mirrored so identical
    eff_00.bin filenames never collide. With flat=True, the relative path is
    encoded into the filename using '__'.
    """
    external_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for eff in parsed:
        src = Path(eff.path)
        try:
            rel = src.relative_to(rom_root)
        except ValueError:
            rel = Path(src.name)

        if flat:
            encoded = "__".join(rel.parts) + ".txt"
            out = external_dir / encoded
        else:
            out = external_dir / rel.with_suffix(rel.suffix + ".txt")
            out.parent.mkdir(parents=True, exist_ok=True)

        out.write_text(format_eff(eff, include_raw=include_raw), encoding="utf-8")
        written += 1

    return written


def write_json_dumps(parsed: list[EFFFile], root: Path, json_dir: Path) -> None:
    json_dir.mkdir(parents=True, exist_ok=True)
    for eff in parsed:
        src = Path(eff.path)
        try:
            rel = src.relative_to(root)
        except ValueError:
            rel = Path(src.name)

        out = json_dir / rel.with_suffix(rel.suffix + ".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(eff_to_dict(eff), indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse Kid Icarus: Uprising eff_00.bin effect-definition files."
    )
    parser.add_argument(
        "path",
        type=Path,
        help="A single eff_00.bin file, or the ROM/RomFS directory to scan recursively",
    )
    parser.add_argument("--raw", action="store_true", help="Include raw record hex in text output")
    parser.add_argument("--json", action="store_true", help="For a single file, print JSON instead of text")
    parser.add_argument(
        "--external-dir",
        type=Path,
        help="Directory OUTSIDE the ROM tree where a second parsed copy is written",
    )
    parser.add_argument(
        "--flat-external",
        action="store_true",
        help="Put external dumps in one flat folder using path-encoded filenames",
    )
    parser.add_argument(
        "--no-in-place",
        action="store_true",
        help="Do not write eff_00.bin.txt beside the original files",
    )
    parser.add_argument("--json-dir", type=Path, help="Optional: also write JSON dumps in this directory")
    args = parser.parse_args()

    path = args.path
    if not path.exists():
        print(f"error: path does not exist: {path}", file=sys.stderr)
        return 2

    if path.is_file():
        try:
            eff = parse_eff_file(path)
        except Exception as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(eff_to_dict(eff), indent=2, ensure_ascii=False))
        else:
            print(format_eff(eff, include_raw=args.raw))
        return 0

    rom_root = path.resolve()
    parsed, failures = analyse_directory(rom_root)
    print_corpus_summary(parsed, failures)

    if not args.no_in_place:
        n = write_in_place_dumps(parsed, include_raw=args.raw)
        print(f"\nIn-place parsed dumps : {n}")
        print("  Each original eff_00.bin now has an eff_00.bin.txt beside it.")

    if args.external_dir:
        external_dir = args.external_dir.resolve()

        # Prevent accidentally choosing a destination inside the ROM tree.
        try:
            external_dir.relative_to(rom_root)
        except ValueError:
            pass
        else:
            print(
                f"error: --external-dir must be outside the scanned ROM tree: {rom_root}",
                file=sys.stderr,
            )
            return 2

        n = write_external_dumps(
            parsed,
            rom_root,
            external_dir,
            include_raw=args.raw,
            flat=args.flat_external,
        )
        print(f"External parsed dumps : {n}")
        print(f"  {external_dir}")

    if args.json_dir:
        write_json_dumps(parsed, rom_root, args.json_dir)
        print(f"JSON dumps written to: {args.json_dir}")

    if not args.external_dir:
        print("\nTip: add --external-dir <folder> to also write a second copy outside the ROM tree.")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
