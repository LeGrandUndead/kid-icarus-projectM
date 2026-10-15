from pathlib import Path
import struct
import sys
from dataclasses import dataclass


@dataclass
class EffSection:
    name: str
    size: int
    record_size: int
    records: list[bytes]


@dataclass
class EffFile:
    field_00: int
    eff_type: int
    sections: list[EffSection]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u32(value: int) -> bytes:
    return struct.pack("<I", value)


def align4(value: int) -> int:
    return (value + 3) & ~3


def read_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.index(b"\x00", offset)
    text = data[offset:end].decode("ascii")
    return text, align4(end + 1)


def write_string(text: str) -> bytes:
    out = bytearray(text.encode("ascii") + b"\x00")
    while len(out) % 4:
        out += b"\x00"
    return bytes(out)


def get_record_size(name: str) -> int:
    if name.startswith("effectModelData_"):
        return 0x5C
    if name.startswith("effectParticleData_"):
        return 0x54
    if name.startswith("effectTriggerData_"):
        return 0x50
    raise ValueError(f"Unknown section type: {name}")


def parse_eff(data: bytes) -> EffFile:
    if len(data) < 8:
        raise ValueError("File is too small to contain an EFF header")

    offset = 0
    field_00 = read_u32(data, offset)
    offset += 4
    eff_type = read_u32(data, offset)
    offset += 4

    sections = []

    while offset < len(data):
        name, offset = read_string(data, offset)

        if offset + 4 > len(data):
            raise ValueError(f"{name}: missing section size")

        section_size = read_u32(data, offset)
        offset += 4

        record_size = get_record_size(name)

        if section_size % record_size != 0:
            raise ValueError(
                f"{name}: section size {section_size:#x} is not divisible "
                f"by record size {record_size:#x}"
            )

        section_end = offset + section_size
        if section_end > len(data):
            raise ValueError(
                f"{name}: section ends at {section_end:#x}, "
                f"beyond file size {len(data):#x}"
            )

        record_count = section_size // record_size
        records = []

        for i in range(record_count):
            record_start = offset + i * record_size
            record_end = record_start + record_size

            if record_end > section_end:
                raise ValueError(f"{name}: record {i} exceeds section boundary")

            records.append(data[record_start:record_end])

        sections.append(
            EffSection(
                name=name,
                size=section_size,
                record_size=record_size,
                records=records,
            )
        )

        offset = section_end

    if offset != len(data):
        raise ValueError(
            f"Parser ended at {offset:#x}, file size is {len(data):#x}"
        )

    return EffFile(
        field_00=field_00,
        eff_type=eff_type,
        sections=sections,
    )


def serialize_eff(eff: EffFile) -> bytes:
    out = bytearray()
    out += write_u32(eff.field_00)
    out += write_u32(eff.eff_type)

    for section in eff.sections:
        out += write_string(section.name)

        section_data = b"".join(section.records)

        if len(section_data) % section.record_size != 0:
            raise ValueError(
                f"{section.name}: rebuilt section size {len(section_data):#x} "
                f"is not divisible by record size {section.record_size:#x}"
            )

        out += write_u32(len(section_data))
        out += section_data

    return bytes(out)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_eff_roundtrip.py <RomFS-or-folder>")
        return 1

    root = Path(sys.argv[1])

    if not root.exists():
        print(f"ERROR: path does not exist: {root}")
        return 1

    files = [root] if root.is_file() else sorted(root.rglob("eff_00.bin"))

    if not files:
        print("No eff_00.bin files found.")
        return 1

    passed = 0
    failed = []
    type_counts = {}
    layout_counts = {}

    for i, path in enumerate(files, 1):
        try:
            original = path.read_bytes()
            eff = parse_eff(original)
            rebuilt = serialize_eff(eff)

            if rebuilt != original:
                raise ValueError(
                    f"round-trip mismatch "
                    f"(original={len(original)} bytes, rebuilt={len(rebuilt)} bytes)"
                )

            passed += 1
            type_counts[eff.eff_type] = type_counts.get(eff.eff_type, 0) + 1

            layout = " -> ".join(
                "model" if s.name.startswith("effectModelData_")
                else "particle" if s.name.startswith("effectParticleData_")
                else "trigger" if s.name.startswith("effectTriggerData_")
                else "unknown"
                for s in eff.sections
            )
            layout_counts[layout] = layout_counts.get(layout, 0) + 1

            print(f"[{i:>3}/{len(files)}] OK   {path}")
        except Exception as exc:
            failed.append((path, str(exc)))
            print(f"[{i:>3}/{len(files)}] FAIL {path}")
            print(f"             {exc}")

    print()
    print("=" * 72)
    print("EFF ROUND-TRIP SUMMARY")
    print("=" * 72)
    print(f"Files found     : {len(files)}")
    print(f"Exact matches   : {passed}")
    print(f"Failures        : {len(failed)}")

    if type_counts:
        print()
        print("Types:")
        for eff_type, count in sorted(type_counts.items()):
            print(f"  type {eff_type}: {count}")

    if layout_counts:
        print()
        print("Section layouts:")
        for layout, count in sorted(layout_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {count:>4} x {layout}")

    if failed:
        print()
        print("Failures:")
        for path, reason in failed:
            print(f"  {path}")
            print(f"    {reason}")

    print()

    if not failed:
        print("SUCCESS: every EFF file rebuilt byte-for-byte identically.")
        return 0

    print("Some files failed; EFF outer format is not yet fully validated.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
