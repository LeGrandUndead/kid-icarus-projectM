from pathlib import Path
import struct
from dataclasses import dataclass
import sys

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

#"D:\Games\Kid icarus\ROM\gameFiles\RomFS\us\doll\000\doll\eff_00.bin"
if len(sys.argv) < 2:
    print("Usage: python inspect_eff.py <eff_00.bin>")
    sys.exit(1)

FILE = Path(sys.argv[1])

def read_u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def align4(value):
    while value % 4 != 0:
        value += 1
    return value


def read_string(data, offset):
    # TODO:
    end = data.index(b"\x00", offset)
    text = data[offset:end].decode("ascii")
    new_offset = end + 1
    new_offset = align4(new_offset)
    return text, new_offset


def get_record_size(name):
    if name.startswith("effectModelData_"):
        return 0x5C

    if name.startswith("effectParticleData_"):
        return 0x54

    if name.startswith("effectTriggerData_"):
        return 0x50

    raise ValueError(f"Unknown section type: {name}")


def parse_eff(data):
    offset = 0

    field_00 = read_u32(data, offset)
    offset += 4

    eff_type = read_u32(data, offset)
    offset += 4

    sections = []

    while offset < len(data):
        name, offset = read_string(data, offset)

        section_size = read_u32(data, offset)
        offset += 4

        record_size = get_record_size(name)

        if section_size % record_size != 0:
            raise ValueError(
                f"{name}: section size {section_size} "
                f"is not divisible by record size {record_size}"
            )

        record_count = section_size // record_size

        records = []

        for i in range(record_count):
            record_start = offset + i * record_size
            record_end = record_start + record_size

            if record_end > len(data):
                raise ValueError("Record extends beyond end of file")

            record_data = data[record_start:record_end]
            records.append(record_data)

        section = EffSection(
            name=name,
            size=section_size,
            record_size=record_size,
            records=records
        )

        sections.append(section)

        offset += section_size

    if offset != len(data):
        raise ValueError(
            f"Parser ended at {hex(offset)}, "
            f"but file size is {hex(len(data))}"
        )

    return EffFile(
        field_00=field_00,
        eff_type=eff_type,
        sections=sections
    )

def write_u32(value):
    return struct.pack("<I", value)

def write_string(text):
    data = bytearray()

    data += text.encode("ascii")
    data += b"\x00"

    while len(data) % 4 != 0:
        data += b"\x00"

    return bytes(data)

def serialize_eff(eff):
    out = bytearray()

    # Header
    out += write_u32(eff.field_00)
    out += write_u32(eff.eff_type)

    # Sections
    for section in eff.sections:

        # Section name + alignment
        out += write_string(section.name)

        # Rebuild section data from the records
        section_data = b"".join(section.records)

        # Write calculated size
        out += write_u32(len(section_data))

        # Write records
        out += section_data

    return bytes(out)


if __name__ == "__main__":
    data = FILE.read_bytes()

    eff = parse_eff(data)

    print("field_00:", eff.field_00)
    print("type:", eff.eff_type)

    print()

    for section in eff.sections:
        print(
            section.name,
            "-",
            len(section.records),
            "records"
        )

    rebuilt = serialize_eff(eff)

    print()
    print("original size:", len(data))
    print("rebuilt size :", len(rebuilt))

    if data == rebuilt:
        print("ROUNDTRIP SUCCESS: rebuilt file is byte-identical")
    else:
        print("ROUNDTRIP FAILED")