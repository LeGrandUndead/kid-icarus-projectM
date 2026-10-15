"""Disassemble the verified KIU USA touch-input path into local research output."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/python-libs'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

code = (ROOT / 'ROM/gameFiles/ExeFS/code.bin').read_bytes()
# Full fingerprint used by the launcher and executable audit.
expected = '2718aa2077a29560208c4e499288e5fecc4446d7adec95efb91ebf1b19eda679'
if hashlib.sha256(code).hexdigest() != expected:
    raise SystemExit('Executable revision does not match the inspected USA image')
decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
ranges = [(0x12D150,0x12D17C), (0x12D7E4,0x12DA08), (0x1317E8,0x131818),
          (0x14D06C,0x14D0F0), (0x16572C,0x1658C0), (0x1BA7FC,0x1BA844),
          (0xA4245C,0xA425F0), (0xA425F8,0xA42760), (0x919E90,0x919F94),
          (0xA279A4,0xA27CE0), (0x60F654,0x60F90C), (0x60FB2C,0x60FD1C),
          (0xA275BC,0xA27668), (0xB6D2A0,0xB6D2EC),
          (0xA41898,0xA41D80), (0x61050C,0x610600),
          (0x4DB974,0x4DBA94), (0x7DAA98,0x7DAF80)]
lines = ['KIU USA input-path disassembly; addresses are virtual ARM addresses.']
for start,end in ranges:
    lines.append(f'\nRange {start:08X}..{end:08X}')
    for address,size,mnemonic,operands in decoder.disasm_lite(code[start-0x100000:end-0x100000], start):
        lines.append(f'{address:08X}  {mnemonic:10} {operands}')
output = ROOT / 'build/kiu-input-disassembly.txt'
output.write_text('\n'.join(lines)+'\n')
print(output)
