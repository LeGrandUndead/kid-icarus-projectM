"""Generate a deliberately bounded native probe for KIU's first BSS-clear call.

Not a general ARM translator. Only the seven validated startup instructions
below are accepted. Game-derived C++ output must remain in ignored build/.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rom'))
from audit_executable import audit, require


def generate(root: Path) -> tuple[str, dict]:
    report = audit(root)
    branch = report['entry_branch']
    require(branch is not None and branch['kind'] == 'BL', 'Entry is not a direct ARM call')
    start = branch['target']
    text = report['segments'][0]
    require(all(s['address'] == text['address'] + s['file_offset'] for s in report['segments']),
            'Probe requires contiguous guest segments')
    code = Path(report['code_path']).read_bytes()
    offset = start - text['address']
    require(offset + 28 <= text['size'], 'Startup routine exceeds text')
    words = struct.unpack_from('<7I', code, offset)
    # Fail closed: no guesses about ARM flags, predication or unsupported opcodes.
    expected = (0xE59F0014, 0xE59F1014, 0xE3A02000, 0xE1500001,
                0x34802004, 0x3AFFFFFC, 0xE12FFF1E)
    require(words == expected, 'Unsupported startup routine; inspect before extending this probe')
    literals = []
    for i in range(2):
        literal_offset = offset + i * 4 + 8 + (words[i] & 0xFFF)
        require(literal_offset + 4 <= text['size'], 'Literal outside text')
        literals.append(struct.unpack_from('<I', code, literal_offset)[0])
    begin, end = literals
    require(begin == report['bss']['address'] and end == begin + report['bss']['size'],
            'Startup literals do not match the ExHeader BSS')
    require(begin < end and begin % 4 == end % 4 == 0, 'Unsupported BSS alignment/size')
    lines = [f'  r[0] = load32(0x{start + 8 + 20:08X}u);',
             f'  r[1] = load32(0x{start + 4 + 8 + 20:08X}u);',
             '  r[2] = 0;', f'L_{start + 12:08X}:',
             '  carry = r[0] >= r[1];',
             '  if (!carry) { store32(r[0], r[2]); r[0] += 4; }',
             f'  if (!carry) goto L_{start + 12:08X};',
             '  r[15] = r[14];']
    # For this routine only, carry is the sole live flag dependency. The probe
    # does not claim to preserve full CPSR or emulate the loader/thread context.
    source = r'''// Generated locally from the user's ROM. Do not redistribute.
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#include <algorithm>
int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("Pass the audited ExeFS code.bin");
    const uint32_t base = BASE, begin = BEGIN, end = END;
    const size_t code_size = CODE_SIZE;
    std::vector<uint8_t> mem(static_cast<size_t>(end - base) + 4, 0xA5);
    std::ifstream input(argv[1], std::ios::binary);
    if (!input.read(reinterpret_cast<char*>(mem.data()), code_size))
      throw std::runtime_error("Cannot read code image");
    if (input.peek() != std::char_traits<char>::eof())
      throw std::runtime_error("Unexpected code image size");
    auto load32 = [&](uint32_t addr) -> uint32_t {
      if (addr < base || uint64_t(addr) + 4 > uint64_t(base) + mem.size())
        throw std::runtime_error("Out-of-range guest read");
      size_t i = addr - base;
      return uint32_t(mem[i]) | (uint32_t(mem[i+1]) << 8) |
             (uint32_t(mem[i+2]) << 16) | (uint32_t(mem[i+3]) << 24);
    };
    // Confirm the instruction/literal range used to generate this probe.
CHECK_WORDS
    std::fill(mem.begin() + begin - base, mem.begin() + end - base, 0xA5);
    auto before = mem;
    size_t stores = 0;
    auto store32 = [&](uint32_t addr, uint32_t value) {
      if (addr < begin || uint64_t(addr) + 4 > end || (addr & 3))
        throw std::runtime_error("Store outside BSS or unaligned");
      for (unsigned i = 0; i < 4; ++i) mem[addr - base + i] = uint8_t(value >> (8*i));
      ++stores;
    };
    uint32_t r[16] = {};
    r[14] = RETURN_PC;
    bool carry = false;
BODY
    if (r[0] != end || r[1] != end || r[2] != 0 || !carry || r[15] != RETURN_PC)
      throw std::runtime_error("Unexpected final register state");
    if (stores != (end - begin) / 4) throw std::runtime_error("Wrong store count");
    for (size_t i = 0; i < mem.size(); ++i) {
      bool bss = i >= begin - base && i < end - base;
      if (mem[i] != (bss ? 0 : before[i])) throw std::runtime_error("Memory verification failed");
    }
    std::cout << "PASS: native startup probe cleared " << end - begin
              << " BSS bytes in " << stores << " stores; other memory unchanged.\n";
    std::cout << "Seven ARM instructions specialized to native C++; no game boot, GPU, or OS runtime.\n";
    return 0;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
'''
    checked = [(start + i * 4, word) for i, word in enumerate(words)]
    checked += [(start + 28, begin), (start + 32, end)]
    replacements = {'BASE': f"0x{text['address']:X}u", 'BEGIN': f'0x{begin:X}u',
                    'END': f'0x{end:X}u', 'CODE_SIZE': str(len(code)),
                    'RETURN_PC': f"0x{report['entrypoint'] + 4:X}u", 'BODY': '\n'.join(lines),
                    'CHECK_WORDS': '\n'.join(f'    if (load32(0x{at:X}u) != 0x{word:X}u) throw std::runtime_error("Probe input changed");' for at, word in checked)}
    for key, value in replacements.items():
        source = source.replace(key, value)
    return source, dict(code_sha256=report['code_sha256'], routine_address=start,
                        instruction_count=7, bss_begin=begin, bss_end=end,
                        limitation='Specialized first-call probe, not a general recompiler or game boot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, report = generate(args.extracted)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'startup_probe.cpp').write_text(source, encoding='utf-8')
    (args.output / 'probe.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
