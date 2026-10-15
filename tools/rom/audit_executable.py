"""Validate an extracted 3DS executable and optionally its original NCSD/NCCH.

Read-only on inputs. No disassembly, decryption, or decompression is attempted.
Header layout references are recorded in doc/history/NATIVE_RECOMP.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

PAGE = 0x1000


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from('<I', data, offset)[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def string(data: bytes) -> str:
    return data.split(b'\0', 1)[0].decode('ascii')


def segments(exheader: bytes, code_size: int) -> list[dict]:
    require(len(exheader) >= 0x400, 'Truncated extended header')
    require(not exheader[0xD] & 1, 'Compressed .code is not supported by this audit; do not use LZ11')
    result = []
    offset = 0
    for name, at, permissions in [('text', 0x10, 'rx'), ('rodata', 0x20, 'r'), ('data', 0x30, 'rw')]:
        address, pages, size = struct.unpack_from('<III', exheader, at)
        mapped = pages * PAGE
        require(address % PAGE == 0, f'{name}: unaligned guest address')
        require(size <= mapped, f'{name}: logical size exceeds page allocation')
        require(address + mapped <= 1 << 32, f'{name}: address overflow')
        require(offset + mapped <= code_size, f'{name}: truncated code image')
        for prior in result:
            require(not (address < prior['address'] + prior['mapped_size'] and
                         prior['address'] < address + mapped), 'Overlapping segments')
        result.append(dict(name=name, address=address, file_offset=offset,
                           size=size, mapped_size=mapped, permissions=permissions))
        offset += mapped
    require(offset == code_size, 'Code image length differs from the declared page allocations')
    require(result[0]['size'] >= 4, 'Missing entry instruction')
    return result


def exefs_entries(header: bytes) -> list[dict]:
    require(len(header) == 0x200, 'ExeFS header must be 512 bytes')
    result = []
    for index in range(10):
        at = index * 16
        name = string(header[at:at + 8])
        if not name:
            continue
        require(name not in [e['name'] for e in result], 'Duplicate ExeFS entry')
        offset, size = struct.unpack_from('<II', header, at + 8)
        for prior in result:
            require(not (offset < prior['offset'] + prior['size'] and
                         prior['offset'] < offset + size), 'Overlapping ExeFS entries')
        result.append(dict(name=name, offset=offset, size=size,
                           sha256=header[0x1E0 - index * 32:0x200 - index * 32].hex()))
    return result


def compare_rom(path: Path, exheader: bytes, exefs: bytes, code: bytes) -> dict:
    with path.open('rb') as stream:
        length = stream.seek(0, 2)

        def read(offset: int, size: int) -> bytes:
            require(0 <= offset <= length and size <= length - offset, 'ROM region outside file')
            stream.seek(offset)
            return stream.read(size)

        outer = read(0, 512)
        if outer[0x100:0x104] == b'NCSD':
            base = u32(outer, 0x120) * 512
            partition_size = u32(outer, 0x124) * 512
            require(base >= 512 and partition_size >= 512 and base + partition_size <= length,
                    'Invalid NCSD executable partition')
        else:
            require(outer[0x100:0x104] == b'NCCH', 'Expected .3ds/.cci NCSD or .cxi NCCH')
            base, partition_size = 0, length
        ncch = read(base, 512)
        require(ncch[0x100:0x104] == b'NCCH', 'Missing executable NCCH')
        require(ncch[0x18F] & 4, 'ROM not marked decrypted; this tool does not decrypt')
        unit = 512 << ncch[0x18E]
        require(u32(ncch, 0x104) * unit <= partition_size, 'NCCH exceeds partition')
        require(read(base + 512, len(exheader)) == exheader, 'ROM extended header differs from extraction')
        exefs_offset = u32(ncch, 0x1A0) * unit
        exefs_size = u32(ncch, 0x1A4) * unit
        require(exefs_offset + exefs_size <= partition_size, 'ExeFS exceeds partition')
        require(read(base + exefs_offset, 512) == exefs, 'ROM ExeFS header differs from extraction')
        entry = next(e for e in exefs_entries(exefs) if e['name'] == '.code')
        require(512 + entry['offset'] + entry['size'] <= exefs_size, '.code exceeds ExeFS')
        require(read(base + exefs_offset + 512 + entry['offset'], entry['size']) == code,
                'ROM .code differs from extraction')
        return dict(path=str(path.resolve()), size=length, partition_offset=base,
                    program_id=f'{struct.unpack_from("<Q", ncch, 0x118)[0]:016X}',
                    product_code=string(ncch[0x150:0x160]),
                    executable_matches=True,
                    scope='ExeFS .code and headers compared; complete RomFS content not compared')


def audit(root: Path, rom: Path | None = None) -> dict:
    exheader = (root / 'ExHeader.bin').read_bytes()
    table = (root / 'HeaderExeFS.bin').read_bytes()
    code_paths = [p for p in [root / 'ExeFS/code.bin', root / 'ExeFS/.code'] if p.is_file()]
    require(len(code_paths) == 1, 'Expected exactly one code.bin or .code')
    code = code_paths[0].read_bytes()
    layout = segments(exheader, len(code))
    entries = exefs_entries(table)
    entry = next((e for e in entries if e['name'] == '.code'), None)
    require(entry is not None, 'Missing .code entry')
    require(entry['size'] == len(code), '.code size does not match ExeFS')
    require(entry['sha256'] == sha256(code), '.code hash does not match ExeFS')
    data = layout[-1]
    services = [string(exheader[i:i + 8]) for i in range(0x250, 0x350, 8) if exheader[i]]
    # Decode only the first ARM immediate B/BL, not a whole-binary linear sweep.
    word = u32(code, 0)
    branch = None
    if word >> 28 == 0xE and word & 0x0E000000 == 0x0A000000:
        displacement = word & 0xFFFFFF
        if displacement & 0x800000:
            displacement -= 1 << 24
        target = (layout[0]['address'] + 8 + displacement * 4) & 0xFFFFFFFF
        require(layout[0]['address'] <= target < layout[0]['address'] + layout[0]['size'],
                'Entry branch target outside text')
        branch = dict(kind='BL' if word & 0x1000000 else 'B', target=target, mode='ARM')
    result = dict(schema_version=1, process_name=string(exheader[:8]),
                  program_id=f'{struct.unpack_from("<Q", exheader, 0x200)[0]:016X}',
                  code_path=str(code_paths[0].resolve()), code_size=len(code),
                  code_sha256=sha256(code), exheader_sha256=sha256(exheader),
                  exefs_code_hash_verified=True, compressed=False,
                  entrypoint=layout[0]['address'], entry_branch=branch,
                  segments=layout, stack_size=u32(exheader, 0x1C),
                  bss=dict(address=data['address'] + data['size'], size=u32(exheader, 0x3C)),
                  service_access_allowlist=services,
                  warnings=['Service permissions are not evidence of actual calls.',
                            'Entry branch is one decoded instruction, not function discovery.',
                            'No original game instructions have been executed by this audit.'])
    if rom:
        result['rom'] = compare_rom(rom, exheader, table, code)
        require(result['rom']['program_id'] == result['program_id'], 'Program IDs disagree')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path)
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.extracted, args.rom)
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f'Audit failed: {error}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Verified {report['process_name']} {report['program_id']}: {report['code_size']:,} bytes")
    print(f"SHA-256 {report['code_sha256']}")
    print(f"Entry 0x{report['entrypoint']:08X}; report: {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
