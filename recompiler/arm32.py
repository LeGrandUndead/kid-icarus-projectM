"""Initial independent A32-to-C backend, targeting the evaluated recomp ABI.

This is deliberately a strict subset: explicit instruction ranges, no function
discovery, Thumb, VFP or instruction fallback. Unsupported encodings fail during
generation. Unlike startup_probe.py, decoding is by instruction fields, not an
exact seven-word signature. See README.md for scope and integration status.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/rom'))
from audit_executable import audit

CONDITIONS = [
    'ctx->z', '!ctx->z', 'ctx->c', '!ctx->c', 'ctx->n', '!ctx->n',
    'ctx->v', '!ctx->v', 'ctx->c && !ctx->z', '!ctx->c || ctx->z',
    'ctx->n == ctx->v', 'ctx->n != ctx->v', '!ctx->z && ctx->n == ctx->v',
    'ctx->z || ctx->n != ctx->v', '1',
]


def ror(value: int, amount: int) -> int:
    return ((value >> amount) | (value << ((32 - amount) % 32))) & 0xFFFFFFFF


def reg(index: int, pc: int) -> str:
    return f'0x{(pc + 8) & 0xFFFFFFFF:08X}u' if index == 15 else f'ctx->r[{index}]'


def instruction(pc: int, word: int) -> list[str]:
    cond = word >> 28
    if cond == 15:
        raise ValueError(f'0x{pc:08X}: unconditional extension space unsupported')
    body = []
    # B/BL immediate; target outside emitted range returns to the host dispatcher.
    if word & 0x0E000000 == 0x0A000000:
        offset = word & 0xFFFFFF
        if offset & 0x800000:
            offset -= 1 << 24
        target = (pc + 8 + offset * 4) & 0xFFFFFFFF
        if word & (1 << 24):
            body.append(f'ctx->r[14] = 0x{pc + 4:08X}u;')
        body += [f'ctx->r[15] = 0x{target:08X}u;', 'continue;']
    elif word & 0x0FFFFFF0 == 0x012FFF10:  # BX
        body += [f'uint32_t target = {reg(word & 15, pc)};',
                 'ctx->thumb = target & 1;',
                 'ctx->r[15] = target & (ctx->thumb ? ~1u : ~3u);',
                 'if (ctx->thumb) return;', 'continue;']
    elif word & 0x0F000000 == 0x0F000000:  # SVC
        body += [f'ctx->svc = 0x{word & 0xFFFFFF:X}u;',
                 f'ctx->r[15] = 0x{pc + 4:08X}u;', 'ctx->exit = EXIT_SVC;', 'return;']
    elif word & 0x0E000000 == 0x04000000:  # Immediate single transfer
        rn, rd = (word >> 16) & 15, (word >> 12) & 15
        pre, up, byte, write, load = [(word >> bit) & 1 for bit in (24, 23, 22, 21, 20)]
        if (not pre and write) or rd == 15 or (rn == 15 and (write or not pre)) or (rn == rd and (write or not pre)):
            raise ValueError(f'0x{pc:08X}: unsupported transfer/writeback combination')
        body += [f'uint32_t base = {reg(rn, pc)};',
                 f'uint32_t next = base {"+" if up else "-"} {word & 0xFFF}u;',
                 f'uint32_t addr = {"next" if pre else "base"};']
        width = 8 if byte else 32
        if load:
            body.append(f'ctx->r[{rd}] = mem_read{width}(ctx, addr);')
        else:
            body.append(f'mem_write{width}(ctx, addr, ctx->r[{rd}]);')
        if write or not pre:
            body.append(f'ctx->r[{rn}] = next;')
    elif word & 0x0C000000 == 0:  # Deliberately limited data-processing forms
        immediate = bool(word & (1 << 25))
        opcode, set_flags = (word >> 21) & 15, bool(word & (1 << 20))
        rn, rd = (word >> 16) & 15, (word >> 12) & 15
        if not immediate and word & 0xFF0:
            raise ValueError(f'0x{pc:08X}: shifted/register-extension operand unsupported')
        if opcode not in (2, 4, 10, 13) or (opcode == 10 and (not set_flags or rd != 0)):
            raise ValueError(f'0x{pc:08X}: unsupported data-processing instruction')
        if opcode != 10 and rd == 15:
            raise ValueError(f'0x{pc:08X}: ALU writes to PC unsupported')
        if opcode == 13 and rn != 0:
            raise ValueError(f'0x{pc:08X}: invalid MOV encoding')
        rotate = ((word >> 8) & 15) * 2
        operand = f'0x{ror(word & 255, rotate):08X}u' if immediate else reg(word & 15, pc)
        body += [f'uint32_t a = {reg(rn, pc)};', f'uint32_t b = {operand};']
        if opcode == 13:
            body.append('uint32_t value = b;')
        elif opcode == 4:
            body.append('uint32_t value = a + b;')
        else:
            body.append('uint32_t value = a - b;')
        if set_flags:
            body += ['ctx->n = value >> 31;', 'ctx->z = value == 0;']
            if opcode in (2, 10):
                body += ['ctx->c = a >= b;', 'ctx->v = ((a ^ b) & (a ^ value)) >> 31;']
            elif opcode == 4:
                body += ['ctx->c = ((uint64_t)a + b) >> 32;', 'ctx->v = (~(a ^ b) & (a ^ value)) >> 31;']
            elif immediate and rotate:
                body.append('ctx->c = b >> 31;')
        if opcode != 10:
            body.append(f'ctx->r[{rd}] = value;')
    else:
        raise ValueError(f'0x{pc:08X}: unsupported instruction 0x{word:08X}')
    return [f'if ({CONDITIONS[cond]}) {{', *['  ' + line for line in body], '}',
            f'ctx->r[15] = 0x{pc + 4:08X}u;', 'continue;']


def emit(start: int, words: list[int]) -> str:
    if not words or start & 3 or start + 4 * len(words) > 1 << 32:
        raise ValueError('Invalid nonempty A32 range')
    lines = ['#include "recomp.h"', 'void kiu_a32(Context *ctx) {',
             '  if (ctx->thumb) return;', '  for (;;) {',
             '    if (ctx->budget <= 0) { ctx->exit = EXIT_BUDGET; return; }',
             '    switch (ctx->r[15]) {']
    for index, word in enumerate(words):
        pc = start + index * 4
        lines += [f'    case 0x{pc:08X}u: {{', '      --ctx->budget;']
        lines += ['      ' + line for line in instruction(pc, word)]
        lines += ['    }']
    lines += ['    default: return;', '    }', '  }', '}',
              'RECOMP_EXPORT const uint32_t recomp_abi = RECOMP_ABI;',
              f'RECOMP_EXPORT const uint32_t recomp_entry_count = {len(words)};',
              'RECOMP_EXPORT const Entry recomp_entries[] = {']
    lines += [f'  {{0x{start + index * 4:08X}u, kiu_a32}},' for index in range(len(words))]
    lines += ['};', 'RECOMP_EXPORT const uint32_t recomp_module_count = 0;',
              'RECOMP_EXPORT const Module recomp_modules[1] = {{0}};']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path)
    parser.add_argument('--start', type=lambda x: int(x, 0), required=True)
    parser.add_argument('--instructions', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.extracted)
    text = report['segments'][0]
    offset = args.start - text['address']
    if not (args.instructions > 0 and 0 <= offset and offset + args.instructions * 4 <= text['size']):
        parser.error('Instruction range must be inside audited text')
    code = Path(report['code_path']).read_bytes()
    words = list(struct.unpack_from('<' + 'I' * args.instructions, code, offset))
    source = emit(args.start, words)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding='utf8')
    args.output.with_suffix('.json').write_text(json.dumps(dict(code_sha256=report['code_sha256'],
        start=args.start, instructions=args.instructions, backend='kiu-a32-subset-v1',
        abi_dependency='3dsrecomp ABI 4; translation implemented independently'), indent=2) + '\n')
