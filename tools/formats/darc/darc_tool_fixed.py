from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import struct
import sys


@dataclass
class DarcEntry:
    index: int
    path: str
    is_dir: bool
    name_offset: int
    field1: int
    field2: int
    data_offset: int | None = None
    size: int | None = None


@dataclass
class DarcArchive:
    file_size: int
    table_offset: int
    table_length: int
    data_offset: int
    entries: list[DarcEntry]


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def read_utf16z(data: bytes, off: int) -> str:
    if off < 0 or off >= len(data):
        raise ValueError(f"name offset out of range: 0x{off:X}")

    end = off
    while end + 1 < len(data):
        if data[end:end+2] == b"\x00\x00":
            raw = data[off:end]
            return raw.decode("utf-16le", errors="strict")
        end += 2

    raise ValueError(f"unterminated UTF-16LE name at 0x{off:X}")


def parse_darc(data: bytes) -> DarcArchive:
    if len(data) < 0x1C:
        raise ValueError("file too small for DARC header")
    if data[:4] != b"darc":
        raise ValueError("not a DARC archive")
    if data[4:6] != b"\xFF\xFE":
        raise ValueError(f"unsupported BOM: {data[4:6].hex(' ')}")

    header_size = u16(data, 0x06)
    file_size = u32(data, 0x0C)
    table_offset = u32(data, 0x10)
    table_length = u32(data, 0x14)
    data_offset = u32(data, 0x18)

    if header_size < 0x1C:
        raise ValueError(f"unexpected header size: 0x{header_size:X}")
    if file_size > len(data):
        raise ValueError(
            f"declared file size 0x{file_size:X} exceeds actual 0x{len(data):X}"
        )
    if table_offset + 12 > len(data):
        raise ValueError("root entry is truncated")

    # Root entry's third u32 is the end-index / total number of entries.
    entry_count = u32(data, table_offset + 8)
    if entry_count <= 0:
        raise ValueError("invalid entry count")

    entries_end = table_offset + entry_count * 12
    table_end = table_offset + table_length

    if entries_end > table_end:
        raise ValueError(
            f"entry structs end at 0x{entries_end:X}, beyond table end 0x{table_end:X}"
        )
    if table_end > len(data):
        raise ValueError("declared file table exceeds file")

    # Important DARC detail:
    # the low 24 bits are a BYTE offset from the start of the name table
    # (the area immediately after the entry structs), NOT UTF-16 code units.
    name_table_start = entries_end

    entries: list[DarcEntry] = []
    dir_stack: list[tuple[int, str]] = []

    for i in range(entry_count):
        off = table_offset + i * 12
        name_flags = u32(data, off)
        field1 = u32(data, off + 4)
        field2 = u32(data, off + 8)

        is_dir = bool(name_flags & 0x01000000)
        name_offset = name_flags & 0x00FFFFFF

        name = read_utf16z(data, name_table_start + name_offset)

        if i == 0:
            # Root node. Keep a stable display name but do not include it in paths.
            entries.append(
                DarcEntry(
                    index=i,
                    path=name or ".",
                    is_dir=True,
                    name_offset=name_offset,
                    field1=field1,
                    field2=field2,
                )
            )
            continue

        while dir_stack and i >= dir_stack[-1][0]:
            dir_stack.pop()

        parent_parts = [x[1] for x in dir_stack]
        full_path = "/".join(parent_parts + [name]) if parent_parts else name

        if is_dir:
            subtree_end = field2
            if subtree_end <= i or subtree_end > entry_count:
                raise ValueError(
                    f"directory entry {i} has invalid subtree end {subtree_end}"
                )

            entries.append(
                DarcEntry(
                    index=i,
                    path=full_path,
                    is_dir=True,
                    name_offset=name_offset,
                    field1=field1,
                    field2=field2,
                )
            )
            dir_stack.append((subtree_end, name))
        else:
            file_off = field1
            size = field2
            end = file_off + size

            if end > len(data):
                raise ValueError(
                    f"file entry {i} ({full_path}) exceeds archive: "
                    f"0x{file_off:X}+0x{size:X} > 0x{len(data):X}"
                )

            entries.append(
                DarcEntry(
                    index=i,
                    path=full_path,
                    is_dir=False,
                    name_offset=name_offset,
                    field1=field1,
                    field2=field2,
                    data_offset=file_off,
                    size=size,
                )
            )

    return DarcArchive(
        file_size=file_size,
        table_offset=table_offset,
        table_length=table_length,
        data_offset=data_offset,
        entries=entries,
    )


def safe_output_path(root: Path, rel: str) -> Path:
    # DARC paths use '/'.
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    out = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()

    if root_resolved != out and root_resolved not in out.parents:
        raise ValueError(f"unsafe path in archive: {rel}")

    return out


def cmd_list(path: Path) -> int:
    data = path.read_bytes()
    arc = parse_darc(data)

    print(f"File size   : {arc.file_size} (0x{arc.file_size:X})")
    print(f"Table offset: 0x{arc.table_offset:X}")
    print(f"Table length: 0x{arc.table_length:X}")
    print(f"Data offset : 0x{arc.data_offset:X}")
    print(f"Entries     : {len(arc.entries)}")
    print()

    for e in arc.entries:
        if e.is_dir:
            print(f"[DIR ] #{e.index:4d} end={e.field2:4d}  {e.path}")
        else:
            print(
                f"[FILE] #{e.index:4d} "
                f"off=0x{e.data_offset:X} size=0x{e.size:X}  {e.path}"
            )

    return 0


def cmd_verify(path: Path) -> int:
    data = path.read_bytes()
    arc = parse_darc(data)

    files = sum(1 for e in arc.entries if not e.is_dir)
    dirs = sum(1 for e in arc.entries if e.is_dir)

    print(f"OK: {path}")
    print(f"entries={len(arc.entries)} dirs={dirs} files={files}")
    return 0


def cmd_extract(path: Path, out_dir: Path) -> int:
    data = path.read_bytes()
    arc = parse_darc(data)
    out_dir.mkdir(parents=True, exist_ok=True)

    extracted = 0

    for e in arc.entries:
        if e.index == 0:
            continue

        target = safe_output_path(out_dir, e.path)

        if e.is_dir:
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data[e.data_offset:e.data_offset + e.size])
        extracted += 1

    print(f"Extracted {extracted} files to {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Small DARC reader/extractor with byte-correct filename offsets."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("archive", type=Path)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("archive", type=Path)

    p_extract = sub.add_parser("extract")
    p_extract.add_argument("archive", type=Path)
    p_extract.add_argument("output", type=Path)

    args = parser.parse_args()

    try:
        if args.cmd == "list":
            return cmd_list(args.archive)
        if args.cmd == "verify":
            return cmd_verify(args.archive)
        if args.cmd == "extract":
            return cmd_extract(args.archive, args.output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
