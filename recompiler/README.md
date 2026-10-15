# KIU-specific recompiler development

`arm32.py` is the first independent translation backend. It decodes instruction
fields and emits C against the evaluated 3dsrecomp ABI 4, so we can compare it
inside the same runtime. The ABI/memory helper header remains an upstream
dependency; instruction decoding/lowering here is our implementation.

Current scope: explicit A32 ranges; all ordinary condition codes; B/BL, BX,
SVC, immediate-offset byte/word LDR/STR with selected addressing modes;
MOV/ADD/SUB/CMP with immediate or unshifted register operands. Arithmetic
flags and instruction budgets are preserved. Unsupported encodings fail at
generation time, and transfers outside the emitted range return to the host.

This is not a full game translator. No automatic function discovery, Thumb,
VFP, exclusives, coprocessors, shifted operands, multiple transfers or generic
exception handling. Word access behavior currently follows the upstream ABI
helpers; ARM alignment-mode behavior has not been independently established.
The game-wide evaluated library still uses 3dsrecomp's translation backend.

Initial checks: 352 compiled native state checks pass. The generated KIU
startup routine returns after 1,431,691 native instructions with zero fallback
and no state mismatch in the interpreter comparison (2,000,000 instruction
budget). Its 60-frame runtime capture equals the interpreter baseline exactly.
The unmodified verifier's 200,000-instruction budget stops this routine early;
those incomplete cases must not be counted as passes.

Build a locally generated first-routine library (after dot-sourcing the local
toolchain environment):

```powershell
python recompiler/arm32.py ROM/gameFiles --start 0x100024 --instructions 7 --output build/own-startup/kiu.c
& $env:CC -shared -O2 -static-libgcc -I tools/3dsrecomp/abi build/own-startup/kiu.c -o build/own-startup/kiu.dll
```

Do not replace the complete evaluated game library with this subset and call
the result a full recompilation. It is a starting point for differential tests
and incremental replacement of verified routines.
