from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import math
import struct
import sys


class PslbError(ValueError):
    pass


@dataclass
class PslbString:
    raw: bytes

    def text(self) -> str:
        try:
            return self.raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return self.raw.decode("cp932")
            except UnicodeDecodeError:
                return self.raw.decode("latin-1")


@dataclass
class PslbInt:
    value: int


@dataclass
class PslbFloat:
    value: float


@dataclass
class PslbByte:
    value: int


@dataclass
class PslbMap:
    items: list[tuple[bytes, "PslbNode"]]


@dataclass
class PslbList:
    items: list["PslbNode"]


PslbNode = PslbString | PslbInt | PslbFloat | PslbByte | PslbMap | PslbList


@dataclass
class PslbFile:
    header_04: int
    header_08: int
    header_0c: int
    root: PslbNode


def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise PslbError(f"Unexpected EOF reading u32 at 0x{offset:X}")
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def _read_i32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise PslbError(f"Unexpected EOF reading i32 at 0x{offset:X}")
    return struct.unpack_from("<i", data, offset)[0], offset + 4


def _read_f32(data: bytes, offset: int) -> tuple[float, int]:
    if offset + 4 > len(data):
        raise PslbError(f"Unexpected EOF reading f32 at 0x{offset:X}")
    return struct.unpack_from("<f", data, offset)[0], offset + 4


