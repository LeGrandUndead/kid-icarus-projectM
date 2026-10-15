"""Independent arithmetic/predication expectations executed as compiled C."""
import os
import random
import subprocess
import unittest
from pathlib import Path

from arm32 import emit, instruction

ROOT = Path(__file__).resolve().parents[1]


class DecoderTests(unittest.TestCase):
    def test_rejects_instructions_outside_subset(self):
        for word in [0xE0000090, 0xE1A00100, 0xE12FF000, 0xEE100F10, 0xE8BD8000, 0xFA000000]:
            with self.subTest(word=hex(word)), self.assertRaises(ValueError):
                instruction(0x1000, word)

    def test_native_arithmetic_conditions_and_memory(self):
        compiler = os.environ.get('CC')
        if not compiler:
            self.fail('Set CC via tools/recomp/environment.ps1; native tests must not silently skip')
        out = ROOT / 'build/own-backend-tests'
        out.mkdir(parents=True, exist_ok=True)
        functions, checks = [], []

        def case(words, setup, verify):
            number = len(functions)
            function = emit(0x1000, words).split('RECOMP_EXPORT')[0].replace('kiu_a32', f'test_{number}')
            functions.append(function)
            checks.append(f'ctx = (Context){{0}}; ctx.r[15]=0x1000; ctx.budget=100; {setup}\n'
                          f'test_{number}(&ctx); if (!({verify})) {{ printf("case {number} failed\\n"); return 1; }}')

        def signed(value):
            return value - (1 << 32) if value & (1 << 31) else value

        randomizer = random.Random(12345)
        pairs = [(0xFFFFFFFF, 1), (0x7FFFFFFF, 1), (0x80000000, 1), (0, 1),
                 (0x80000000, 0x80000000), (0, 0)]
        pairs += [(randomizer.getrandbits(32), randomizer.getrandbits(32)) for _ in range(48)]
        for add in (False, True):
            for a, b in pairs:
                math = a + b if add else a - b
                result = math & 0xFFFFFFFF
                signed_math = signed(a) + signed(b) if add else signed(a) - signed(b)
                overflow = int(not -(1 << 31) <= signed_math < (1 << 31))
                carry = int(math > 0xFFFFFFFF) if add else int(a >= b)
                # ADDS/SUBS r2,r0,r1; input flags deliberately disagree.
                word = 0xE0902001 if add else 0xE0502001
                case([word], f'ctx.r[0]={a}u; ctx.r[1]={b}u; ctx.n=1; ctx.z=1; ctx.c=1; ctx.v=1;',
                     f'ctx.r[2]=={result}u && ctx.n=={result >> 31} && ctx.z=={int(result == 0)} && '
                     f'ctx.c=={carry} && ctx.v=={overflow} && ctx.budget==99 && ctx.r[15]==0x1004')
        for bits in range(16):
            n, z, c, v = [(bits >> i) & 1 for i in range(4)]
            truth = [z, not z, c, not c, n, not n, v, not v, c and not z,
                     not c or z, n == v, n != v, not z and n == v, z or n != v, True]
            for condition, expected in enumerate(truth):
                case([(condition << 28) | 0x03A02007],
                     f'ctx.r[2]=3; ctx.n={n}; ctx.z={z}; ctx.c={c}; ctx.v={v};',
                     f'ctx.r[2]=={7 if expected else 3} && ctx.budget==99 && '
                     f'ctx.n=={n} && ctx.z=={z} && ctx.c=={c} && ctx.v=={v}')
        # MOVS r2,#0x80000000: nonzero rotate updates C, preserves V.
        case([0xE3B02102], 'ctx.v=1;', 'ctx.r[2]==0x80000000u && ctx.n==1 && ctx.z==0 && ctx.c==1 && ctx.v==1')
        # MOVS without rotation keeps incoming C; BX sets the Thumb bit.
        case([0xE3B02000, 0xE12FFF1E], 'ctx.c=1; ctx.r[14]=0x2001;',
             'ctx.r[2]==0 && ctx.c==1 && ctx.z==1 && ctx.thumb==1 && ctx.r[15]==0x2000 && ctx.budget==98')
        # Small zero-fill loop tests predication, post-indexing, back edge and flags.
        case([0xE1500001, 0x34802004, 0x3AFFFFFC, 0xE12FFF1E],
             'ctx.r[0]=0x2000; ctx.r[1]=0x2010; ctx.r[2]=0; ctx.r[14]=0x3000; '
             'ctx.read_pages=reads; ctx.write_pages=writes; memset(page,0xA5,4096);',
             'ctx.r[0]==0x2010 && ctx.r[15]==0x3000 && ctx.z==1 && ctx.c==1 && '
             'ctx.n==0 && ctx.v==0 && ctx.budget==84 && page[15]==0 && page[16]==0xA5 && load32(page)==0')
        case([0xEF000032], '', 'ctx.svc==0x32 && ctx.exit==EXIT_SVC && ctx.r[15]==0x1004 && ctx.budget==99')
        source = '\n'.join(functions) + '\n#include <stdio.h>\n#include <stdlib.h>\nint main(void) {\n'
        source += 'Context ctx; uint8_t page[4096]; uint8_t **reads=calloc(1<<20,sizeof(void*)), **writes=calloc(1<<20,sizeof(void*));\n'
        source += 'if (!reads || !writes) return 2; reads[2]=page; writes[2]=page;\n'
        source += '\n'.join(checks) + f'\nfree(reads); free(writes); puts("PASS: {len(checks)} native state checks"); return 0; }}\n'
        (out / 'tests.c').write_text(source)
        subprocess.run([compiler, '-O1', '-I', str(ROOT / 'tools/3dsrecomp/abi'), str(out / 'tests.c'),
                        '-o', str(out / 'tests.exe')], check=True)
        subprocess.run([str(out / 'tests.exe')], check=True)


if __name__ == '__main__':
    unittest.main()