def _read_raw_string(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = _read_u32(data, offset)
    end = offset + length
    if end > len(data):
        raise PslbError(
            f"String at 0x{offset - 4:X} declares {length} bytes beyond EOF"
        )
    return data[offset:end], end


def _parse_node(data: bytes, offset: int, depth: int = 0) -> tuple[PslbNode, int]:
    if depth > 2048:
        raise PslbError("PSLB nesting depth is unreasonable")
    if offset >= len(data):
        raise PslbError("Unexpected EOF reading PSLB type")

    type_offset = offset
    type_id = data[offset]
    offset += 1

    if type_id == 1:  # string
        raw, offset = _read_raw_string(data, offset)
        return PslbString(raw), offset

    if type_id == 2:  # int32
        value, offset = _read_i32(data, offset)
        return PslbInt(value), offset

    if type_id == 3:  # float32
        value, offset = _read_f32(data, offset)
        return PslbFloat(value), offset

    if type_id == 4:  # byte
        if offset >= len(data):
            raise PslbError(f"Unexpected EOF reading byte at 0x{offset:X}")
        return PslbByte(data[offset]), offset + 1

    if type_id == 5:  # map
        count, offset = _read_u32(data, offset)
        items: list[tuple[bytes, PslbNode]] = []
        seen: set[bytes] = set()

        for _ in range(count):
            # Map keys are strings without a leading type byte.
            key, offset = _read_raw_string(data, offset)
            if key in seen:
                raise PslbError(f"Duplicate map key at/after 0x{type_offset:X}")
            seen.add(key)

            value, offset = _parse_node(data, offset, depth + 1)
            items.append((key, value))

        return PslbMap(items), offset

    if type_id == 6:  # list
        count, offset = _read_u32(data, offset)
        items: list[PslbNode] = []

        for _ in range(count):
            value, offset = _parse_node(data, offset, depth + 1)
            items.append(value)

        return PslbList(items), offset

    raise PslbError(f"Unknown PSLB type 0x{type_id:02X} at 0x{type_offset:X}")


def parse_pslb(data: bytes) -> PslbFile:
    if len(data) < 0x11:
        raise PslbError("File is too small to be PSLB")
    if data[:4] != b"PSLB":
        raise PslbError("Missing PSLB magic")

    header_04, header_08, header_0c = struct.unpack_from("<III", data, 4)
    root, end = _parse_node(data, 0x10)

    if end != len(data):
        raise PslbError(
            f"Parser stopped at 0x{end:X}, but file ends at 0x{len(data):X}"
        )

    return PslbFile(header_04, header_08, header_0c, root)


def _write_raw_string(raw: bytes) -> bytes:
    return struct.pack("<I", len(raw)) + raw


def _serialize_node(node: PslbNode) -> bytes:
    if isinstance(node, PslbString):
        return b"\x01" + _write_raw_string(node.raw)

    if isinstance(node, PslbInt):
        return b"\x02" + struct.pack("<i", node.value)

    if isinstance(node, PslbFloat):
        return b"\x03" + struct.pack("<f", node.value)

    if isinstance(node, PslbByte):
        if not 0 <= node.value <= 0xFF:
            raise PslbError(f"Byte value outside range: {node.value}")
        return b"\x04" + bytes([node.value])

    if isinstance(node, PslbMap):
        out = bytearray(b"\x05" + struct.pack("<I", len(node.items)))
        for key, value in node.items:
            out += _write_raw_string(key)
            out += _serialize_node(value)
        return bytes(out)

    if isinstance(node, PslbList):
        out = bytearray(b"\x06" + struct.pack("<I", len(node.items)))
        for value in node.items:
            out += _serialize_node(value)
        return bytes(out)

    raise TypeError(f"Unsupported PSLB node: {type(node)!r}")


def serialize_pslb(pslb: PslbFile) -> bytes:
    return (
        b"PSLB"
        + struct.pack("<III", pslb.header_04, pslb.header_08, pslb.header_0c)
        + _serialize_node(pslb.root)
    )


def _decode_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp932")
        except UnicodeDecodeError:
            return raw.decode("latin-1")


def to_python(node: PslbNode):
    if isinstance(node, PslbString):
        return _decode_text(node.raw)
    if isinstance(node, PslbInt):
        return node.value
    if isinstance(node, PslbFloat):
        return node.value
    if isinstance(node, PslbByte):
        return node.value
    if isinstance(node, PslbMap):
        return {_decode_text(k): to_python(v) for k, v in node.items}
    if isinstance(node, PslbList):
        return [to_python(v) for v in node.items]
    raise TypeError(type(node))


def _root_keys(pslb: PslbFile) -> list[str]:
    if not isinstance(pslb.root, PslbMap):
        return []
    return [_decode_text(key) for key, _ in pslb.root.items]


def command_inspect(path: Path) -> int:
    data = path.read_bytes()
    pslb = parse_pslb(data)

    print(f"File       : {path}")
    print(f"Size       : {len(data)} bytes (0x{len(data):X})")
    print(f"Header +04 : {pslb.header_04} (0x{pslb.header_04:X})")
    print(f"Header +08 : {pslb.header_08} (0x{pslb.header_08:X})")
    print(f"Header +0C : {pslb.header_0c} (0x{pslb.header_0c:X})")
    print(f"Root type  : {type(pslb.root).__name__}")

    keys = _root_keys(pslb)
    if keys:
        print(f"Root keys  : {len(keys)}")
        for key in keys:
            print(f"  {key}")

    return 0


def command_json(path: Path, output: Path | None) -> int:
    pslb = parse_pslb(path.read_bytes())
    payload = {
        "_pslb_header": {
            "field_04": pslb.header_04,
            "field_08": pslb.header_08,
            "field_0c": pslb.header_0c,
        },
        "data": to_python(pslb.root),
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)

    if output is None:
        print(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(output)

    return 0


def command_roundtrip(path: Path) -> int:
    files = [path] if path.is_file() else sorted(
        p for p in path.rglob("*") if p.is_file()
    )

    checked = 0
    exact = 0
    skipped = 0
    failed: list[tuple[Path, str]] = []

    for file in files:
        try:
            with file.open("rb") as f:
                if f.read(4) != b"PSLB":
                    skipped += 1
                    continue

            original = file.read_bytes()
            parsed = parse_pslb(original)
            rebuilt = serialize_pslb(parsed)
            checked += 1

            if rebuilt == original:
                exact += 1
            else:
                first_diff = next(
                    (i for i, (a, b) in enumerate(zip(original, rebuilt)) if a != b),
                    min(len(original), len(rebuilt)),
                )
                failed.append((file, f"first byte mismatch at 0x{first_diff:X}"))

        except Exception as exc:
            checked += 1
            failed.append((file, str(exc)))

        if checked and checked % 500 == 0:
            print(f"checked={checked} exact={exact} failed={len(failed)}", flush=True)

    print()
    print("PSLB ROUND-TRIP")
    print("=" * 64)
    print(f"Checked PSLB : {checked}")
    print(f"Exact matches: {exact}")
    print(f"Failures     : {len(failed)}")
    print(f"Non-PSLB skip: {skipped}")

    if failed:
        print()
        for file, reason in failed[:50]:
            print(f"FAIL {file}")
            print(f"     {reason}")
        return 2

    print("SUCCESS: every checked PSLB rebuilt byte-for-byte identically.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kid Icarus / NW4C PSLB research tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Show header and root keys")
    p_inspect.add_argument("file", type=Path)

    p_json = sub.add_parser("json", help="Decode a PSLB into readable JSON")
    p_json.add_argument("file", type=Path)
    p_json.add_argument("-o", "--output", type=Path)

    p_round = sub.add_parser("roundtrip", help="Parse and rebuild all PSLBs exactly")
    p_round.add_argument("path", type=Path)

    args = parser.parse_args()

    if args.command == "inspect":
        return command_inspect(args.file)
    if args.command == "json":
        return command_json(args.file, args.output)
    if args.command == "roundtrip":
        return command_roundtrip(args.path)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
